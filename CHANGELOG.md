# Changelog

All notable changes to PhantomKey are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

PhantomKey is pre-1.0; the public API may change between minor versions until v1.0 is tagged. Breaking changes are called out explicitly.

---

## [Unreleased]

### Changed
- License model formalized as **source-available with a free Personal Use grant** (drafted in `LICENSE` v1.0). Replaces the prior "all rights reserved, no rights granted" stance and the briefly-explored Apache 2.0 path. Personal use by individuals is now explicitly free; commercial use (work, client, hosted, or product use) requires a separate paid license. Source review remains permitted for all readers regardless of tier.
- `README.md` License and Project-shape sections rewritten to reflect the two-tier model
- `CONTRIBUTING.md` updated to describe the project as source-available rather than open-core/open-source

### Notes
- The `LICENSE` is a draft pending legal review. Jurisdiction (§10) is unfilled.

---

## [0.1.0] — 2026-04-25

Initial commit. Core functionality is implemented and tested.

### Added

#### Vault
- Local encrypted credential vault at `~/.phantomkey/vault.pk` (configurable via `PHANTOMKEY_VAULT_DIR`)
- AES-256-GCM authenticated encryption for vault contents
- Scrypt-derived key from master password (memory-hard KDF)
- Append-only sequence number for tamper detection
- Pluggable recovery strategies: 12-word phrase recovery (default) and recovery-key recovery
- One-time recovery-phrase display at `init` time with confirmation challenge

#### CLI (Typer-based)
- `phantomkey init` — interactive vault initialization (refuses to run from a non-TTY context, blocking agent invocation)
- `phantomkey recover` — reset master password using the recovery phrase
- `phantomkey status` — show vault state and credential count
- `phantomkey add NAME --field k=v --type ... --service ... --tag ...` — store a credential
- `phantomkey get NAME` — show credential metadata (never values)
- `phantomkey list [--tag ...] [--service ...]` — list credentials
- `phantomkey update NAME --field k=v` — update fields on an existing credential
- `phantomkey rm NAME` — delete a credential
- `phantomkey exec-http --url ... --method ... --header ... --body ...` — execute an HTTP request with blind credential injection from the CLI

#### Executor
- Template resolution for `{{cred.name.field}}` placeholders in URLs, headers, and bodies
- HTTP execution via `httpx` with configurable timeout
- Response sanitization that redacts any secret values that appear in the response body before returning it

#### MCP server
- Seven tools exposed to AI agents:
  - `phantomkey_status` — vault state (locked/unlocked, credential count)
  - `phantomkey_list` — list credentials (metadata only)
  - `phantomkey_get_meta` — get a credential's metadata (field names, never values)
  - `phantomkey_add` — store a new credential
  - `phantomkey_update` — update fields on an existing credential
  - `phantomkey_delete` — delete a credential
  - `phantomkey_exec` — execute an HTTP request with blind injection (only path for a secret to leave the vault, and only inside an outbound request)

#### Audit
- Append-only local audit log of credential reads, writes, and execs

#### Auth
- Initial scaffolding for per-credential access control between agents and credentials (full enforcement on the roadmap)

#### Registration
- Email-capture-on-init webhook for waitlist / user-acquisition

### Security

- Vault is encrypted at rest with AES-256-GCM
- Master password is never persisted; only the Scrypt-derived key is held in memory while the vault is unlocked
- `phantomkey init` and `phantomkey recover` require an interactive TTY, blocking agents from creating or hijacking vaults
- MCP tool surface exposes only metadata (six tools) plus the blind-injection executor (one tool) — secrets never flow back to the agent

### Known limitations

- An attacker with root/admin on the host can read the unlocked vault from process memory; this is a fundamental limitation of running a password manager on a compromised host (see [`SECURITY.md`](SECURITY.md))
- OS-level memory protection (`mlock`, secure enclave integration) is not yet implemented
- A vault initialized with `--no-recovery` is unrecoverable on master password loss (by design)
- The destination API can echo the secret back in error messages; the sanitizer redacts known secret values from the response, but verify your sanitization rules cover the APIs you use
- Cloud sync, team vaults, and audit dashboard are not implemented in the open-source core (planned for the proprietary cloud product)

---

[Unreleased]: https://github.com/ritviksalim/phantomkey/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ritviksalim/phantomkey/releases/tag/v0.1.0
