# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Stdio runner for the PhantomKey MCP server.

This is the entry point registered as the `phantomkey-mcp` script in
pyproject.toml. It is also runnable as `python -m phantomkey.mcp`.

Configuration is environment-driven (see phantomkey.mcp.server.create_server):
  - PHANTOMKEY_VAULT_DIR  — vault location (default ~/.phantomkey)
  - PHANTOMKEY_MASTER_KEY — master password (required to unlock the vault)
"""

import asyncio

from mcp.server.stdio import stdio_server

from phantomkey.mcp.server import create_server


async def _async_main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
