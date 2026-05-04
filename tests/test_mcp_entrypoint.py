# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Tests for phantomkey.mcp.__main__ — the stdio runner entry point.

Written BEFORE implementation (TDD).

The runner is a thin glue layer:
  1. Build the server with create_server() (env-driven config).
  2. Open the MCP stdio_server context.
  3. Run the server against the read/write streams from stdio.

These tests verify the glue without spinning up a real subprocess. The
underlying server logic is already covered in test_mcp.py.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


def test_main_module_exposes_main_callable():
    """The package script entry point is `phantomkey.mcp.__main__:main`."""
    from phantomkey.mcp import __main__ as runner

    assert callable(runner.main)


def test_main_module_exposes_async_main_coroutine():
    """Internal coroutine that does the actual stdio wiring."""
    from phantomkey.mcp import __main__ as runner

    assert asyncio.iscoroutinefunction(runner._async_main)


def test_main_invokes_asyncio_run_with_async_main(tmp_path, monkeypatch):
    """main() should hand off to asyncio.run() with the _async_main coroutine."""
    from phantomkey.mcp import __main__ as runner

    monkeypatch.setenv("PHANTOMKEY_VAULT_DIR", str(tmp_path / "no-such-vault"))
    monkeypatch.setenv("PHANTOMKEY_MASTER_KEY", "irrelevant")

    captured = {}

    def fake_run(coro):
        captured["coro_name"] = coro.__qualname__
        coro.close()  # don't actually run it

    monkeypatch.setattr(asyncio, "run", fake_run)

    runner.main()

    assert captured["coro_name"].endswith("_async_main")


@pytest.mark.asyncio
async def test_async_main_wires_create_server_to_stdio_server(tmp_path, monkeypatch):
    """_async_main() creates the server, opens stdio, and runs the server."""
    from phantomkey.mcp import __main__ as runner

    fake_server = AsyncMock()
    fake_server.run = AsyncMock()
    fake_server.create_initialization_options = lambda: {"sentinel": "init-opts"}

    fake_streams = (object(), object())

    class _FakeStdioCtx:
        async def __aenter__(self):
            return fake_streams

        async def __aexit__(self, *a):
            return None

    create_server_calls = []

    def fake_create_server():
        create_server_calls.append(True)
        return fake_server

    with patch.object(runner, "create_server", fake_create_server), patch.object(
        runner, "stdio_server", lambda: _FakeStdioCtx()
    ):
        await runner._async_main()

    assert create_server_calls == [True]
    fake_server.run.assert_awaited_once()
    args, _ = fake_server.run.call_args
    # Server.run signature: (read_stream, write_stream, initialization_options)
    assert args[0] is fake_streams[0]
    assert args[1] is fake_streams[1]
    assert args[2] == {"sentinel": "init-opts"}
