# Quickstart

Last updated: 2026-05-28

This walkthrough gets you from zero to an AI agent making authenticated API calls **without ever seeing the secret** — in about five minutes.

## 1. Install

```bash
pipx install phantomkey
```

For platform-specific instructions (macOS, Linux, WSL) and prerequisites, see [Install](install.md).

## 2. Initialize the vault

```bash
phantomkey init
```

You will be prompted to set a master password, then PhantomKey will print a **12-word recovery phrase** and ask you to confirm three of the words.

> ## Save your recovery phrase NOW
>
> **The 12-word phrase will be shown exactly once. If you lose both your master password and your recovery phrase, your vault is unrecoverable — there is no backdoor, no cloud copy, no support reset.**
>
> Write it down on paper. Store it somewhere you trust. Do not save it in a cloud note, a screenshot, or another password manager that lives on the same machine. See [Recovery](recovery.md) for storage best practices.

The vault is created at `~/.phantomkey/vault.pk` by default. Override the location with the `PHANTOMKEY_VAULT_DIR` environment variable.

Confirm it worked:

```bash
phantomkey status
```

You should see `Vault: unlocked` and `Credentials: 0`.

## 3. Store a credential

Add an API key. The `--field` flag takes `key=value` pairs — store as many fields as the credential needs (token, secret, account ID, etc.):

```bash
phantomkey add stripe --field key=sk_test_REPLACE_WITH_YOUR_KEY
```

List what's in the vault — metadata only, never values:

```bash
phantomkey list
phantomkey get stripe
```

`phantomkey get` shows the credential's name, type, service, tags, and **field names** — but never field values. There is no CLI command that prints a secret in plaintext. The only path a secret can leave the vault is through the blind-injection executor.

## 4. Hook into your AI client

Add PhantomKey's MCP server to your AI client config. For Claude Desktop, edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent on your platform, and add:

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

Restart Claude Desktop. The agent now has access to PhantomKey's MCP tools — `phantomkey_status`, `phantomkey_list`, `phantomkey_get_meta`, `phantomkey_add`, `phantomkey_update`, `phantomkey_delete`, `phantomkey_exec`, and (with the `browser` extra) `phantomkey_browser`.

For Cursor, Cline, and other MCP-compatible clients, plus details on running the MCP server without putting the master password in the config file, see [MCP integration](mcp-integration.md).

## 5. Use it

Ask the agent to make an authenticated call using a placeholder instead of the real secret. For example, in Claude Desktop:

> Call the Stripe API to list my last 3 charges. Use `Authorization: Bearer {{stripe.key}}` for auth.

When the agent invokes `phantomkey_exec`, here is what each party sees:

**What the LLM sends to PhantomKey (and what appears in any agent trace, log, or eval):**

```http
GET https://api.stripe.com/v1/charges?limit=3
Authorization: Bearer {{stripe.key}}
```

**What PhantomKey actually puts on the wire to Stripe:**

```http
GET https://api.stripe.com/v1/charges?limit=3
Authorization: Bearer sk_test_REPLACE_WITH_YOUR_KEY
```

**What PhantomKey returns to the LLM:** the HTTP response from Stripe, with any occurrences of your actual `sk_test_…` value redacted from the body before the agent sees it.

You can test the same blind-injection flow from the CLI without an agent:

```bash
phantomkey exec-http \
  --url https://api.stripe.com/v1/charges?limit=3 \
  --header "Authorization: Bearer {{stripe.key}}"
```

## What's next

- [Install](install.md) — platform-specific setup, updating, uninstalling.
- [Recovery](recovery.md) — how the 12-word phrase works and how to restore a vault on a new machine.
- [MCP integration](mcp-integration.md) — full client setup for Claude Desktop, Cursor, Cline, and others.
- [Architecture](architecture.md) — how vault encryption, template resolution, and response sanitization fit together.
- [Threat model](threat-model.md) — what PhantomKey defends against, and what it does not.
- [FAQ](faq.md) — common questions.
