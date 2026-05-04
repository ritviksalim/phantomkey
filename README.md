# PhantomKey

> AI-native password manager for AI agents — credentials are injected blindly into requests, so the LLM never sees plaintext secrets.

PhantomKey solves a single, narrow problem: **how do you give an AI agent the ability to authenticate to APIs without leaking credentials into the model context window?**

The moment a password, API token, or OAuth secret enters an LLM prompt, it is effectively compromised — it can leak through traces, logs, eval datasets, prompt injection, model fine-tuning, or third-party tool calls. PhantomKey keeps secrets out of the context window entirely.

---

## How it works

1. You store credentials locally in an encrypted vault (AES-256-GCM, Scrypt-derived key).
2. You give the agent **placeholders** instead of secrets: `Authorization: Bearer {{github.token}}`. The placeholder syntax is `{{credential_name.field_name}}` — `github` is the name you used with `phantomkey add github`, and `token` is a field name within that credential.
3. The agent calls PhantomKey's `phantomkey_exec` MCP tool with the templated request.
4. PhantomKey resolves placeholders against the vault, executes the HTTP request itself, sanitizes the response of any secret values, and returns the result.

The LLM sees the placeholders, the URL, the method, and the sanitized response. It never sees the secret.

```
   ┌──────────┐    {{name.field}}  ┌────────────┐    real secret     ┌─────────┐
   │  Agent   │  ───────────────→ │ PhantomKey │  ───────────────→  │   API   │
   │  (LLM)   │  ←─── sanitized ── │   Vault    │  ←──── response ── │         │
   └──────────┘     response       └────────────┘                    └─────────┘
```

---

## Status

**Pre-release (v0.1.0).** Local-only vault and MCP server are functional. Not yet published to PyPI. Cloud sync, team vaults, and audit dashboard are on the roadmap (paid tier).

---

## Install

> Not yet published to PyPI. For now, install from source:

```bash
git clone https://github.com/ritviksalim/phantomkey.git
cd phantomkey
pip install -e .
```

Requires Python 3.11+.

Once published, install will be:

```bash
pipx install phantomkey
```

---

## Quickstart

### 1. Initialize a vault

```bash
phantomkey init
```

You will be prompted for a master password. PhantomKey will print a 12-word recovery phrase — **write it down**. If you lose your master password and don't have the phrase, the vault is unrecoverable.

### 2. Add a credential

```bash
phantomkey add github \
  --type api_key \
  --service github.com \
  --field token=ghp_xxxxxxxxxxxxxxxxxxxx
```

### 3. Verify

```bash
phantomkey list
phantomkey get github   # shows metadata only — never the secret value
```

### 4. Use it from the CLI (test the blind-injection path)

```bash
phantomkey exec-http \
  --url https://api.github.com/user \
  --header "Authorization: Bearer {{github.token}}"
```

### 5. Wire it up to an AI agent (MCP)

Add PhantomKey to your Claude Desktop / Cursor / Cline config:

```json
{
  "mcpServers": {
    "phantomkey": {
      "command": "phantomkey-mcp",
      "env": {
        "PHANTOMKEY_MASTER_KEY": "your-master-password"
      }
    }
  }
}
```

The agent now has access to seven tools (`phantomkey_status`, `phantomkey_list`, `phantomkey_get_meta`, `phantomkey_add`, `phantomkey_update`, `phantomkey_delete`, `phantomkey_exec`). The first six expose only metadata. The seventh executes templated HTTP requests with blind injection.

> **Detailed setup:** see [`docs/mcp-integration.md`](docs/mcp-integration.md).

---

## CLI reference

| Command | Purpose |
|---|---|
| `phantomkey init` | Create a new vault (interactive only — refuses to run from an agent) |
| `phantomkey recover` | Reset master password using recovery phrase |
| `phantomkey status` | Show vault state and credential count |
| `phantomkey add NAME --field k=v` | Add a credential |
| `phantomkey get NAME` | Show metadata (never values) |
| `phantomkey list` | List all credentials |
| `phantomkey update NAME --field k=v` | Update fields on an existing credential |
| `phantomkey rm NAME` | Delete a credential |
| `phantomkey exec-http --url ... --header ...` | Execute HTTP with blind injection |

---

## Security model

PhantomKey makes specific guarantees and explicit non-guarantees. **Read [`docs/threat-model.md`](docs/threat-model.md) before deploying it for anything you care about.** Short version:

**What PhantomKey defends against**
- Secrets leaking into LLM context windows, traces, or logs
- Agents accidentally echoing credentials in responses
- Prompt injection that tries to exfiltrate stored secrets via tool calls
- Disk-at-rest exposure (vault is encrypted at rest)

**What PhantomKey does NOT defend against**
- A compromised host machine (root/admin can read the unlocked vault from memory)
- A malicious agent that uses your real credentials to make legitimate-looking but harmful API calls (PhantomKey hides the *value*, not the *capability*)
- Side-channel leakage from the destination API (e.g., an API that echoes the token in a 401 response — PhantomKey sanitizes responses, but verify your sanitizer rules cover your APIs)

To report a vulnerability, see [`SECURITY.md`](SECURITY.md). **Do not file public issues for security bugs.**

---

## Architecture

```
src/phantomkey/
  cli.py              # Typer CLI entrypoint
  vault/              # Encrypted storage, key derivation, recovery
    crypto.py
    models.py
    store.py
    recovery.py
  executor/           # Template resolution, HTTP execution, response sanitization
    template.py
    http.py
    sanitizer.py
  mcp/                # MCP server exposed to AI agents
    server.py
  audit/              # Local append-only audit log
    log.py
  auth/               # Access control between agents and credentials
    access.py
  registration/       # Email capture / onboarding
```

Full architecture: [`docs/architecture.md`](docs/architecture.md).

---

## Project shape

PhantomKey ships in two tiers:

- **Personal (free).** This repository — the local vault, CLI, and MCP server. Source is published for transparency. Free for individual personal use under the [LICENSE](LICENSE).
- **Commercial / Cloud (paid).** Multi-device sync, team vaults, hosted audit dashboard, SSO, and any use within a company or in revenue-generating work. Developed in a separate proprietary repository. Contact ritviksalim@gmail.com for licensing.

Contributions to this repository are welcome and require signing the [Contributor License Agreement](CLA.md).

---

## Roadmap

- [x] Local encrypted vault with recovery phrase
- [x] MCP server with blind credential injection
- [x] HTTP executor with response sanitization
- [ ] PyPI publish + `pipx` install
- [ ] Homebrew tap
- [ ] Per-credential access control (which agents can use which secrets)
- [ ] Audit log dashboard
- [ ] Cloud sync (paid)
- [ ] Team vaults (paid)

---

## License

PhantomKey is **source-available**, not open-source.

- **Free for personal use** — install it on your own machine, manage your own credentials, modify it for your own needs. See [`LICENSE`](LICENSE) §2 for the full grant.
- **Commercial use requires a paid license** — including any use at your job, in client work, in a product you ship, or as a hosted service. See [`LICENSE`](LICENSE) §6 for how to obtain one.
- **Source review is always permitted** — security researchers and prospective customers can read the code freely to verify the security claims, regardless of license tier. See [`LICENSE`](LICENSE) §3.

The full terms are in [`LICENSE`](LICENSE) and a plain-language summary at the bottom of that file.

> The current LICENSE is a draft pending legal review. The grants above are intended to remain stable; specific clauses may evolve.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). All contributors must sign the [`CLA`](CLA.md).
