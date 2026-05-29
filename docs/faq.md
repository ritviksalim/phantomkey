# PhantomKey FAQ

_Last updated: 2026-05-28_

This page collects the questions developers ask most often before installing PhantomKey. It mirrors the FAQ on the marketing site and is the canonical answer source — if the website and this doc ever disagree, this file wins.

PhantomKey is a local, encrypted credential vault designed for AI agents (Claude Code, Cursor, Cline). Agents reference credentials with `{{cred.field}}` placeholders; PhantomKey injects the real secret at the network layer so the LLM context window never sees plaintext.

---

### What happens if I lose my device?

At init, PhantomKey shows you a 12-word recovery phrase — once. Save it offline (a safe, a hardware wallet, even paper). With the phrase you can restore your full vault on a new machine. PhantomKey also supports a recovery-key strategy if you'd rather not memorize a phrase.

### How do I install PhantomKey?

```bash
pipx install phantomkey
```

Requires Python 3.11 or newer. macOS, Linux, and Windows (WSL recommended) are supported.

### Does it work with Cursor, Claude Desktop, Cline, and other AI tools?

Yes. PhantomKey ships an MCP (Model Context Protocol) server — `phantomkey-mcp` — that any MCP-capable client can use. Claude Desktop, Cursor, and Cline are tested. Add it to your client's MCP config and your credentials become available as `{{vault.field}}` placeholders.

### What platforms are supported?

macOS, Linux, and Windows (WSL recommended). Requires Python 3.11+. There's no platform-specific code in the vault — paths, encryption, and MCP transport are all cross-platform.

### Is it open source? Can I audit it?

Source-available. The full source is on GitHub and you can read, audit, fork, and use it for free under the Personal Use grant. Commercial use requires a paid license. We're not AGPL or MIT, but every line of cryptography is public and verifiable.

### How is this different from .env files or 1Password?

`.env` files end up in your shell, your editor, and your AI assistant's context window — Claude Code reads `.env` files automatically. 1Password is built for humans typing passwords; it doesn't sit between an agent and the network. PhantomKey is the only vault designed for the LLM-as-caller threat model: the agent sees a placeholder, the secret is injected at the HTTP layer, and the response is sanitized before returning to the model.

### Where does the master password live? Can PhantomKey see my secrets?

The master password is scrypt-derived locally and never leaves your machine. The vault file at `~/.phantomkey/vault.pk` is AES-256-GCM encrypted at rest. PhantomKey has no cloud component in v0.1 — there's nothing to see. Optional encrypted sync is on the v2 roadmap.

### How does the `{{cred.field}}` placeholder actually work?

When the agent calls `phantomkey_exec` with a templated request (e.g. `POST api.stripe.com Authorization: Bearer {{stripe.api_key}}`), PhantomKey resolves the placeholders against the local vault, executes the HTTP request itself, strips any echoed secrets from the response, and returns the clean result. The LLM only sees the placeholder and the sanitized response.
