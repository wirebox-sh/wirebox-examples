# use-wirebox-vault

Vault TOTP example — store a login credential with TOTP in the zero-knowledge
vault, generate a one-time code, and use it to pass a **real** TOTP login
challenge, then clean up.

Target: the public TOTP challenge at
[authenticationtest.com/totpChallenge](https://authenticationtest.com/totpChallenge/)
(a throwaway test account whose credentials and TOTP secret are public).

## What it shows

- Client-side encryption: the password and TOTP secret are encrypted in-process
  before upload — the API only ever stores ciphertext.
- Reading a credential back and generating the current TOTP code.
- Using the credential + code to actually log in to an external service.

## Prerequisites

1. `WIREBOX_API_KEY` — an admin credential (this script creates and deletes a secret).
2. `WIREBOX_VAULT_KEY` — the vault key. The vault must already be initialized
   (via the Console or `wirebox vault init`).
3. `WIREBOX_BASE_URL` — optional, e.g. `https://staging-api.wirebox.sh`.

## Run

```bash
cd use-wirebox-vault
npm install
WIREBOX_VAULT_KEY=... npm start
```

Expected output:

```text
✓ Vault unlocked
✓ Stored secret vsec_...
✓ Retrieved login for totp@authenticationtest.com; current code 123456 (14s left)
  → challenge responded 302 → https://authenticationtest.com/loginSuccess/
✓ TOTP login challenge PASSED
✓ Deleted secret
```
