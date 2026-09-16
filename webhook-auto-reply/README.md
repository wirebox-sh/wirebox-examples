# Wirebox Example: Inbound Email Webhook & Auto-Reply

An end-to-end demonstration of real-world AI agent communications using [Wirebox](https://wirebox.sh): expose a local webhook receiver over a secure **Wirebox Network Tunnel**, subscribe to real-time inbound email notifications (`message.received`), verify HMAC-SHA256 signatures, and autonomously reply to senders.

> **No ngrok, public IP, or router configuration required.** Wirebox provides the agent identity, dedicated inbox, network tunnel, and webhook delivery layer in one integrated workflow.

---

## What It Does

1. **Provisions an Agent Identity**: Generates an isolated agent identity (`webhook-demo-<random>`) with a dedicated email inbox (`@wireboxmail.com`) and network tunnel.
2. **Starts a Local Webhook Receiver**: Launches an HTTP server on `localhost:3456/webhook` using Node.js.
3. **Connects Wirebox Tunnel**: Securely bridges local port `3456` to a public HTTPS endpoint (`https://<agent-handle>.tunnel.wirebox.sh`) via WebSockets.
4. **Subscribes to Webhooks**: Creates a `message.received` webhook subscription pointing to the tunnel URL. Wirebox provides an HMAC signing secret (`whsec_...`).
5. **Sends a Probe Email**: Dispatches a test message into the agent's mailbox to trigger inbound ingestion.
6. **Verifies Cryptographic Signature**: When Wirebox dispatches the webhook, the agent validates the `X-Wirebox-Signature` header using Web Crypto (`crypto.subtle`) to guarantee authenticity and prevent replay attacks.
7. **Autonomous Reply**: Automatically parses the sender's address and message ID, calling `agent.replyEmail()` to send a confirmation back into the thread.
8. **Resource Teardown**: Deletes the webhook, closes the tunnel, and removes the temporary demo agent upon completion.

---

## Architecture Flow

```text
Local Machine / Container                     Wirebox Edge Infrastructure
┌─────────────────────────┐                  ┌────────────────────────────────────────┐
│                         │                  │                                        │
│  Local HTTP Server      │◄─── WebSocket ───┤ Wirebox Network Tunnel                 │
│  (:3456/webhook)        │      Tunnel      │ (https://<handle>.tunnel.wirebox.sh)   │
│                         │                  │                   ▲                    │
│  verifyWebhook()        │                  │                   │ Webhook Dispatch   │
│  HMAC-SHA256 Check      │                  │                   │ (X-Wirebox-*)      │
│            │            │                  │                   │                    │
│            ▼            │                  │                   │                    │
│  agent.replyEmail() ────┼─── HTTPS API ───►│ Inbound Mailbox ──┘                    │
│                         │                  │ (agent@wireboxmail.com)                │
└─────────────────────────┘                  └────────────────────────────────────────┘
```

---

## Prerequisites

- **Node.js** `>= 20.0.0`
- **Wirebox API Key**: Obtainable from the [Wirebox Console](https://wirebox.sh/console) or via `wirebox me` in the CLI.

---

## Quickstart

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/wirebox-sh/wirebox-examples.git
cd wirebox-examples/webhook-auto-reply
npm install
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and supply your Wirebox API key:

```env
WIREBOX_API_KEY=wb_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Run the Demonstration

```bash
npm start
```

You will see live logs as each stage executes:

```text
=======================================================
  Wirebox Inbound Webhook + Auto-Reply Example
=======================================================

[1/6] 🤖 Provisioning Agent Identity '@webhook-demo-7x2k9q'...
   ✓ Identity created: @webhook-demo-7x2k9q
   ✓ Dedicated mailbox: webhook-demo-7x2k9q@wireboxmail.com

[2/6] 🌐 Starting local HTTP server on http://localhost:3456...
   ✓ Local server listening at http://127.0.0.1:3456/webhook

[3/6] ⚡ Connecting Wirebox Network Tunnel for @webhook-demo-7x2k9q...
   ✓ Public Tunnel URL: https://webhook-demo-7x2k9q.tunnel.wirebox.sh
   ✓ Webhook Endpoint:  https://webhook-demo-7x2k9q.tunnel.wirebox.sh/webhook

[4/6] 🔔 Registering Webhook subscription for 'message.received'...
   ✓ Subscription ID:   whk_01J8DEF456GHI789
   ✓ HMAC Secret:       whsec_...

[5/6] 🚀 Sending probe email to webhook-demo-7x2k9q@wireboxmail.com...
   ✓ Probe message queued for delivery.
   ⏳ Waiting up to 90s for inbound webhook delivery...

   ✓ Webhook Received & Cryptographically Verified!
     • Event Type:  message.received
     • Event ID:    evt_01J8DEF123ABC456
     • From:        webhook-demo-7x2k9q@wireboxmail.com
     • Subject:     "Webhook probe: Real-time autonomous delivery test"

[6/6] ✉️  Auto-replying to original sender...
   ✓ Reply successfully sent back into thread!

=======================================================
  🎉 Full Round-Trip Webhook Lifecycle Successful!
=======================================================

🧹 Tearing down demo resources...
   ✓ Deleted webhook subscription 'whk_01J8DEF456GHI789'
   ✓ Closed network tunnel session
   ✓ Stopped local HTTP server
   ✓ Deleted demo agent '@webhook-demo-7x2k9q'
   Done.
```

---

## Security: Webhook Signature Verification

To guarantee that incoming requests originate from Wirebox and have not been altered or replayed, Wirebox signs every webhook payload using **HMAC-SHA256**.

The SDK exports a universal `verifyWebhook` helper compatible with all modern JavaScript runtimes:

```typescript
import { verifyWebhook } from "@wirebox-sh/sdk";

const isValid = await verifyWebhook({
  payload: rawBody,       // Raw unparsed request body string or Buffer
  headers: req.headers,   // Incoming HTTP headers
  secret: webhookSecret,  // The whsec_... secret returned upon creation
  toleranceMs: 300_000,   // Max allowable clock drift (5 minutes)
});

if (!isValid) {
  // Reject untrusted payload immediately
  res.writeHead(403).end("Invalid signature");
  return;
}
```

---

## How to Adapt for Real AI Agents

To convert this self-terminating probe into a production agent:

1. **Remove Ephemeral Creation**: Instead of calling `client.createIdentity(...)` with a random handle, reference your existing permanent agent:
   ```typescript
   const agent = await client.getIdentity("support-bot");
   ```
2. **Hook Up an LLM**: In the webhook handler, pass the incoming message content into your agent framework (OpenAI, Anthropic Claude, Google Gemini, LangChain, or Browser Use) to generate real contextual responses:
   ```typescript
   const replyContent = await ai.generateReply({
     from: message.from_address,
     subject: message.subject,
     body: message.text,
   });

   await agent.replyEmail(message.id, { text: replyContent });
   ```
3. **Run as a Daemon**: Remove the `finally` teardown block and probe trigger to keep the tunnel and HTTP server listening indefinitely for incoming customer inquiries.

---

## License

MIT © [Wirebox](https://wirebox.sh)
