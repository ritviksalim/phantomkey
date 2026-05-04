# PhantomKey Architecture

This document describes how PhantomKey is built — the modules, the data flow for a typical request, the vault file format, and the extension points. It is for contributors and integrators; users should start with the [README](../README.md).

For *why* the design is what it is and what it defends against, read [`docs/threat-model.md`](threat-model.md) alongside this document.

---

## 1. Top-level shape

PhantomKey is a Python package with two entry points:

- A **CLI** (`phantomkey ...`) — used by humans for vault management and one-off requests.
- An **MCP server** (`phantomkey-mcp`) — used by AI agents via the Model Context Protocol.

Both entry points share the same vault, executor, and audit subsystems. The CLI runs interactively and refuses to operate without a TTY for vault-creation flows; the MCP server runs as a long-lived process unlocked by `PHANTOMKEY_MASTER_KEY`.

```
┌────────────────────────────────────────────────────────────────┐
│                          User / Agent                          │
└───────────┬────────────────────────────────┬───────────────────┘
            │ CLI invocations                │ MCP tool calls
            ▼                                ▼
   ┌─────────────────┐               ┌─────────────────┐
   │  phantomkey.cli │               │ phantomkey.mcp  │
   │   (cli.py)      │               │  (server.py)    │
   └─────────┬───────┘               └────────┬────────┘
             │                                │
             └───────────────┬────────────────┘
                             ▼
            ┌──────────────────────────────────┐
            │            Vault                 │
            │  ┌────────────────────────────┐  │
            │  │  vault/store.py            │  │
            │  │  vault/crypto.py           │  │
            │  │  vault/models.py           │  │
            │  │  vault/recovery.py         │  │
            │  └────────────────────────────┘  │
            └──────────────────────────────────┘
                             │
            ┌────────────────┴───────────────┐
            ▼                                ▼
   ┌─────────────────┐              ┌─────────────────┐
   │    Executor     │              │      Audit      │
   │  template.py    │              │      log.py     │
   │  http.py        │              └─────────────────┘
   │  sanitizer.py   │
   └────────┬────────┘                ┌─────────────────┐
            │                         │      Auth       │
            ▼                         │    access.py    │
   ┌─────────────────┐                └─────────────────┘
   │ Destination API │
   └─────────────────┘
```

---

## 2. Module map

| Module | Responsibility | Files |
|---|---|---|
| `phantomkey.cli` | Typer-based CLI commands | `cli.py` |
| `phantomkey.mcp` | MCP server exposing tools to agents | `mcp/server.py` |
| `phantomkey.vault` | Encrypted credential storage | `vault/store.py`, `vault/crypto.py`, `vault/models.py`, `vault/recovery.py` |
| `phantomkey.executor` | Template resolution, HTTP execution, response sanitization | `executor/template.py`, `executor/http.py`, `executor/sanitizer.py` |
| `phantomkey.audit` | Append-only audit log | `audit/log.py` |
| `phantomkey.auth` | Per-agent access policy enforcement | `auth/access.py` |
| `phantomkey.registration` | Email-capture-on-init webhook (waitlist) | `registration/` |

The boundaries reflect responsibility, not just code organization: every cross-module call is a place where the threat model can be examined.

---

## 3. Key hierarchy

PhantomKey uses a two-tier key hierarchy. Rotating the master password does not require re-encrypting the entire credential database — only the wrapped DEK.

```
   Master Password (user-supplied)
            │
            ▼  Scrypt(N=2^17, r=8, p=1, salt=256-bit random)
            │
        ┌───┴────────────────────┐
        │  KEK (Key-Encryption-  │   256-bit key
        │       Key)             │
        └───┬────────────────────┘
            │  AES-256-GCM (96-bit nonce)
            ▼
        ┌────────────────────────┐
        │ encrypted_dek          │   ← stored in vault.pk envelope
        └────────────────────────┘
            │  decrypt with KEK
            ▼
        ┌────────────────────────┐
        │ DEK (Data-Encryption-  │   256-bit key, random per vault
        │       Key)             │
        └───┬────────────────────┘
            │  AES-256-GCM (96-bit nonce, fresh per save)
            ▼
        ┌────────────────────────┐
        │ encrypted_data         │   ← stored in vault.pk envelope
        │   (credentials JSON)   │
        └────────────────────────┘
```

When a recovery strategy is enabled, a **second KEK** derived from the recovery phrase/key encrypts the same DEK. Either credential decrypts the vault.

```
   Recovery Phrase / Key
            │
            ▼  Scrypt(...) with separate recovery_kek_salt
            │
        Recovery KEK
            │  AES-256-GCM (separate recovery_dek_nonce)
            ▼
        recovery_encrypted_dek   ← stored alongside encrypted_dek
            │  decrypts to
            ▼
        the same DEK (which decrypts the same encrypted_data)
```

After a successful `recover`, both the master KEK and the recovery KEK are re-derived (with new salts) and the wrapped DEKs are rewritten.

---

## 4. Vault file format

The vault is a single JSON file at `~/.phantomkey/vault.pk` (path overridable via `PHANTOMKEY_VAULT_DIR`). The format is versioned for forward compatibility.

```json
{
  "version": 1,
  "kdf": "scrypt",
  "kdf_params": { "n": 131072, "r": 8, "p": 1 },
  "kek_salt":            "<base64, 32 bytes>",
  "encrypted_dek":       "<base64, AES-GCM(KEK, DEK)>",
  "dek_nonce":           "<base64, 12 bytes>",
  "encrypted_data":      "<base64, AES-GCM(DEK, vault_json)>",
  "data_nonce":          "<base64, 12 bytes>",

  "recovery_strategy":     "phrase | key",
  "recovery_kek_salt":     "<base64, 32 bytes>",
  "recovery_encrypted_dek":"<base64, AES-GCM(RecoveryKEK, DEK)>",
  "recovery_dek_nonce":    "<base64, 12 bytes>"
}
```

The bottom four `recovery_*` fields are present only if the vault was created with a recovery strategy.

The plaintext `vault_json` (inside `encrypted_data`) decrypts to:

```json
{
  "credentials": {
    "github": {
      "id": "<uuid>",
      "name": "github",
      "credential_type": "api_key",
      "service": "github.com",
      "fields": { "token": "ghp_..." },
      "tags": [],
      "notes": null,
      "created_at": "...",
      "updated_at": "...",
      "last_accessed_at": "...",
      "expires_at": null,
      "access_policy": null
    }
  },
  "version": 1,
  "sequence": 7
}
```

`sequence` increments on every save (`vault/store.py:_save`) and provides rollback detection.

---

## 5. The blind-injection request flow

The flow that defines PhantomKey. An agent makes one MCP call (`phantomkey_exec`); PhantomKey performs four phases internally.

```
┌────────────────────────────────────────────────────────────────────────┐
│  Agent (LLM)                                                           │
│  "Authorization: Bearer {{github.token}}"                              │
│  url=https://api.github.com/user                                       │
└──────────────────────┬─────────────────────────────────────────────────┘
                       │ MCP tool call: phantomkey_exec
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 1: Template Resolution  (executor/template.py)                  │
│   - Find every {{name.field}} placeholder in url, headers, body        │
│   - For each, call vault.get_field(name, field) → plaintext value      │
│   - Build secrets_used = { "github.token" → "ghp_xxxxx", ... }         │
└──────────────────────┬─────────────────────────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 2: HTTP Execution  (executor/http.py)                           │
│   - httpx.request(method, resolved_url, headers, body, timeout)        │
│   - Plaintext secret leaves the process exactly here, only as part    │
│     of the outbound request to the destination API                     │
└──────────────────────┬─────────────────────────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 3: Response Sanitization  (executor/sanitizer.py)               │
│   - For each (key, value) in secrets_used (longest-first):             │
│       response_body = response_body.replace(value,         "[REDACTED:key]") │
│       response_body = response_body.replace(urlquote(value),"[REDACTED:key]") │
│   - Same for response_headers                                          │
└──────────────────────┬─────────────────────────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 4: Return to Agent                                              │
│   - { status_code, headers, body } — all sanitized                     │
└──────────────────────┬─────────────────────────────────────────────────┘
                       │
                       ▼
                    Agent (LLM)
```

The agent sees the templated request before, the sanitized response after. **The plaintext secret value never crosses the agent boundary.**

This is the single most important code path in the project. Any change to it requires a threat-model review — see CONTRIBUTING.md.

---

## 6. Template syntax

```
{{credential_name.field_name}}
```

- `credential_name`: the name you used with `phantomkey add NAME`. May contain alphanumerics, underscores, and hyphens.
- `field_name`: a key in the credential's `fields` dict. Alphanumerics and underscores.

Regex: `\{\{([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)\}\}` (one dot, no nesting).

**Examples:**
```
{{github.token}}
{{stripe-prod.secret_key}}
{{my_db.password}}
```

Templates can appear in:
- The URL
- Header values (header *names* are not templated)
- The request body

A placeholder that references an unknown credential or field raises `KeyError` and the request is rejected before any HTTP call is made.

---

## 7. MCP tool surface

The MCP server exposes seven tools. Six return only metadata; one (`phantomkey_exec`) is the only path by which a secret leaves the vault, and only as part of an outbound HTTP request.

| Tool | Inputs | Returns |
|---|---|---|
| `phantomkey_status` | — | `{ locked, credential_count, sequence }` |
| `phantomkey_list` | `{ tag?, service? }` | array of `{ name, type, service, tags, field_names }` |
| `phantomkey_get_meta` | `{ name }` | `{ name, type, service, tags, field_names, created_at, updated_at }` |
| `phantomkey_add` | `{ name, fields, type?, service?, tags? }` | `{ success, message }` |
| `phantomkey_update` | `{ name, fields }` | `{ success, message }` |
| `phantomkey_delete` | `{ name }` | `{ success, message }` |
| `phantomkey_exec` | `{ url, method?, headers?, body?, timeout? }` | `{ status_code, headers, body }` (sanitized) |

Adding a new tool requires:
1. A schema entry in `list_tools()` (`mcp/server.py`).
2. A handler that does **not** return raw credential values.
3. A test asserting that the tool cannot be coerced into returning a secret.
4. An update to this document and the threat model.

---

## 8. Audit log

`audit/log.py` writes an append-only NDJSON log of credential events. Each entry is one line:

```json
{"ts":"2026-05-04T12:34:56Z","action":"exec","credential":"github","agent":"claude-desktop","fields":["token"],"success":true}
```

**The log records names and field names — never values.**

Current default location: `~/.phantomkey/audit.log`. The log is plaintext on disk; W-7 in the threat model tracks moving to encrypted or hash-chained storage.

---

## 9. Access control

`auth/access.py` provides per-credential access policies. Each credential has an optional `access_policy` field that is one of:

| `access_policy` | Behavior |
|---|---|
| `null` (default) | Any caller may use the credential |
| `[]` (empty list) | No caller may use the credential (effectively disabled) |
| `["agent-id-1", "agent-id-2"]` | Only listed agent IDs may use it |

Currently, agent identification is supplied at MCP-server-start time. Per-tool-call agent identification (binding a request to a specific calling agent) is on the roadmap; the current scaffolding lets you write policies, but enforcement granularity is process-wide rather than per-call.

---

## 10. CLI vs. MCP separation

A deliberate asymmetry, enforced at multiple layers:

| Operation | CLI | MCP |
|---|---|---|
| `init` | ✅ — TTY required | ❌ — refused |
| `recover` | ✅ — TTY required | ❌ — refused |
| `status`, `list`, `get_meta` | ✅ | ✅ |
| `add`, `update`, `delete` | ✅ | ✅ |
| `exec-http` / `phantomkey_exec` | ✅ | ✅ |
| Show plaintext values | ❌ | ❌ |

The TTY requirement (`cli.py:_require_tty`) prevents an agent from creating or hijacking a vault. Vault creation is exclusively a human operation.

---

## 11. Extension points

### 11.1 New executor protocol (gRPC, GraphQL, raw socket)

Add `executor/<protocol>.py` exposing an `execute_<protocol>(vault, ...)` function. It must:
1. Resolve placeholders with `template.resolve_template`.
2. Capture the `secrets_used` map.
3. Pass the response through `sanitizer.sanitize` before returning.
4. Add a corresponding MCP tool in `mcp/server.py`.

### 11.2 New credential type

Add a value to `vault/models.py:CredentialType`. Type-specific validation lives in the type itself; the vault treats fields as opaque key-value strings.

### 11.3 New recovery strategy

Subclass `vault/recovery.py:RecoveryStrategy` and implement `generate`, `derive_kek`, `display_name`, and `strategy_id`. Register it in `cli.py:recover` for detection on existing vaults.

### 11.4 New sanitization rule

Edit `executor/sanitizer.py`. Sanitization is intentionally simple (exact + URL-encoded match) to keep the trust surface narrow; complex sanitization rules are a known weakness vector and require careful review.

---

## 12. Configuration

| Variable | Effect |
|---|---|
| `PHANTOMKEY_VAULT_DIR` | Override vault location (default `~/.phantomkey`) |
| `PHANTOMKEY_MASTER_KEY` | Supply master password without prompting (used by MCP server, also by tests) |

A TOML config file at `<vault_dir>/config.toml` controls runtime parameters:

```toml
[security]
auto_lock_minutes = 15

[registration]
webhook_url = ""
```

Auto-lock enforcement is a roadmap item; the field is reserved for it.

---

## 13. Where the open-core boundary lies

**This repository (open-source core):**
- Local encrypted vault
- CLI
- MCP server
- Blind-injection executor (HTTP)
- Per-credential access control
- Local audit log

**Separate proprietary repository (paid cloud product):**
- Multi-device sync (end-to-end encrypted; key never leaves the device)
- Team vaults and credential sharing
- Hosted audit dashboard
- SSO, SCIM, RBAC
- Centralized policy management

Contributions to this repository should target the core. Feature requests that are fundamentally team/sync/dashboard-shaped are likely a fit for the cloud product — see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## 14. Further reading

- [`README.md`](../README.md) — user-facing overview
- [`docs/threat-model.md`](threat-model.md) — what we defend against and what we don't
- [`docs/mcp-integration.md`](mcp-integration.md) — Claude Desktop / Cursor / Cline setup *(coming next)*
- [`SECURITY.md`](../SECURITY.md) — vulnerability reporting
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — how to contribute
