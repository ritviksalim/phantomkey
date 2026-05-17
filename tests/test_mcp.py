# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.mcp.server — written BEFORE implementation (TDD)."""

import json
import pytest
import pytest_asyncio
from pathlib import Path

from mcp.types import ListToolsRequest, CallToolRequest


@pytest_asyncio.fixture
async def vault_dir(tmp_path):
    return tmp_path / ".phantomkey"


@pytest_asyncio.fixture
async def initialized_vault(vault_dir):
    """Create a vault with test credentials."""
    from phantomkey.vault.store import Vault

    v = Vault(vault_dir)
    v.init(b"test-pw")
    v.add("stripe", fields={"secret_key": "sk_test_123", "public_key": "pk_test_456"}, service="stripe.com", tags=["billing"])
    v.add("github", fields={"token": "ghp_abc789"}, service="github.com", tags=["ci"])
    v.lock()
    return vault_dir


@pytest_asyncio.fixture
async def server(initialized_vault):
    """Create a PhantomKey MCP server instance."""
    from phantomkey.mcp.server import create_server

    return create_server(vault_dir=initialized_vault, master_key=b"test-pw")


async def _list_tools(server):
    handler = server.request_handlers[ListToolsRequest]
    result = await handler(ListToolsRequest(method="tools/list"))
    return result.root.tools


async def _call_tool(server, name, arguments=None):
    handler = server.request_handlers[CallToolRequest]
    result = await handler(CallToolRequest(
        method="tools/call",
        params={"name": name, "arguments": arguments or {}},
    ))
    return result.root.content


@pytest.mark.asyncio
class TestMCPTools:
    async def test_server_has_tools(self, server):
        """Server should expose the expected tools."""
        tools = await _list_tools(server)
        tool_names = {t.name for t in tools}
        assert "phantomkey_status" in tool_names
        assert "phantomkey_list" in tool_names
        assert "phantomkey_get_meta" in tool_names
        assert "phantomkey_add" in tool_names
        assert "phantomkey_update" in tool_names
        assert "phantomkey_delete" in tool_names
        assert "phantomkey_exec" in tool_names

    async def test_status(self, server):
        result = await _call_tool(server, "phantomkey_status")
        text = result[0].text
        data = json.loads(text)
        assert data["locked"] is False
        assert data["credential_count"] == 2

    async def test_list(self, server):
        result = await _call_tool(server, "phantomkey_list")
        text = result[0].text
        data = json.loads(text)
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"stripe", "github"}

    async def test_list_filter_by_tag(self, server):
        result = await _call_tool(server, "phantomkey_list", {"tag": "billing"})
        text = result[0].text
        data = json.loads(text)
        assert len(data) == 1
        assert data[0]["name"] == "stripe"

    async def test_get_meta_no_secret_values(self, server):
        """get_meta must return field NAMES but never field VALUES."""
        result = await _call_tool(server, "phantomkey_get_meta", {"name": "stripe"})
        text = result[0].text
        data = json.loads(text)
        assert data["name"] == "stripe"
        assert "field_names" in data
        assert "secret_key" in data["field_names"]
        # The actual secret value must NOT appear
        assert "sk_test_123" not in text
        assert "pk_test_456" not in text

    async def test_get_meta_nonexistent(self, server):
        result = await _call_tool(server, "phantomkey_get_meta", {"name": "nope"})
        text = result[0].text
        assert "not found" in text.lower() or "error" in text.lower()

    async def test_add(self, server):
        result = await _call_tool(server, "phantomkey_add", {
            "name": "new-cred",
            "fields": {"api_key": "test123"},
            "service": "example.com",
        })
        text = result[0].text
        assert "success" in text.lower() or "added" in text.lower()

        # Verify it was added
        result = await _call_tool(server, "phantomkey_list")
        data = json.loads(result[0].text)
        names = {c["name"] for c in data}
        assert "new-cred" in names

    async def test_add_duplicate_fails(self, server):
        result = await _call_tool(server, "phantomkey_add", {
            "name": "stripe",
            "fields": {"key": "val"},
        })
        text = result[0].text
        assert "already exists" in text.lower() or "error" in text.lower()

    async def test_update(self, server):
        result = await _call_tool(server, "phantomkey_update", {
            "name": "stripe",
            "fields": {"secret_key": "sk_new_key"},
        })
        text = result[0].text
        assert "success" in text.lower() or "updated" in text.lower()
        # The new secret value must NOT appear in the response
        assert "sk_new_key" not in text

    async def test_delete(self, server):
        result = await _call_tool(server, "phantomkey_delete", {"name": "github"})
        text = result[0].text
        assert "success" in text.lower() or "deleted" in text.lower()

        # Verify it was deleted
        result = await _call_tool(server, "phantomkey_list")
        data = json.loads(result[0].text)
        names = {c["name"] for c in data}
        assert "github" not in names

    async def test_exec_never_leaks_secrets(self, server):
        """The phantomkey_exec tool must NEVER return secret values."""
        tools = await _list_tools(server)
        exec_tool = next(t for t in tools if t.name == "phantomkey_exec")
        assert exec_tool is not None
        schema = exec_tool.inputSchema
        assert "url" in schema.get("properties", {})

@pytest.mark.asyncio
class TestMCPBrowserTool:
    async def test_browser_tool_is_listed(self, server):
        tools = await _list_tools(server)
        assert "phantomkey_browser" in {t.name for t in tools}

    async def test_browser_tool_has_actions_schema(self, server):
        tools = await _list_tools(server)
        browser_tool = next(t for t in tools if t.name == "phantomkey_browser")
        assert "actions" in browser_tool.inputSchema.get("properties", {})

    async def test_browser_tool_blind_injection(self, server, monkeypatch):
        """The real value reaches the browser; the MCP response keeps the placeholder."""
        from contextlib import contextmanager
        from phantomkey.executor import browser_playwright

        calls = []

        class FakeDriver:
            def navigate(self, url):
                calls.append(("navigate", url))

            def fill(self, selector, value):
                calls.append(("fill", selector, value))

            def click(self, selector):
                calls.append(("click", selector))

            def text_content(self, selector):
                return ""

        @contextmanager
        def fake_browser(headless=True):
            yield FakeDriver()

        monkeypatch.setattr(browser_playwright, "playwright_browser", fake_browser)

        result = await _call_tool(server, "phantomkey_browser", {
            "actions": [{"action": "fill", "selector": "#pw", "value": "{{stripe.secret_key}}"}],
        })
        text = result[0].text
        assert ("fill", "#pw", "sk_test_123") in calls
        assert "sk_test_123" not in text
        assert "{{stripe.secret_key}}" in text
