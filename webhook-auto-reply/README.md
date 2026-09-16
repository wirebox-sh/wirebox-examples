# Wirebox Example: Inbound Email Webhook & Auto-Reply (Python)

An end-to-end demonstration of real-world AI agent communications using [Wirebox](https://wirebox.sh) and Python: expose a local webhook receiver over a secure **Wirebox Network Tunnel**, subscribe to real-time inbound email notifications (`message.received`), verify HMAC-SHA256 signatures, and autonomously reply to senders.

> **No ngrok, public IP, or router configuration required.** Wirebox provides the agent identity, dedicated inbox, network tunnel, and webhook delivery layer in one integrated workflow.

---

## What It Does

1. **Provisions an Agent Identity**: Generates an isolated agent identity (`webhook-demo-py-<random>`) with a dedicated email inbox (`@wireboxmail.com`) and network tunnel.
2. **Starts a Local Webhook Receiver**: Launches an asynchronous `aiohttp` HTTP server on `localhost:3456/webhook`.
3. **Connects Wirebox Tunnel**: Securely bridges local port `3456` to a public HTTPS endpoint (`https://<agent-handle>.tunnel.wirebox.sh`) via WebSockets.
4. **Subscribes to Webhooks**: Creates a `message.received` webhook subscription pointing to the tunnel URL. Wirebox provides an HMAC signing secret (`whsec_...`).
5. **Sends a Probe Email**: Dispatches a test message into the agent's mailbox to trigger inbound ingestion.
6. **Verifies Cryptographic Signature**: When Wirebox dispatches the webhook, the agent validates the `X-Wirebox-Signature` header using `verify_webhook` to guarantee authenticity and prevent replay attacks.
7. **Autonomous Reply**: Automatically parses the sender's address and message ID, calling `agent.reply_email()` to send a confirmation back into the thread.
8. **Resource Teardown**: Deletes the webhook, closes the tunnel, and removes the temporary demo agent upon completion.

---

## Architecture Flow

```text
Local Machine / Container                     Wirebox Edge Infrastructure
┌─────────────────────────┐                  ┌────────────────────────────────────────┐
│                         │                  │                                        │
│  aiohttp Server         │◄─── WebSocket ───┤ Wirebox Network Tunnel                 │
│  (:3456/webhook)        │      Tunnel      │ (https://<handle>.tunnel.wirebox.sh)   │
│                         │                  │                   ▲                    │
│  verify_webhook()       │                  │                   │ Webhook Dispatch   │
│  HMAC-SHA256 Check      │                  │                   │ (X-Wirebox-*)      │
│            │            │                  │                   │                    │
│            ▼            │                  │                   │                    │
│  agent.reply_email() ───┼─── HTTPS API ───►│ Inbound Mailbox ──┘                    │
│                         │                  │ (agent@wireboxmail.com)                │
└─────────────────────────┘                  └────────────────────────────────────────┘
```

---

## Prerequisites

- **Python** `>= 3.11`
- **uv** (recommended) or **pip**
- **Wirebox API Key**: Obtainable from the [Wirebox Console](https://wirebox.sh/console) or via `wirebox me` in the CLI.

---

## Quickstart

### 1. Clone & Configure Environment

```bash
git clone https://github.com/wirebox-sh/wirebox-examples.git
cd wirebox-examples/webhook-auto-reply

cp .env.example .env
```

Edit `.env` and supply your Wirebox API key:

```env
WIREBOX_API_KEY=wb_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Run the Demonstration

Using `uv` (recommended):

```bash
uv run python src/main.py
```

Or install with pip and run:

```bash
pip install -e .
python src/main.py
```

You will see live logs as each stage executes:

```text
=======================================================
  Wirebox Python Inbound Webhook + Auto-Reply Example  
=======================================================

[1/6] 🤖 Provisioning Agent Identity '@webhook-demo-py-7x2k9q'...
   ✓ Identity created: @webhook-demo-py-7x2k9q
   ✓ Dedicated mailbox: webhook-demo-py-7x2k9q@wireboxmail.com

[2/6] 🌐 Starting local HTTP server on http://localhost:3456...
   ✓ Local server listening at http://127.0.0.1:3456/webhook

[3/6] ⚡ Connecting Wirebox Network Tunnel for @webhook-demo-py-7x2k9q...
   ✓ Public Tunnel URL: https://webhook-demo-py-7x2k9q.tunnel.wirebox.sh
   ✓ Webhook Endpoint:  https://webhook-demo-py-7x2k9q.tunnel.wirebox.sh/webhook

[4/6] 🔔 Registering Webhook subscription for 'message.received'...
   ✓ Subscription ID:   whk_01J8DEF456GHI789
   ✓ HMAC Secret:       whsec_... (Keep secret in prod!)

[5/6] 🚀 Sending probe email to webhook-demo-py-7x2k9q@wireboxmail.com...
   ✓ Probe message queued for delivery.
   ⏳ Waiting up to 90s for inbound webhook delivery...

   ✓ Webhook Received & Cryptographically Verified!
     • Event Type:  message.received
     • Event ID:    evt_01J8DEF123ABC456
     • From:        webhook-demo-py-7x2k9q@wireboxmail.com
     • Subject:     "Webhook probe: Real-time autonomous delivery test (Python)"

[6/6] ✉️  Auto-replying to original sender...
   ✓ Reply successfully sent back into thread!

=======================================================
  🎉 Full Round-Trip Webhook Lifecycle Successful!    
=======================================================

🧹 Tearing down demo resources...
   ✓ Deleted webhook subscription 'whk_01J8DEF456GHI789'
   ✓ Closed network tunnel session
   ✓ Stopped local aiohttp server
   ✓ Deleted demo agent '@webhook-demo-py-7x2k9q'
   Done.
```

---

## Security: Webhook Signature Verification

To guarantee that incoming requests originate from Wirebox and have not been altered or replayed, Wirebox signs every webhook payload using **HMAC-SHA256**.

The `wirebox` SDK provides a built-in `verify_webhook` helper:

```python
from wirebox import verify_webhook

is_valid = verify_webhook(
    payload=raw_body,              # Raw bytes or string of incoming request body
    headers=request.headers,       # Request headers (case-insensitive)
    secret=webhook_secret,         # The whsec_... secret returned upon creation
    tolerance_seconds=300,         # Maximum allowable clock drift (5 minutes)
)

if not is_valid:
    # Reject untrusted payload immediately
    return web.json_response({"error": "Invalid signature"}, status=403)
```

---

## How to Adapt for Real AI Agents

To convert this self-terminating probe into a production agent:

1. **Remove Ephemeral Creation**: Instead of calling `client.create_identity(...)` with a random handle, reference your existing permanent agent:
   ```python
   agent = await client.get_identity("support-bot")
   ```
2. **Hook Up an LLM**: In the webhook handler, pass the incoming message content into your agent framework (OpenAI, Anthropic Claude, Google Gemini, LangChain, or Browser Use) to generate real contextual responses:
   ```python
   reply_content = await ai.generate_reply(
       sender=message.get("from_address"),
       subject=message.get("subject"),
       body=message.get("text"),
   )

   await agent.reply_email(message.get("id"), text=reply_content)
   ```
3. **Run as a Daemon**: Remove the `finally` teardown block and probe trigger to keep the tunnel and HTTP server listening indefinitely for incoming customer inquiries.

---

## License

MIT © [Wirebox](https://wirebox.sh)
