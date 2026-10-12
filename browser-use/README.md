# Wirebox + Browser Use

Equip your [Browser Use](https://browser-use.com) AI agent with a **real Wirebox email address**.

Autonomous web agents often get stopped cold by email verification walls (OTP codes, magic links, or confirmation emails). **Wirebox** gives your browser agents real inboxes (`@wireboxmail.com`) and clean API tools so they can register for services, handle OTP codes and magic links, and complete workflows completely autonomously.

---

## ⚡️ Key Features

- **No Email Verification Blocker**: The agent signs up on websites with its own Wirebox email, waits for the verification email, parses the OTP, and completes signup.
- **Zero-Friction Self-Signup**: No pre-existing Wirebox credentials required. If run without an API key, the agent can auto-register a new mailbox on the fly.
- **Smart Inbound Waiting (`wait_for_email`)**: Built-in polling helper with keyword/sender filtering so the agent doesn't waste LLM tokens looping on inbox checks.
- **Native Async Client**: Direct, lightweight integration with Wirebox Edge REST API (`api.wirebox.sh`) without heavy proprietary dependencies.
- **Multi-Model Support**: Works seamlessly with OpenAI (`gpt-4o`) and Anthropic (`claude-3-5-sonnet`).

---

## 🛠️ Quickstart with `uv`

### 1. Prerequisites
Make sure you have [uv](https://docs.astral.sh/uv/) installed (recommended for instant, isolated Python execution):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Configure Environment
Copy the `.env.example` file and add your API keys:
```bash
cp .env.example .env
```

Edit `.env` with your preferred LLM provider:
```env
# Provide ANY ONE of the following LLM providers:
BROWSER_USE_API_KEY=...       # Browser Use Cloud (model: bu-2-0)
# or OPENAI_API_KEY=sk-...    # OpenAI (model: gpt-4o)
# or ANTHROPIC_API_KEY=sk-... # Anthropic (model: claude-3-5-sonnet)

# Optional: If you already have a Wirebox identity from Wirebox:
# WIREBOX_API_KEY=wb_live_...
# WIREBOX_EMAIL=agent-xyz@wireboxmail.com
```
*(Note: If `WIREBOX_API_KEY` is omitted, the CLI will automatically provision a new mailbox for you at startup!)*

### 3. Run the Autonomous Agent

```bash
# Example: Autonomously sign in to Notion using Wirebox email verification
uv run wirebox-browser-use "Go to notion.com, sign in with my email, wait for the verification code, and log in"
```

The agent will:
1. Launch Chromium (visible window so you can watch it work).
2. Navigate to `notion.com` and fill in the form using its Wirebox address.
3. Call `wait_for_email` to receive the verification code or magic link.
4. Enter the verification code into the page and complete login!

### Logging in with vault credentials (including 2FA)

Set `WIREBOX_VAULT_KEY` and the agent also gets `get_vault_login` and
`get_vault_totp_code` tools — it can sign in to a site using a stored login and
its TOTP two-factor code.

First store a login with TOTP and **grant it to the identity this agent runs
as** (the one whose `WIREBOX_API_KEY` is in your `.env`). For a reliable, public
demo target you can use
[authenticationtest.com](https://authenticationtest.com/totpChallenge/) — a test
account whose credentials and TOTP secret are public.

> **Two things must line up or the agent gets a 404 when it reads the vault:**
> 1. The secret **name** must match the name in your task prompt (`authenticationtest` below).
> 2. The secret must be **granted** to the identity whose API key the agent uses.

**Option A — CLI** (stores and grants to the current API key's identity in one step):

```bash
wirebox vault add --type login --name authenticationtest \
  --email totp@authenticationtest.com --password 'pa$$w0rd' \
  --url https://authenticationtest.com/totpChallenge/ \
  --totp-uri "otpauth://totp/authenticationtest?secret=I65VU7K5ZQL7WB4E"
```

**Option B — Console** ([wirebox.sh](https://wirebox.sh) → Vault → unlock → **New secret**):

| Field | Value |
| :--- | :--- |
| **Grant access** | ✅ check the identity whose `WIREBOX_API_KEY` the agent uses |
| **Name** | `authenticationtest` |
| **Type** | Login |
| **Email** | `totp@authenticationtest.com` |
| **Password** | `pa$$w0rd` |
| **URL** | `https://authenticationtest.com/totpChallenge/` |
| **TOTP** | paste `otpauth://totp/authenticationtest?secret=I65VU7K5ZQL7WB4E` into the `otpauth://` field (or upload the QR) |

Leave Username blank — this site logs in by email. Click **Save**.

Then run the agent against it:

```bash
WIREBOX_VAULT_KEY=WBV-... uv run wirebox-browser-use --browser-stay-open \
  "Go to https://authenticationtest.com/totpChallenge/ and log in using the 'authenticationtest' login from my vault, including the current 2FA code. Confirm you reach the success page."
```

The agent fetches the username and password with `get_vault_login`, submits
them, generates the live 2FA code with `get_vault_totp_code`, enters it, and
reaches the success page — all without the credentials ever being hard-coded.

---

## 💻 CLI Usage & Options

```bash
# Custom task
uv run wirebox-browser-use "Sign up on linear.app with my email and wait for confirmation"

# Run in headless mode (no GUI window)
uv run wirebox-browser-use --headless "Create an account on example.com"

# Increase or decrease maximum execution steps
uv run wirebox-browser-use --steps 60 "Complete a multi-page registration"

# Keep browser window open after task finishes (great for demo recording & inspection)
uv run wirebox-browser-use --browser-stay-open "Go to notion.com, sign in with my email, wait for the verification code, and log in"
```

---

## 🏗️ Architecture & Tools

```text
src/
├── client.py     # Native async Wirebox Edge REST client (httpx)
├── tools.py      # Browser Use Controller action registrations
├── agent.py      # System prompt injection and Browser Use Agent loop
├── config.py     # Environment settings and LLM resolution
└── cli.py        # Interactive CLI entrypoint
```

### Registered Controller Actions

| Tool Name | Parameters | Purpose |
| :--- | :--- | :--- |
| `get_agent_email` | *None* | Returns the agent's active Wirebox address (e.g. `agent-xxxx@wireboxmail.com`). |
| `wait_for_email` | `subject_contains`, `from_contains`, `timeout_seconds` | Smartly polls the inbox until a matching verification or OTP email arrives. |
| `check_inbox` | `limit` | Lists recent inbound and outbound emails with subject, snippet, and message IDs. |
| `read_email` | `message_id` | Fetches the full plain-text and HTML body of a specific email. |
| `send_email` | `to`, `subject`, `body_text` | Sends an outbound email directly from the agent's identity. |
| `get_vault_login`¹ | `name` | Fetches a stored login (username/email, password, URL) from the encrypted vault. |
| `get_vault_totp_code`¹ | `name` | Generates the current TOTP (2FA) code for a stored login. |

¹ Available only when `WIREBOX_VAULT_KEY` is set.

---

## 📚 Resources

- **Wirebox Website**: [https://wirebox.sh](https://wirebox.sh)
- **Documentation**: [https://docs.wirebox.sh](https://docs.wirebox.sh)
- **Browser Use**: [https://github.com/browser-use/browser-use](https://github.com/browser-use/browser-use)
