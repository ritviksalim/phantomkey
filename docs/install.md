# Installing PhantomKey

Last updated: 2026-05-28

PhantomKey is distributed on PyPI as the `phantomkey` package. The recommended installer is [`pipx`](https://pipx.pypa.io/), which installs the CLI into an isolated environment and puts the `phantomkey` and `phantomkey-mcp` commands on your `PATH`.

## Prerequisites

- **Python 3.11 or newer.** PhantomKey is tested on 3.11, 3.12, and 3.13.
- **`pipx`.** Installation instructions vary by platform — see below.

You can confirm your Python version with:

```bash
python3 --version
```

If `python3` reports a version older than 3.11, install a newer Python before continuing.

## macOS

Install `pipx` via Homebrew, then install PhantomKey:

```bash
brew install pipx
pipx ensurepath
pipx install phantomkey
```

After `pipx ensurepath`, open a new terminal so the updated `PATH` takes effect.

## Linux (Debian / Ubuntu)

Install `pipx` from `apt`, then install PhantomKey:

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
pipx install phantomkey
```

On older Debian/Ubuntu releases that do not ship `pipx`, install it with `python3 -m pip install --user pipx` instead.

## Windows (WSL)

Native Windows is **not officially tested**. Use Windows Subsystem for Linux:

1. Enable WSL2 and install Ubuntu from the Microsoft Store. Microsoft's setup guide: [https://learn.microsoft.com/windows/wsl/install](https://learn.microsoft.com/windows/wsl/install).
2. Launch the Ubuntu shell and follow the [Linux (Debian / Ubuntu)](#linux-debian--ubuntu) steps above.

> **TODO:** Confirm with maintainer — whether the team plans to publish an officially supported native Windows install path (e.g., a signed installer or a tested `pipx` flow on PowerShell).

## Verifying

Confirm the CLI is installed and on your `PATH`:

```bash
phantomkey --version
```

You should see output like `phantomkey 0.1.0`. If the command is not found, run `pipx ensurepath` again and reopen your terminal.

You can also list every subcommand:

```bash
phantomkey --help
```

## Updating

`pipx` can upgrade PhantomKey in place:

```bash
pipx upgrade phantomkey
```

To pin a specific version:

```bash
pipx install --force phantomkey==0.1.0
```

Review the [CHANGELOG](../CHANGELOG.md) before upgrading across a minor version — PhantomKey is pre-1.0, so minor releases may include breaking changes.

## Uninstalling

Remove the CLI:

```bash
pipx uninstall phantomkey
```

This removes the `phantomkey` and `phantomkey-mcp` commands but **leaves your encrypted vault in place**. To delete the vault as well:

```bash
rm -rf ~/.phantomkey
```

If you set `PHANTOMKEY_VAULT_DIR` to a custom location, remove that directory instead. Deleting the vault is **irreversible** — make sure you have either exported your credentials elsewhere or are intentionally wiping them.

## Optional: browser executor

The browser executor (for blind credential injection into web forms) requires the `browser` extra and a Playwright runtime:

```bash
pipx install 'phantomkey[browser]'
pipx runpip phantomkey install playwright
playwright install chromium
```

See the [CHANGELOG](../CHANGELOG.md) Unreleased section for the current status of the browser executor.

## Next steps

- [Quickstart](quickstart.md) — get a vault working in five minutes.
- [MCP integration](mcp-integration.md) — wire PhantomKey into Claude Desktop, Cursor, or Cline.
- [Architecture](architecture.md) — how the vault, executor, and MCP server fit together.
- [FAQ](faq.md) — common questions about install, security, and licensing.
