"""Wirebox Python Example — Inbound Email Webhook & Auto-Reply.

Demonstrates:
1. Provisioning a dedicated Agent Identity with an atomic Mailbox and Network Tunnel.
2. Starting a local aiohttp webhook receiver behind Wirebox's secure Network Tunnel.
3. Subscribing to real-time `message.received` webhooks scoped to the agent.
4. Sending a probe email to trigger inbound delivery.
5. Cryptographic verification of the `X-Wirebox-Signature` HMAC-SHA256 header.
6. Autonomous RFC-compliant email auto-reply via the Agent Mailbox.
7. Clean teardown of temporary cloud resources.
"""

from __future__ import annotations

import asyncio
import os
import random
import string
import sys

from aiohttp import web
from dotenv import load_dotenv
from wirebox import AsyncAgentIdentity, AsyncWirebox, TunnelSession, verify_webhook

load_dotenv()

PORT = int(os.environ.get("PORT", "3456"))
PROBE_SUBJECT = "Webhook probe: Real-time autonomous delivery test (Python)"
WAIT_TIMEOUT_SECONDS = 90


def require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"\033[31m[ERROR]\033[0m Missing required environment variable: {key}", file=sys.stderr)
        print(f"Please supply your {key} in .env or environment variables.", file=sys.stderr)
        sys.exit(1)
    return val


def generate_random_handle() -> str:
    prefix = os.environ.get("AGENT_HANDLE_PREFIX", "webhook-demo-py")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


async def main() -> None:
    api_key = require_env("WIREBOX_API_KEY")
    base_url = os.environ.get("WIREBOX_BASE_URL", "https://api.wirebox.sh")
    handle = generate_random_handle()

    print("\033[36m=======================================================\033[0m")
    print("\033[36m  Wirebox Python Inbound Webhook + Auto-Reply Example  \033[0m")
    print("\033[36m=======================================================\n")

    client = AsyncWirebox(api_key=api_key, base_url=base_url)

    agent: AsyncAgentIdentity | None = None
    tunnel_session: TunnelSession | None = None
    runner: web.AppRunner | None = None
    webhook_id: str | None = None
    webhook_secret: str | None = None
    probe_completed = asyncio.Event()
    handled_probe = False

    try:
        # --------------------------------------------------------------------
        # Step 1: Create an Agent Identity with dedicated Mailbox and Tunnel
        # --------------------------------------------------------------------
        print(f"[1/6] 🤖 Provisioning Agent Identity '@{handle}'...")
        agent = await client.create_identity(
            handle,
            display_name="Python Webhook Auto-Responder",
            description="Demonstrates secure webhook reception and autonomous auto-reply in Python",
        )
        mailbox_address = agent.mailbox.email_address
        print(f"   ✓ Identity created: @{agent.agent_handle}")
        print(f"   ✓ Dedicated mailbox: {mailbox_address}\n")

        # --------------------------------------------------------------------
        # Step 2: Start local aiohttp Webhook Receiver
        # --------------------------------------------------------------------
        print(f"[2/6] 🌐 Starting local HTTP server on http://localhost:{PORT}...")

        async def handle_webhook(request: web.Request) -> web.Response:
            nonlocal handled_probe
            raw_body = await request.read()

            # ----------------------------------------------------------------
            # Cryptographic Signature Verification (HMAC-SHA256)
            # ----------------------------------------------------------------
            is_valid = verify_webhook(
                payload=raw_body,
                headers=request.headers,
                secret=webhook_secret or "",
                tolerance_seconds=300,
            )

            if not is_valid:
                print("   \033[31m✗ Incoming webhook failed signature verification!\033[0m")
                return web.json_response({"error": "Invalid signature"}, status=403)

            envelope = await request.json()
            event_type = envelope.get("event_type")
            message = envelope.get("data", {}).get("message", {})

            print("\n   \033[32m✓ Webhook Received & Cryptographically Verified!\033[0m")
            print(f"     • Event Type:  {event_type}")
            print(f"     • Event ID:    {envelope.get('id')}")
            print(f"     • From:        {message.get('from_address')}")
            print(f"     • Subject:     \"{message.get('subject')}\"")

            if (
                event_type == "message.received"
                and message.get("subject") == PROBE_SUBJECT
                and not handled_probe
                and agent
            ):
                handled_probe = True
                print("\n[6/6] ✉️  Auto-replying to original sender...")

                reply_text = (
                    f"Hello!\n\n"
                    f"This is an autonomous confirmation from @{agent.agent_handle} (Python SDK).\n"
                    f"Your email was received in real time via Wirebox Webhook and verified using HMAC-SHA256.\n\n"
                    f"Details:\n"
                    f"- Original Message ID: {message.get('id')}\n"
                    f"- Timestamp: {envelope.get('timestamp')}\n\n"
                    f"Powered by Wirebox (https://wirebox.sh)"
                )

                await agent.reply_email(message.get("id"), text=reply_text)
                print("   ✓ Reply successfully sent back into thread!")
                probe_completed.set()

            return web.json_response({"success": True})

        app = web.Application()
        app.router.add_post("/webhook", handle_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", PORT)
        await site.start()
        print(f"   ✓ Local server listening at http://127.0.0.1:{PORT}/webhook\n")

        # --------------------------------------------------------------------
        # Step 3: Establish Wirebox Network Tunnel (Zero-config public HTTPS)
        # --------------------------------------------------------------------
        print(f"[3/6] ⚡ Connecting Wirebox Network Tunnel for @{agent.agent_handle}...")
        tunnel_session = await agent.connect_tunnel(forward_to=PORT)
        webhook_url = f"{tunnel_session.public_url}/webhook"
        print(f"   ✓ Public Tunnel URL: {tunnel_session.public_url}")
        print(f"   ✓ Webhook Endpoint:  {webhook_url}\n")

        # --------------------------------------------------------------------
        # Step 4: Register Webhook Subscription
        # --------------------------------------------------------------------
        print("[4/6] 🔔 Registering Webhook subscription for 'message.received'...")
        webhook = await agent.create_webhook(
            url=webhook_url,
            events=["message.received"],
        )
        webhook_id = webhook.id
        webhook_secret = webhook.secret
        print(f"   ✓ Subscription ID:   {webhook.id}")
        print(f"   ✓ HMAC Secret:       {webhook.secret} (Keep secret in prod!)\n")

        # --------------------------------------------------------------------
        # Step 5: Send Probe Email to Trigger Inbound Delivery
        # --------------------------------------------------------------------
        print(f"[5/6] 🚀 Sending probe email to {mailbox_address}...")
        await agent.send_email(
            to=mailbox_address,
            subject=PROBE_SUBJECT,
            text="Ping from the Wirebox Python webhook example! Testing real-time edge delivery and auto-response.",
        )
        print("   ✓ Probe message queued for delivery.")
        print(f"   ⏳ Waiting up to {WAIT_TIMEOUT_SECONDS}s for inbound webhook delivery...\n")

        # --------------------------------------------------------------------
        # Wait for the full round-trip to complete
        # --------------------------------------------------------------------
        try:
            await asyncio.wait_for(probe_completed.wait(), timeout=WAIT_TIMEOUT_SECONDS)
        except TimeoutError:
            raise TimeoutError(f"No webhook received within {WAIT_TIMEOUT_SECONDS}s.")

        print("\n\033[32m=======================================================\033[0m")
        print("\033[32m  🎉 Full Round-Trip Webhook Lifecycle Successful!    \033[0m")
        print("\033[32m=======================================================\n")

    except Exception as err:
        print(f"\n\033[31m[FAILED]\033[0m Execution error: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        # --------------------------------------------------------------------
        # Step 7: Clean Teardown of Temporary Cloud Resources
        # --------------------------------------------------------------------
        print("🧹 Tearing down demo resources...")

        if webhook_id and client:
            try:
                await client.webhooks.delete(webhook_id)
                print(f"   ✓ Deleted webhook subscription '{webhook_id}'")
            except Exception as e:
                print(f"   ⚠️  Could not delete webhook: {e}")

        if tunnel_session:
            try:
                await tunnel_session.close()
                print("   ✓ Closed network tunnel session")
            except Exception as e:
                print(f"   ⚠️  Could not close tunnel: {e}")

        if runner:
            try:
                await runner.cleanup()
                print("   ✓ Stopped local aiohttp server")
            except Exception as e:
                print(f"   ⚠️  Could not stop server: {e}")

        if agent:
            try:
                await agent.delete()
                print(f"   ✓ Deleted demo agent '@{agent.agent_handle}'")
            except Exception as e:
                print(f"   ⚠️  Could not delete agent: {e}")

        await client.aclose()
        print("   Done.\n")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
