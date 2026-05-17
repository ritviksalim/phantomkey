# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""PhantomKey CLI — Typer-based command-line interface."""

import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from phantomkey.vault.models import CredentialType
from phantomkey.vault.store import Vault, VaultLocked

app = typer.Typer(name="phantomkey", help="AI-native password manager for AI agents.")
console = Console()


def _get_vault_dir() -> Path:
    return Path(os.environ.get("PHANTOMKEY_VAULT_DIR", Path.home() / ".phantomkey"))


def _get_master_key() -> bytes:
    key = os.environ.get("PHANTOMKEY_MASTER_KEY")
    if key:
        return key.encode()
    return typer.prompt("Master password", hide_input=True).encode()


def _get_vault(unlock: bool = True) -> Vault:
    vault = Vault(_get_vault_dir())
    if unlock:
        vault.unlock(_get_master_key())
    return vault


def _require_tty():
    """Refuse to run if not in an interactive terminal (blocks MCP/agent use).

    Skipped when PHANTOMKEY_MASTER_KEY is set (programmatic/test mode).
    """
    if os.environ.get("PHANTOMKEY_MASTER_KEY"):
        return  # Programmatic mode — TTY not required
    if not sys.stdin.isatty():
        console.print("[red]This command requires an interactive terminal. It cannot be run by an AI agent.[/red]")
        raise typer.Exit(code=1)


def _version_callback(value: bool) -> None:
    if value:
        from phantomkey import __version__

        console.print(f"phantomkey {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the PhantomKey version and exit.",
        ),
    ] = None,
) -> None:
    """AI-native password manager for AI agents."""


@app.command()
def init(
    no_recovery: Annotated[bool, typer.Option("--no-recovery", help="Skip recovery phrase generation")] = False,
):
    """Initialize a new PhantomKey vault. Must be run interactively by a human."""
    _require_tty()
    vault_dir = _get_vault_dir()
    vault = Vault(vault_dir)

    try:
        master_key = _get_master_key()

        if no_recovery:
            vault.init(master_key)
            console.print(f"[green]Vault initialized at {vault_dir}[/green]")
            console.print("[yellow]Warning: No recovery phrase. If you lose your master password, the vault is unrecoverable.[/yellow]")
        else:
            from phantomkey.vault.recovery import PhraseRecovery, pick_challenge_words

            strategy = PhraseRecovery()
            phrase = vault.init_with_recovery(master_key, strategy)

            # Display recovery phrase
            words = phrase.split()
            console.print()
            console.print("[bold red]RECOVERY PHRASE — Write this down and store it safely![/bold red]")
            console.print("[red]This will NOT be shown again.[/red]")
            console.print()
            for i, word in enumerate(words, 1):
                console.print(f"  {i:2d}. {word}")
            console.print()

            # Confirmation challenge
            indices, expected_words = pick_challenge_words(phrase, count=3)
            console.print("[bold]Confirm your recovery phrase:[/bold]")
            for idx, expected in zip(indices, expected_words):
                answer = typer.prompt(f"  Word #{idx + 1}")
                if answer.strip().lower() != expected:
                    console.print(f"[red]Incorrect. Expected word #{idx + 1} to be '{expected}'.[/red]")
                    console.print("[red]Vault created but please write down your recovery phrase carefully.[/red]")
                    break
            else:
                console.print("[green]Recovery phrase confirmed![/green]")

            console.print(f"[green]Vault initialized at {vault_dir}[/green]")

    except FileExistsError:
        console.print("[red]Vault already exists.[/red]")
        raise typer.Exit(code=1)


@app.command()
def recover():
    """Recover vault access with your recovery phrase. Must be run interactively by a human."""
    _require_tty()
    from phantomkey.vault.recovery import PhraseRecovery, KeyRecovery

    vault_dir = _get_vault_dir()
    vault = Vault(vault_dir)

    if not (vault_dir / "vault.pk").exists():
        console.print("[red]No vault found. Run 'phantomkey init' first.[/red]")
        raise typer.Exit(code=1)

    # Detect recovery strategy from vault file
    import json
    raw = json.loads((vault_dir / "vault.pk").read_text())
    strategy_id = raw.get("recovery_strategy")

    if not strategy_id:
        console.print("[red]This vault was created without a recovery phrase.[/red]")
        raise typer.Exit(code=1)

    strategies = {"phrase": PhraseRecovery, "key": KeyRecovery}
    strategy_cls = strategies.get(strategy_id)
    if not strategy_cls:
        console.print(f"[red]Unknown recovery strategy: {strategy_id}[/red]")
        raise typer.Exit(code=1)

    strategy = strategy_cls()
    console.print(f"This vault uses a {strategy.display_name()} for recovery.")

    recovery_input = typer.prompt(f"Enter your {strategy.display_name()}")
    new_password = typer.prompt("New master password", hide_input=True)
    confirm_password = typer.prompt("Confirm new master password", hide_input=True)

    if new_password != confirm_password:
        console.print("[red]Passwords do not match.[/red]")
        raise typer.Exit(code=1)

    try:
        vault.recover(recovery_input, new_password.encode(), strategy)
        console.print("[green]Vault recovered! Master password has been reset.[/green]")
    except Exception as e:
        console.print(f"[red]Recovery failed: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def status():
    """Show vault status."""
    try:
        vault = _get_vault()
        creds = vault.list()
        console.print(f"Vault: [green]unlocked[/green]")
        console.print(f"Credentials: {len(creds)}")
        console.print(f"Sequence: {vault.sequence}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def add(
    name: str,
    field: Annotated[list[str], typer.Option("--field", help="key=value pair")] = [],
    type: Annotated[str, typer.Option("--type", help="Credential type")] = "generic",
    service: Annotated[Optional[str], typer.Option("--service")] = None,
    tag: Annotated[list[str], typer.Option("--tag", help="Tag")] = [],
):
    """Add a new credential to the vault."""
    vault = _get_vault()
    fields = {}
    for f in field:
        if "=" not in f:
            console.print(f"[red]Invalid field format: {f}. Use key=value.[/red]")
            raise typer.Exit(code=1)
        k, v = f.split("=", 1)
        fields[k] = v

    try:
        cred_type = CredentialType(type)
    except ValueError:
        console.print(f"[red]Invalid type: {type}[/red]")
        raise typer.Exit(code=1)

    try:
        vault.add(name, fields=fields, credential_type=cred_type, service=service, tags=tag)
        console.print(f"[green]Added credential: {name}[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def get(name: str):
    """Get credential metadata (never shows secret values)."""
    vault = _get_vault()
    try:
        cred = vault.get(name)
        table = Table(title=f"Credential: {cred.name}")
        table.add_column("Property", style="bold")
        table.add_column("Value")
        table.add_row("Name", cred.name)
        table.add_row("Type", cred.credential_type.value)
        table.add_row("Service", cred.service or "—")
        table.add_row("Tags", ", ".join(cred.tags) if cred.tags else "—")
        table.add_row("Fields", ", ".join(cred.fields.keys()))
        table.add_row("Created", str(cred.created_at))
        table.add_row("Updated", str(cred.updated_at))
        console.print(table)
    except KeyError:
        console.print(f"[red]Credential '{name}' not found.[/red]")
        raise typer.Exit(code=1)


@app.command("list")
def list_creds(
    tag: Annotated[Optional[str], typer.Option("--tag")] = None,
    service: Annotated[Optional[str], typer.Option("--service")] = None,
):
    """List all credentials (metadata only)."""
    vault = _get_vault()
    creds = vault.list(tag=tag, service=service)
    if not creds:
        console.print("No credentials found.")
        return

    table = Table(title="Credentials")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Service")
    table.add_column("Tags")
    table.add_column("Fields")
    for c in creds:
        table.add_row(
            c.name,
            c.credential_type.value,
            c.service or "—",
            ", ".join(c.tags) if c.tags else "—",
            ", ".join(c.fields.keys()),
        )
    console.print(table)


@app.command()
def rm(name: str):
    """Delete a credential."""
    vault = _get_vault()
    try:
        vault.delete(name)
        console.print(f"[green]Deleted credential: {name}[/green]")
    except KeyError:
        console.print(f"[red]Credential '{name}' not found.[/red]")
        raise typer.Exit(code=1)


@app.command()
def update(
    name: str,
    field: Annotated[list[str], typer.Option("--field", help="key=value pair")] = [],
):
    """Update fields on an existing credential."""
    vault = _get_vault()
    fields = {}
    for f in field:
        if "=" not in f:
            console.print(f"[red]Invalid field format: {f}. Use key=value.[/red]")
            raise typer.Exit(code=1)
        k, v = f.split("=", 1)
        fields[k] = v

    try:
        vault.update(name, fields=fields)
        console.print(f"[green]Updated credential: {name}[/green]")
    except KeyError:
        console.print(f"[red]Credential '{name}' not found.[/red]")
        raise typer.Exit(code=1)


@app.command("exec-http")
def exec_http(
    url: Annotated[str, typer.Option("--url", help="URL (may contain {{placeholders}})")],
    method: Annotated[str, typer.Option("--method")] = "GET",
    header: Annotated[list[str], typer.Option("--header", help="Header as 'Name: Value'")] = [],
    body: Annotated[Optional[str], typer.Option("--body")] = None,
    timeout: Annotated[int, typer.Option("--timeout")] = 30,
):
    """Execute an HTTP request with blind credential injection."""
    from phantomkey.executor.http import execute_http

    vault = _get_vault()
    headers = {}
    for h in header:
        if ": " not in h:
            console.print(f"[red]Invalid header: {h}. Use 'Name: Value'.[/red]")
            raise typer.Exit(code=1)
        k, v = h.split(": ", 1)
        headers[k] = v

    try:
        result = execute_http(
            vault=vault,
            url=url,
            method=method,
            headers=headers or None,
            body=body,
            timeout=timeout,
        )
        console.print(f"Status: {result['status_code']}")
        console.print(result["body"])
    except KeyError as e:
        console.print(f"[red]Credential error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Request failed: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()