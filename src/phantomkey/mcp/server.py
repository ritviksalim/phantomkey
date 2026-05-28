# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""PhantomKey MCP Server — exposes vault tools to AI agents."""

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from mcp.server import Server
from mcp.types import TextContent, Tool

from phantomkey.executor.http import execute_http
from phantomkey.executor.sanitizer import sanitize
from phantomkey.executor.template import resolve_template
from phantomkey.vault.store import Vault


def create_server(
    vault_dir: Optional[Path] = None,
    master_key: Optional[bytes] = None,
) -> Server:
    """Create and configure a PhantomKey MCP server.

    Args:
        vault_dir: Path to vault directory. Defaults to ~/.phantomkey.
        master_key: Master password bytes. If None, reads PHANTOMKEY_MASTER_KEY env var.
    """
    import os

    if vault_dir is None:
        vault_dir = Path(os.environ.get("PHANTOMKEY_VAULT_DIR", Path.home() / ".phantomkey"))
    if master_key is None:
        key_str = os.environ.get("PHANTOMKEY_MASTER_KEY", "")
        master_key = key_str.encode()

    vault = Vault(vault_dir)
    vault.unlock(master_key)

    server = Server("phantomkey")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="phantomkey_status",
                description="Check vault status (locked/unlocked, credential count).",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="phantomkey_list",
                description="List stored credentials (metadata only, never secret values).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string", "description": "Filter by tag"},
                        "service": {"type": "string", "description": "Filter by service"},
                    },
                },
            ),
            Tool(
                name="phantomkey_get_meta",
                description="Get metadata for a credential (field names only, never values).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Credential name"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="phantomkey_add",
                description="Store a new credential in the vault.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Credential name"},
                        "fields": {"type": "object", "description": "Key-value pairs of credential fields"},
                        "type": {"type": "string", "description": "Credential type (generic, api_key, password, etc.)"},
                        "service": {"type": "string", "description": "Service name (e.g. github.com)"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    },
                    "required": ["name", "fields"],
                },
            ),
            Tool(
                name="phantomkey_update",
                description="Update fields on an existing credential.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Credential name"},
                        "fields": {"type": "object", "description": "Fields to update (merged with existing)"},
                    },
                    "required": ["name", "fields"],
                },
            ),
            Tool(
                name="phantomkey_delete",
                description="Delete a credential from the vault.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Credential name"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="phantomkey_exec",
                description="Execute an HTTP request with blind credential injection. Placeholders like {{cred.field}} are resolved from the vault. The response is sanitized — secrets are never returned.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL (may contain {{cred.field}} placeholders)"},
                        "method": {"type": "string", "description": "HTTP method", "default": "GET"},
                        "headers": {"type": "object", "description": "Headers (values may contain placeholders)"},
                        "body": {"type": "string", "description": "Request body (may contain placeholders)"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="phantomkey_browser",
                description=(
                    "Drive a browser through a sequence of actions with blind credential "
                    "injection. Each action is an object: "
                    '{"action": "navigate"|"fill"|"click"|"read", ...}. {{cred.field}} '
                    "placeholders in navigate URLs and fill values are resolved from the "
                    "vault — the real value reaches the browser, never this response. "
                    "Requires the optional 'browser' extra."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "description": "Ordered browser actions; fill/navigate values may contain {{cred.field}} placeholders.",
                            "items": {"type": "object"},
                        },
                        "headless": {"type": "boolean", "description": "Run the browser headless", "default": True},
                    },
                    "required": ["actions"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
        try:
            if name == "phantomkey_status":
                return _handle_status()
            elif name == "phantomkey_list":
                return _handle_list(arguments)
            elif name == "phantomkey_get_meta":
                return _handle_get_meta(arguments)
            elif name == "phantomkey_add":
                return _handle_add(arguments)
            elif name == "phantomkey_update":
                return _handle_update(arguments)
            elif name == "phantomkey_delete":
                return _handle_delete(arguments)
            elif name == "phantomkey_exec":
                return _handle_exec(arguments)
            elif name == "phantomkey_browser":
                return _handle_browser(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _handle_status() -> list[TextContent]:
        creds = vault.list()
        data = {
            "locked": not vault.is_unlocked,
            "credential_count": len(creds),
            "sequence": vault.sequence,
        }
        return [TextContent(type="text", text=json.dumps(data))]

    def _handle_list(args: dict) -> list[TextContent]:
        creds = vault.list(tag=args.get("tag"), service=args.get("service"))
        data = [
            {
                "name": c.name,
                "type": c.credential_type.value,
                "service": c.service,
                "tags": c.tags,
                "field_names": list(c.fields.keys()),
            }
            for c in creds
        ]
        return [TextContent(type="text", text=json.dumps(data))]

    def _handle_get_meta(args: dict) -> list[TextContent]:
        name = args["name"]
        try:
            cred = vault.get(name)
            data = {
                "name": cred.name,
                "type": cred.credential_type.value,
                "service": cred.service,
                "tags": cred.tags,
                "field_names": list(cred.fields.keys()),
                "created_at": str(cred.created_at),
                "updated_at": str(cred.updated_at),
            }
            return [TextContent(type="text", text=json.dumps(data))]
        except KeyError:
            return [TextContent(type="text", text=json.dumps({"error": f"Credential '{name}' not found"}))]

    def _handle_add(args: dict) -> list[TextContent]:
        from phantomkey.vault.models import CredentialType

        name = args["name"]
        fields = args["fields"]
        cred_type = CredentialType(args.get("type", "generic"))
        service = args.get("service")
        tags = args.get("tags", [])
        try:
            vault.add(name, fields=fields, credential_type=cred_type, service=service, tags=tags)
            return [TextContent(type="text", text=json.dumps({"success": True, "message": f"Added credential: {name}"}))]
        except ValueError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _handle_update(args: dict) -> list[TextContent]:
        name = args["name"]
        fields = args["fields"]
        try:
            vault.update(name, fields=fields)
            return [TextContent(type="text", text=json.dumps({"success": True, "message": f"Updated credential: {name}"}))]
        except KeyError:
            return [TextContent(type="text", text=json.dumps({"error": f"Credential '{name}' not found"}))]

    def _handle_delete(args: dict) -> list[TextContent]:
        name = args["name"]
        try:
            vault.delete(name)
            return [TextContent(type="text", text=json.dumps({"success": True, "message": f"Deleted credential: {name}"}))]
        except KeyError:
            return [TextContent(type="text", text=json.dumps({"error": f"Credential '{name}' not found"}))]

    def _handle_exec(args: dict) -> list[TextContent]:
        result = execute_http(
            vault=vault,
            url=args["url"],
            method=args.get("method", "GET"),
            headers=args.get("headers"),
            body=args.get("body"),
            timeout=args.get("timeout", 30),
        )
        return [TextContent(type="text", text=json.dumps({
            "status_code": result["status_code"],
            "body": result["body"],
        }))]

    def _handle_browser(args: dict) -> list[TextContent]:
        from phantomkey.executor.browser import execute_browser
        from phantomkey.executor.browser_playwright import playwright_browser

        with playwright_browser(headless=args.get("headless", True)) as driver:
            result = execute_browser(vault, args["actions"], driver)
        return [TextContent(type="text", text=json.dumps(result))]

    return server