/**
 * Wirebox Vault — TOTP login example.
 *
 * Stores a login credential (with TOTP) in the zero-knowledge vault, reads it
 * back, generates a one-time code, and uses it to pass a real TOTP login
 * challenge — then cleans up.
 *
 * Target: the public TOTP challenge at https://authenticationtest.com/totpChallenge/
 *   Email:    totp@authenticationtest.com
 *   Password: pa$$w0rd
 *   Secret:   I65VU7K5ZQL7WB4E
 *
 * Requires in the environment:
 *   WIREBOX_API_KEY     an admin (or JWT) credential — this script creates & deletes a secret
 *   WIREBOX_VAULT_KEY   the vault key (the vault must already be initialized)
 *   WIREBOX_BASE_URL    optional, e.g. https://staging-api.wirebox.sh
 */

import { Wirebox, VaultSecretType, parseTotpUri } from "@wirebox-sh/sdk";

const TOTP_URI = "otpauth://totp/totp@authenticationtest.com?secret=I65VU7K5ZQL7WB4E";
const CHALLENGE_URL = "https://authenticationtest.com/login/?mode=totpChallenge";

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

const wb = new Wirebox();

// 1. Unlock the vault (derives the key client-side; the vault key never leaves this process).
const vault = await wb.vault.unlock(process.env.WIREBOX_VAULT_KEY!);
console.log("✓ Vault unlocked");

// 2. Store a login credential with TOTP. Encrypted in the browser/process; the API sees only ciphertext.
const secret = await vault.createSecret({
  type: VaultSecretType.LOGIN,
  name: "authenticationtest.com",
  description: "Demo login with TOTP",
  payload: {
    username: "totp@authenticationtest.com",
    password: "pa$$w0rd",
    service_url: "https://authenticationtest.com/totpChallenge/",
    totp: parseTotpUri(TOTP_URI),
  },
});
console.log(`✓ Stored secret ${secret.id}`);

try {
  // 3. Read it back (as an agent would) and generate the current code.
  const login = vault.getLogin(secret.id);
  const code = await vault.getTotpCode(secret.id);
  console.log(`✓ Retrieved login for ${login.username}; current code ${code.code} (${code.expiresInSeconds}s left)`);

  // 4. Use the credential + code to pass the real TOTP challenge.
  const form = new URLSearchParams({
    email: login.username ?? "",
    password: login.password ?? "",
    totpmfa: code.code,
  });
  const res = await fetch(CHALLENGE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
    redirect: "manual",
  });
  const location = res.headers.get("location") ?? "";
  console.log(`  → challenge responded ${res.status}${location ? ` → ${location}` : ""}`);
  const ok = location.includes("loginSuccess") || res.status === 302;
  assert(ok, `Login challenge did not succeed (status ${res.status}, location "${location}")`);
  console.log("✓ TOTP login challenge PASSED");
} finally {
  // 5. Clean up. Secrets can be addressed by name or id.
  await vault.deleteSecret(secret.id);
  console.log("✓ Deleted secret");
}
