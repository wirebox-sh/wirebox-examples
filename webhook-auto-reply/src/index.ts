/**
 * Wirebox Example — End-to-End Inbound Email Webhook & Auto-Reply
 *
 * Demonstrates:
 * 1. Provisioning a dedicated Agent Identity with an atomic Mailbox and Network Tunnel.
 * 2. Starting a local HTTP receiver behind Wirebox's secure Network Tunnel (no ngrok required).
 * 3. Subscribing to real-time `message.received` webhooks scoped to the agent.
 * 4. Sending a probe email to trigger inbound delivery.
 * 5. Cryptographic verification of the `X-Wirebox-Signature` HMAC-SHA256 header.
 * 6. Autonomous RFC-compliant email auto-reply via the Agent Mailbox.
 * 7. Clean teardown of temporary cloud resources.
 */

import http from "node:http";
import { Wirebox, verifyWebhook } from "@wirebox-sh/sdk";
import type { AgentIdentity, TunnelSession } from "@wirebox-sh/sdk";
import dotenv from "dotenv";

dotenv.config();

const PORT = parseInt(process.env.PORT || "3456", 10);
const PROBE_SUBJECT = "Webhook probe: Real-time autonomous delivery test";
const WAIT_TIMEOUT_SECONDS = 90;

function requireEnv(key: string): string {
  const val = process.env[key]?.trim();
  if (!val) {
    console.error(`\x1b[31m[ERROR]\x1b[0m Missing required environment variable: ${key}`);
    console.error(`Please copy .env.example to .env and configure your ${key}.`);
    process.exit(1);
  }
  return val;
}

function generateRandomHandle(): string {
  const prefix = process.env.AGENT_HANDLE_PREFIX || "webhook-demo";
  const suffix = Math.random().toString(36).substring(2, 8);
  return `${prefix}-${suffix}`;
}

async function readRequestBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}

async function main() {
  const apiKey = requireEnv("WIREBOX_API_KEY");
  const baseUrl = process.env.WIREBOX_BASE_URL || "https://api.wirebox.sh";
  const handle = generateRandomHandle();

  console.log("\x1b[36m%s\x1b[0m", "=======================================================");
  console.log("\x1b[36m%s\x1b[0m", "  Wirebox Inbound Webhook + Auto-Reply Example");
  console.log("\x1b[36m%s\x1b[0m", "=======================================================\n");

  const client = new Wirebox({ apiKey, baseUrl });

  let agent: AgentIdentity | null = null;
  let server: http.Server | null = null;
  let tunnelSession: TunnelSession | null = null;
  let webhookId: string | null = null;
  let webhookSecret: string | null = null;
  let handledProbe = false;

  let resolveCompletion: () => void;
  let rejectCompletion: (err: Error) => void;
  const probeCompletion = new Promise<void>((resolve, reject) => {
    resolveCompletion = resolve;
    rejectCompletion = reject;
  });

  try {
    // ------------------------------------------------------------------------
    // Step 1: Create an Agent Identity with dedicated Mailbox and Tunnel
    // ------------------------------------------------------------------------
    console.log(`[1/6] 🤖 Provisioning Agent Identity '@${handle}'...`);
    agent = await client.createIdentity({
      agent_handle: handle,
      display_name: "Webhook Auto-Responder",
      description: "Demonstrates secure webhook reception and autonomous auto-reply",
    });

    const mailboxAddress = agent.mailbox.email_address;
    console.log(`   ✓ Identity created: @${agent.agent_handle}`);
    console.log(`   ✓ Dedicated mailbox: ${mailboxAddress}\n`);

    // ------------------------------------------------------------------------
    // Step 2: Start local HTTP Webhook Receiver on localhost:PORT
    // ------------------------------------------------------------------------
    console.log(`[2/6] 🌐 Starting local HTTP server on http://localhost:${PORT}...`);
    server = http.createServer(async (req, res) => {
      if (req.method !== "POST" || req.url !== "/webhook") {
        res.writeHead(404, { "Content-Type": "text/plain" }).end("Not Found");
        return;
      }

      try {
        const rawBody = await readRequestBody(req);

        // --------------------------------------------------------------------
        // Cryptographic Signature Verification (HMAC-SHA256)
        // --------------------------------------------------------------------
        const isValid = await verifyWebhook({
          payload: rawBody,
          headers: req.headers as Record<string, string>,
          secret: webhookSecret || "",
          toleranceMs: 300_000, // 5 minute clock drift tolerance
        });

        if (!isValid) {
          console.error("   \x1b[31m✗ Incoming webhook failed signature verification!\x1b[0m");
          res.writeHead(403, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Invalid signature" }));
          return;
        }

        // Return HTTP 200 OK immediately to acknowledge receipt
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ success: true }));

        // Parse event envelope
        const envelope = JSON.parse(rawBody);
        const eventType = envelope.event_type;
        const message = envelope.data?.message;

        console.log(`\n   \x1b[32m✓ Webhook Received & Cryptographically Verified!\x1b[0m`);
        console.log(`     • Event Type:  ${eventType}`);
        console.log(`     • Event ID:    ${envelope.id}`);
        console.log(`     • From:        ${message?.from_address}`);
        console.log(`     • Subject:     "${message?.subject}"`);

        // If this is our probe message, dispatch an autonomous reply
        if (
          eventType === "message.received" &&
          message?.subject === PROBE_SUBJECT &&
          !handledProbe &&
          agent
        ) {
          handledProbe = true;
          console.log(`\n[6/6] ✉️  Auto-replying to original sender...`);

          const replyText = [
            `Hello!`,
            ``,
            `This is an autonomous confirmation from @${agent.agent_handle}.`,
            `Your email was received in real time via Wirebox Webhook and verified using HMAC-SHA256.`,
            ``,
            `Details:`,
            `- Original Message ID: ${message.id}`,
            `- Timestamp: ${envelope.timestamp}`,
            ``,
            `Powered by Wirebox (https://wirebox.sh)`,
          ].join("\n");

          await agent.replyEmail(message.id, {
            text: replyText,
          });

          console.log(`   ✓ Reply successfully sent back into thread!`);
          resolveCompletion();
        }
      } catch (err: any) {
        console.error("   Error handling webhook request:", err);
        if (!res.headersSent) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: err.message }));
        }
      }
    });

    await new Promise<void>((resolve) => server!.listen(PORT, resolve));
    console.log(`   ✓ Local server listening at http://127.0.0.1:${PORT}/webhook\n`);

    // ------------------------------------------------------------------------
    // Step 3: Establish Wirebox Network Tunnel (Zero-config public HTTPS)
    // ------------------------------------------------------------------------
    console.log(`[3/6] ⚡ Connecting Wirebox Network Tunnel for @${agent.agent_handle}...`);
    tunnelSession = await agent.connectTunnel({
      forwardTo: PORT,
    });

    const webhookUrl = `${tunnelSession.publicUrl}/webhook`;
    console.log(`   ✓ Public Tunnel URL: ${tunnelSession.publicUrl}`);
    console.log(`   ✓ Webhook Endpoint:  ${webhookUrl}\n`);

    // ------------------------------------------------------------------------
    // Step 4: Register Webhook Subscription
    // ------------------------------------------------------------------------
    console.log(`[4/6] 🔔 Registering Webhook subscription for 'message.received'...`);
    const webhook = await agent.createWebhook({
      url: webhookUrl,
      events: ["message.received"],
    });

    webhookId = webhook.id;
    webhookSecret = webhook.secret;
    console.log(`   ✓ Subscription ID:   ${webhook.id}`);
    console.log(`   ✓ HMAC Secret:       ${webhook.secret} (Keep secret in prod!)\n`);

    // ------------------------------------------------------------------------
    // Step 5: Send Probe Email to Trigger Inbound Delivery
    // ------------------------------------------------------------------------
    console.log(`[5/6] 🚀 Sending probe email to ${mailboxAddress}...`);
    await agent.sendEmail({
      to: mailboxAddress,
      subject: PROBE_SUBJECT,
      text: "Ping from the Wirebox webhook example! Testing real-time edge delivery and auto-response.",
    });
    console.log(`   ✓ Probe message queued for delivery.`);
    console.log(`   ⏳ Waiting up to ${WAIT_TIMEOUT_SECONDS}s for inbound webhook delivery...\n`);

    // ------------------------------------------------------------------------
    // Wait for the full round-trip to complete
    // ------------------------------------------------------------------------
    const timeoutHandle = setTimeout(() => {
      rejectCompletion(new Error(`Timeout: No webhook received within ${WAIT_TIMEOUT_SECONDS}s`));
    }, WAIT_TIMEOUT_SECONDS * 1000);

    await probeCompletion;
    clearTimeout(timeoutHandle);

    console.log("\n\x1b[32m%s\x1b[0m", "=======================================================");
    console.log("\x1b[32m%s\x1b[0m", "  🎉 Full Round-Trip Webhook Lifecycle Successful!");
    console.log("\x1b[32m%s\x1b[0m", "=======================================================\n");
  } catch (err: any) {
    console.error("\n\x1b[31m[FAILED]\x1b[0m Execution error:", err?.message || err);
    process.exitCode = 1;
  } finally {
    // ------------------------------------------------------------------------
    // Step 7: Clean Teardown of Temporary Cloud Resources
    // ------------------------------------------------------------------------
    console.log("🧹 Tearing down demo resources...");

    if (webhookId && client) {
      try {
        await client.webhooks.delete(webhookId);
        console.log(`   ✓ Deleted webhook subscription '${webhookId}'`);
      } catch (e: any) {
        console.warn(`   ⚠️  Could not delete webhook: ${e.message}`);
      }
    }

    if (tunnelSession) {
      try {
        await tunnelSession.close();
        console.log(`   ✓ Closed network tunnel session`);
      } catch (e: any) {
        console.warn(`   ⚠️  Could not close tunnel: ${e.message}`);
      }
    }

    if (server) {
      try {
        await new Promise<void>((resolve) => server!.close(() => resolve()));
        console.log(`   ✓ Stopped local HTTP server`);
      } catch (e: any) {
        console.warn(`   ⚠️  Could not stop server: ${e.message}`);
      }
    }

    if (agent) {
      try {
        await agent.delete();
        console.log(`   ✓ Deleted demo agent '@${agent.agent_handle}'`);
      } catch (e: any) {
        console.warn(`   ⚠️  Could not delete agent: ${e.message}`);
      }
    }

    console.log("   Done.\n");
  }
}

main().catch((err) => {
  console.error("Fatal unhandled error:", err);
  process.exit(1);
});
