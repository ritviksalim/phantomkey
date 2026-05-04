# MCP Integration Guide

PhantomKey is built to be used by AI agents via the **Model Context Protocol (MCP)**. This guide walks through setting up PhantomKey with the major MCP-capable clients: Claude Desktop, Cursor, Cline, and Continue. Generic MCP clients are also supported.

---

## 1. What is MCP, briefly

The Model Context Protocol is an open protocol that lets AI assistants connect to local tools and data sources. PhantomKey is implemented as an MCP server: it advertises a set of tools, and the MCP client (Claude Desktop, Cursor, etc.) makes those tools available to the model running inside it.

The seven tools PhantomKey exposes are documented in [`docs/architecture.md` §7](architecture.md#7-mcp-tool-surface).

---

## 2. Prerequisites

1. PhantomKey installed (`pip install -e .` from source today; `pipx install phantomkey` once published).
2. A vault initialized and at least one credential added:
   ```bash
   phantomkey init
   phantomkey add github --type api_key --service github.com --field token=ghp_xxxxxxxxxxxxx
   ```
3. An MCP-capable client (latest version recommended).

---

## 3. Claude Desktop

### Locate the config file

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### Add PhantomKey

Open the config in a text editor and add a `phantomkey` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "phantomkey": {
      "command": "phantomkey-mcp",
      "env": {
        "PHANTOMKEY_MASTER_KEY": "your-master-password-here",
        "PHANTOMKEY_VAULT_DIR": "/Users/you/.phantomkey"
      }
    }
  }
}
```

Replace `your-master-password-here` with your actual master password and the vault directory path. Restart Claude Desktop. The seven PhantomKey tools should now appear in the tool picker.

> ⚠️ **Master password in plaintext.** Storing the master password in the config file is a known security tradeoff (W-8 in the [threat model](threat-model.md#8-known-weaknesses-being-tracked)). The file is readable by any process running as your user. OS keychain integration is on the roadmap; until then, see §5 for hardening options.

A complete copy-pasteable example lives at [`examples/claude_desktop_config.json`](../examples/claude_desktop_config.json).

---

## 4. Cursor

Cursor uses an MCP configuration in its settings. The exact location depends on the Cursor version.

**Cursor 0.40+:** open Settings → Features → MCP, click "Add new MCP server," and use:

| Field | Value |
|---|---|
| Name | `phantomkey` |
| Type | `stdio` |
| Command | `phantomkey-mcp` |
| Env | `PHANTOMKEY_MASTER_KEY=...`, `PHANTOMKEY_VAULT_DIR=...` |

A reference JSON config is at [`examples/cursor_config.json`](../examples/cursor_config.json).

---

## 5. Cline (VS Code extension)

Cline configures MCP servers in `cline_mcp_settings.json` (accessible via the Cline UI: "MCP Servers" → "Edit MCP Settings").

```json
{
  "mcpServers": {
    "phantomkey": {
      "command": "phantomkey-mcp",
      "env": {
        "PHANTOMKEY_MASTER_KEY": "your-master-password-here",
        "PHANTOMKEY_VAULT_DIR": "/Users/you/.phantomkey"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

The `autoApprove` list is intentionally empty — every PhantomKey tool call requires explicit approval by default. If you want to auto-approve metadata-only tools, you can add `"phantomkey_status"`, `"phantomkey_list"`, and `"phantomkey_get_meta"` (these never return secrets). **Do not auto-approve `phantomkey_exec`** — it's the only tool that can send a secret over the network, and it should always be reviewed.

A reference is at [`examples/cline_config.json`](../examples/cline_config.json).

---

## 6. Alternate launch: `python -m`

If `phantomkey-mcp` is not on your `$PATH` (for example, you are running from a virtualenv that the MCP client doesn't see), the same runner is also reachable via the Python module form:

```bash
/path/to/.venv/bin/python -m phantomkey.mcp
```

This is equivalent to invoking the `phantomkey-mcp` script. Use it as the `command` in your MCP client config if you need to pin to a specific Python interpreter.

---

## 7. Verifying the integration

After adding the config and restarting your client:

1. Ask the agent: *"What credentials does PhantomKey have stored?"* — it should call `phantomkey_list` and reply with a list of credential **names**, services, and field names. **No secret values should appear.**
2. Ask the agent: *"Make a GET request to https://api.github.com/user using my GitHub token."* — it should:
   - Call `phantomkey_get_meta` for `github` to see the field names.
   - Call `phantomkey_exec` with `Authorization: Bearer {{github.token}}`.
   - Receive a sanitized response — your username, profile fields, etc.

If the response contains a literal `{{github.token}}` string instead of a successful API call, the placeholder did not resolve. Check that the credential name in your placeholder matches `phantomkey list` output exactly.

---

## 8. Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| MCP client says "phantomkey: connection failed" | `phantomkey-mcp` not on PATH | Verify with `which phantomkey-mcp`; if the MCP client uses a different shell environment, switch the `command` to the absolute path or the `python -m phantomkey.mcp` form (§6) |
| Agent says "vault is locked" | `PHANTOMKEY_MASTER_KEY` env not set or wrong | Check the env block; remember this is the master *password*, not a key file |
| Tool list is empty | MCP client didn't reload | Fully quit and restart the client (not just close the window) |
| `phantomkey_exec` returns an error mentioning `{{...}}` | Placeholder didn't match a credential | Verify `phantomkey list` shows the name exactly; remember syntax is `{{name.field}}` (one dot) |
| Agent gets metadata but every `phantomkey_exec` fails | Network, the destination API, TLS issue — not PhantomKey | Try `phantomkey exec-http` with the same template from the CLI to isolate |
| Secrets appearing in agent context | **Critical bug — stop and report** | See [`SECURITY.md`](../SECURITY.md). This violates the blind-injection invariant and should never happen. |

---

## 9. Security considerations

### Master password storage

Storing `PHANTOMKEY_MASTER_KEY` in the MCP client config is the current state and has known limitations:

- The config file is readable by any process running as your user.
- It will appear in process trees and may be logged by some clients.
- It is not encrypted at rest.

For now, mitigations:
- **File permissions**: `chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json` (and equivalents on Linux/Windows).
- **Use a dedicated secondary vault** for credentials you grant to agents, separate from anything you would not store this way (e.g., your bank password). Multiple `PHANTOMKEY_VAULT_DIR` paths can coexist.
- **Don't sync the config file to git or cloud storage.** Add it to your `.gitignore` if you keep dotfiles in version control.

OS keychain integration (macOS Keychain, Windows Credential Manager, libsecret on Linux) is on the roadmap as W-8.

### Auto-approval

The `autoApprove` (Cline) / equivalent settings let you skip the per-call confirmation prompt. Recommendations:

| Tool | Auto-approve? |
|---|---|
| `phantomkey_status` | Safe |
| `phantomkey_list` | Safe |
| `phantomkey_get_meta` | Safe |
| `phantomkey_add` | Discouraged — agents shouldn't add credentials silently |
| `phantomkey_update` | Discouraged |
| `phantomkey_delete` | **Never** |
| `phantomkey_exec` | **Never** — every credential use should be reviewed |

### Per-credential access policies

Once enforcement is fully wired (`auth/access.py`), you can scope each credential to a specific agent identifier. This is the future-proof way to limit blast radius if one agent is compromised.

```bash
phantomkey add stripe-prod \
  --type api_key \
  --service stripe.com \
  --field secret=sk_live_... \
  --tag prod
# ...then once access policies ship, restrict it to a specific agent.
```

---

## 10. Bigger-picture: what good usage looks like

A few practices that are worth adopting from day one:

1. **One credential per service per use case.** A PhantomKey credential is cheap to create. Don't reuse the same `github` credential across personal projects, work, and open-source — make `github-personal`, `github-work-readonly`, `github-oss-bot`. This makes audit logs interpretable and makes per-credential access policies meaningful.
2. **Tag credentials by environment.** `--tag prod`, `--tag dev`, `--tag readonly`. Makes it easy to grep `phantomkey list --tag prod` and review what an agent has access to.
3. **Review the audit log.** `cat ~/.phantomkey/audit.log | jq` (the log is NDJSON). Anomalies — credentials used at unusual times, unusual count of requests, unusual fields used — are signal.
4. **Rotate credentials periodically.** PhantomKey doesn't yet automate rotation; that's on the roadmap. Until then, rotate manually as you would without PhantomKey.

---

## 11. Further reading

- [`README.md`](../README.md) — overview and CLI reference
- [`docs/architecture.md`](architecture.md) — modules, MCP tool surface (§7), request flow (§5)
- [`docs/threat-model.md`](threat-model.md) — what the integration does and doesn't defend against
- [`SECURITY.md`](../SECURITY.md) — vulnerability reporting
- [`examples/`](../examples/) — copy-pasteable configs and a sample agent session
