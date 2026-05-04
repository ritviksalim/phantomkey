# PhantomKey Threat Model

This document describes what PhantomKey defends against, what it does not, and the specific design choices that produce those guarantees. It is the source of truth for any security claim made elsewhere in the project.

If you are evaluating PhantomKey for a real deployment, **read this first**.

---

## 1. Purpose

PhantomKey solves one narrow problem: **prevent secrets from entering an LLM's context window when an AI agent needs to authenticate to an API.**

That is the core asset, and most of the design follows from protecting it.

PhantomKey is *not* a general-purpose enterprise password manager. It is a focused tool for AI agent workflows.

---

## 2. Trust model

| Component | Trust level | Why |
|---|---|---|
| The host operating system kernel | **Trusted** | If the kernel is compromised, no userspace defense holds. |
| The user (the human running PhantomKey) | **Trusted** | They chose the master password and decide what to store. |
| The PhantomKey binary itself | **Trusted** | Tamper detection of the binary is out of scope; verify via PyPI / GitHub release artifacts. |
| The MCP client (Claude Desktop, Cursor, Cline, etc.) | **Partially trusted** | Trusted to deliver tool calls and responses faithfully; not trusted with secret values. |
| The LLM ("the agent") | **Untrusted with secret values, trusted with capabilities** | Can hold templates and metadata; cannot hold plaintext secrets. May still misuse capabilities. |
| The destination API the agent calls | **Untrusted** | Treated as a hostile party for the purpose of response handling. |
| The local network | **Untrusted** | All traffic is HTTPS via `httpx`. |
| The disk at rest | **Untrusted** | Vault is encrypted before write. |

The asymmetry that drives the whole design: **the LLM is trusted with the *capability* to call APIs but not trusted with the *value* of the credentials those calls require.**

---

## 3. Assets

In rough order of value:

1. **Credential values** (passwords, API keys, OAuth tokens). The crown jewels.
2. **The master password.** Compromise → all credentials decryptable.
3. **The recovery phrase / recovery key.** Compromise → all credentials decryptable.
4. **The Data-Encryption-Key (DEK).** A 256-bit key derived per vault. Compromise → all credentials decryptable from the encrypted blob alone.
5. **Credential metadata** (names, services, tags, timestamps). Lower value but still sensitive — reveals what services the user authenticates to.
6. **The audit log.** Reveals patterns of credential use.

---

## 4. Adversaries

The threat model assumes the following adversary classes:

| Adversary | Capabilities | In scope? |
|---|---|---|
| **A1. Curious agent** | LLM with access to PhantomKey MCP tools. Wants to read secrets it shouldn't. | ✅ Primary |
| **A2. Prompt-injecting attacker** | Injects malicious instructions into the agent's context (via API responses, document contents, etc.) trying to coerce the agent into exfiltrating secrets. | ✅ Primary |
| **A3. Network observer** | Sniffs traffic between the user's machine and the destination API. | ✅ |
| **A4. Disk thief** | Has the laptop / vault file but not the master password. | ✅ |
| **A5. Logging / telemetry collector** | Reads LLM provider traces, eval datasets, conversation logs that may include leaked secrets. | ✅ Primary |
| **A6. Hostile destination API** | An API the agent calls that tries to phish or exfiltrate secrets via response content. | ✅ |
| **A7. Local user without root** | A separate user account on the same machine. | ✅ |
| **A8. Local root / kernel-level attacker** | Has root on the host. | ❌ Out of scope (see §6) |
| **A9. Hardware-level attacker** | Cold-boot, DMA, side-channel. | ❌ Out of scope |
| **A10. Supply-chain attacker** | Compromises PyPI, GitHub release, or a dependency. | Partial — we publish via OIDC, sign releases, and lock dependencies, but the responsibility to verify is shared with the user. |

---

## 5. What PhantomKey defends against

### 5.1 Secrets leaking into LLM context (A1, A2, A5)

**Mechanism:** the agent never holds plaintext credentials. It calls `phantomkey_exec` with templated requests using `{{credential_name.field_name}}` placeholders. The PhantomKey process resolves placeholders, performs the HTTP request itself, and returns a sanitized response.

Tools exposed to the agent (`mcp/server.py`):

| Tool | Returns secrets? |
|---|---|
| `phantomkey_status` | No — counts only |
| `phantomkey_list` | No — names, services, tags, field *names* |
| `phantomkey_get_meta` | No — same as `list` for one credential |
| `phantomkey_add` | No — agent supplies the value, vault stores it; agent never sees existing values |
| `phantomkey_update` | No — same |
| `phantomkey_delete` | No — name only |
| `phantomkey_exec` | No — sanitized response (see §5.3) |

**There is no `phantomkey_get_secret` tool. By design.**

### 5.2 Prompt-injection-driven exfiltration (A2)

A malicious document or API response may try to coerce the agent into echoing a stored secret. Because the agent never has access to plaintext secrets, the most it can be coerced into is calling `phantomkey_exec` with a templated request that points to an attacker-controlled URL.

**Mitigations:**
- The executor performs the HTTP request itself; the agent does not get the plaintext value before or after.
- The response sanitizer (§5.3) redacts the secret if it appears echoed in the response.
- Per-credential access policies (`auth/access.py`) restrict which agents can use which credentials. *(Initial scaffolding implemented; full enforcement on the roadmap.)*

**Residual risk:** the agent can still send the secret to an attacker-controlled URL by rewriting the request URL in the templated call. The secret never enters the LLM context, but it leaves the machine to a hostile destination. Per-credential **allowed-host lists** are a planned hardening (see §10).

### 5.3 Secrets echoed in API responses (A6)

If the destination API echoes the credential back (e.g., `{"error": "invalid token: ghp_xxxxx"}`), naïvely returning the response body to the agent would leak the secret.

**Mechanism (`executor/sanitizer.py`):**
- Every secret value resolved during the request is collected into a `secrets_used` map.
- Before the response body and headers are returned, every occurrence of every used secret is replaced with `[REDACTED:credential.field]`.
- URL-encoded variants of each secret are also redacted.
- Longer secrets are processed first to avoid partial-replacement bugs.

**Residual risk:**
- An API that returns a *transformation* of the secret (e.g., a hash, a prefix, the first 4 chars) is not redacted by exact match. This is documented as an out-of-scope failure mode; users should not store credentials in services that leak fragments.
- Whitespace-altered echoes (e.g., `gh\np_xxxx`) are not redacted by exact match.

### 5.4 Disk-at-rest exposure (A4)

**Mechanism (`vault/store.py`, `vault/crypto.py`):**

- Vault file `~/.phantomkey/vault.pk` is a JSON envelope containing only ciphertext and parameters.
- **Two-tier key hierarchy:**
  - Master Password → `Scrypt(N=2^17, r=8, p=1, salt=32B)` → KEK (256-bit Key-Encryption-Key)
  - KEK + AES-256-GCM → encrypts a random per-vault DEK (256-bit Data-Encryption-Key)
  - DEK + AES-256-GCM → encrypts the credential JSON
- AES-256-GCM provides both confidentiality and integrity (authenticated encryption). Tampering with ciphertext fails decryption.
- Scrypt parameters follow OWASP recommendations as of 2024 — memory-hard, designed to resist GPU/ASIC brute force.
- Salts are 256 bits, generated with `secrets.token_bytes`.
- Nonces are 96 bits, generated with `os.urandom`, fresh per encryption.

**Why two tiers:** rotating the master password only requires re-encrypting the DEK (32 bytes), not the entire credential database. Recovery adds a parallel KEK encrypting the *same* DEK, so either credential can decrypt.

**Residual risk:**
- A weak master password reduces brute-force resistance to the strength of the password, not the strength of Scrypt. Users are advised to use a strong, unique master password.
- Scrypt parameters are not user-configurable; if quantum or hardware advances obsolete `N=2^17`, a vault format migration is required.

### 5.5 Network observation (A3)

**Mechanism:** the executor (`executor/http.py`) uses `httpx`, which uses TLS by default. Plaintext-HTTP URLs are not blocked by the library but should be — see §10.

### 5.6 Vault tampering (A4 + A8 with file write but no key)

**Mechanism:**
- AES-256-GCM authenticates the ciphertext. Modification fails decryption with `InvalidTag`.
- A monotonic `sequence` counter is included in the (encrypted) vault data and incremented on every save. Rollback to an old vault file is detectable by comparing the current sequence to the previous one.

**Residual risk:** detection of a rollback requires the user (or an external monitor) to track the sequence. PhantomKey does not currently have a tamper-evident anchor outside the vault file itself.

### 5.7 Lockout from forgotten master password (user error, not adversarial)

**Mechanism:** vault may be initialized with a recovery strategy. Two are implemented:
- `PhraseRecovery` — 12 words from a 2048-word dictionary (entropy ≈ 132 bits). Shown once at init.
- `KeyRecovery` — `PK-` prefixed base62 string, 192 bits of entropy.

The recovery credential derives a parallel KEK that encrypts the same DEK. Recovery does not require the master password, only the recovery phrase. After successful recovery, both the master password and the recovery credential are rotated.

**Residual risk:** vaults initialized with `--no-recovery` are unrecoverable on master password loss. **By design.**

---

## 6. What PhantomKey does NOT defend against

### 6.1 Root-level attackers on the host (A8)

A user with root or kernel-level access to the host machine can:

- Read the unlocked vault from process memory (`/proc/<pid>/mem`, `lldb`, `task_for_pid`)
- Install a keylogger to capture the master password the next time it is typed
- Replace the `phantomkey` binary with a malicious version
- Read `/dev/mem`, dump RAM, trigger core dumps

**This is not a vulnerability in PhantomKey.** It is a fundamental limitation of running any password manager on a compromised host. The same is true of 1Password, Bitwarden, KeePass, and every other vault. PhantomKey assumes an uncompromised host.

**Locked vault** (no PhantomKey process running) is *not* exposed — see §5.4.

### 6.2 An agent abusing the capability it has

PhantomKey hides the *value* of credentials from the LLM, not the *capability* to use them. If you grant an agent access to a credential and the agent decides to make a harmful API call, PhantomKey will faithfully execute that call.

**This is the most commonly misunderstood property of PhantomKey.** It is necessary that the agent can use the credential — that is the entire point. PhantomKey reduces the *blast radius* of compromise (no plaintext secret to exfiltrate) but does not eliminate the ability of the agent to take authorized-but-undesired actions.

Mitigations belong in adjacent layers:
- Per-credential access policies (`auth/access.py`) — limit which agents can use which credentials
- Allowed-host lists (planned, §10) — limit *where* a credential can be sent
- Agent sandboxing in your MCP client
- Rate limiting at the API itself
- Audit log monitoring (`audit/log.py`)

### 6.3 Hostile API echoing transformations of secrets (A6 partial)

The sanitizer redacts exact and URL-encoded matches of secret values. It does not redact transformations (hashes, prefixes, individual character escapes). An adversarial API designed to leak secrets via transformation can succeed.

### 6.4 Hardware attacks (A9)

Cold-boot extraction of RAM, DMA via Thunderbolt, EM side-channels, and similar are out of scope.

### 6.5 Side-channel timing on Scrypt or AES-GCM

Both primitives come from `cryptography` (the OpenSSL-backed Python library) which provides constant-time implementations on supported hardware. PhantomKey does not add new side channels. Verification against a sophisticated local attacker measuring CPU timing is out of scope.

### 6.6 Denial of service

Locking yourself out, corrupting your own vault, deleting `~/.phantomkey`, etc. are user-controllable and not in scope. Backups are the user's responsibility.

### 6.7 Compromise of the MCP client

If Claude Desktop / Cursor / Cline / etc. is itself compromised, it can inject arbitrary tool calls or alter responses. Report such issues to the respective vendors.

---

## 7. The blind-injection invariant

The single most important security property of PhantomKey:

> **For every secret stored in the vault, there is no path by which the plaintext value of that secret reaches the agent's context.**

This invariant is enforced by:
1. Every MCP tool that returns data from the vault returns metadata only.
2. The `phantomkey_exec` tool resolves placeholders inside the PhantomKey process, sends the request itself, and runs the response through the sanitizer before returning.
3. Code review for any new tool, executor, or response path must explicitly answer: *"Can a secret leak through this?"*

If you find a code path that violates this invariant, please report it via [`SECURITY.md`](../SECURITY.md). It is the single class of bug we treat as critical.

---

## 8. Known weaknesses being tracked

| ID | Weakness | Plan |
|---|---|---|
| W-1 | Sanitizer does not redact transformed secrets | Document; recommend short, opaque tokens; add detection for common transformations later |
| W-2 | `phantomkey_exec` has no allowed-host enforcement | Add per-credential `allowed_hosts` field; reject requests whose resolved URL host is not on the list |
| W-3 | Process memory not locked / wiped on exit | Implement `mlock` and best-effort zeroing; secure-enclave integration as a later milestone |
| W-4 | Plaintext-HTTP destinations not refused | Default-refuse `http://`; require explicit opt-in per credential |
| W-5 | No tamper-evident anchor outside vault file | Optional sync of monotonic sequence to OS keychain or a tamper-evident log |
| W-6 | Recovery wordlist is curated, not full BIP-39 | Replace with the canonical 2048-word list before v1.0 |
| W-7 | Audit log is plaintext on disk | Encrypt or hash-chain; current plaintext form is fine for personal use, problematic for regulated environments |
| W-8 | Master password lives in env var (`PHANTOMKEY_MASTER_KEY`) when running as MCP server | Add OS keychain unlock and biometric prompts |

---

## 9. Cryptographic parameters

| Parameter | Value | Source |
|---|---|---|
| KDF | Scrypt | `vault/crypto.py:26` |
| Scrypt N | 131,072 (2^17) | `vault/crypto.py:19` |
| Scrypt r | 8 | `vault/crypto.py:20` |
| Scrypt p | 1 | `vault/crypto.py:21` |
| Salt size | 32 bytes (256 bits) | `vault/crypto.py:38` |
| Symmetric cipher | AES-256-GCM | `vault/crypto.py:48` |
| Key size | 32 bytes (256 bits) | `vault/crypto.py:22` |
| Nonce size | 12 bytes (96 bits) | `vault/crypto.py:47` |
| Random source | `os.urandom`, `secrets.token_bytes` | Python stdlib, OS CSPRNG |
| Recovery phrase entropy | log2(2048^12) ≈ 132 bits | `vault/recovery.py` |
| Recovery key entropy | 192 bits (24 random bytes, base62-encoded) | `vault/recovery.py` |

---

## 10. Roadmap (security-relevant)

In rough priority order:

1. **Allowed-host lists per credential** — close the prompt-injection-to-attacker-URL hole (§5.2)
2. **`mlock` + best-effort zeroing of secrets in memory** — narrow the unlocked-vault window
3. **OS keychain integration** for storing the master password under biometric/passphrase prompt — eliminate `PHANTOMKEY_MASTER_KEY` env var pattern for the MCP server
4. **Refuse plaintext HTTP** by default (W-4)
5. **Sanitizer hardening** — common transformations (base64, hex, partial), structured-response awareness (JSON keys)
6. **Hash-chained / signed audit log** (W-7)
7. **Full BIP-39 wordlist** (W-6)
8. **Hardware-backed keys** (Secure Enclave on macOS, TPM on Linux/Windows)
9. **Cloud sync with end-to-end encryption** — paid product; key never leaves the local machine

---

## 11. Reporting

Vulnerabilities of any kind described here, *or any code path that violates the blind-injection invariant in §7*, should be reported via [`SECURITY.md`](../SECURITY.md). Do not file public issues.
