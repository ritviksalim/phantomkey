# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.executor.browser — written BEFORE implementation (TDD)."""

import pytest

from phantomkey.vault.store import Vault

SECRET = "s3cr3t-PaSsW0rd"


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path / ".phantomkey")
    v.init(b"pw")
    v.add("brassring", fields={"email": "ritvik@example.com", "password": SECRET})
    return v


class FakeBrowserDriver:
    """Records every call so tests can assert what the real browser received."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._page_text: dict[str, str] = {}

    def set_page_text(self, selector: str, text: str) -> None:
        self._page_text[selector] = text

    def navigate(self, url: str) -> None:
        self.calls.append(("navigate", url))

    def fill(self, selector: str, value: str) -> None:
        self.calls.append(("fill", selector, value))

    def click(self, selector: str) -> None:
        self.calls.append(("click", selector))

    def text_content(self, selector: str) -> str:
        self.calls.append(("text_content", selector))
        return self._page_text.get(selector, "")


class TestExecuteBrowser:
    def test_fill_passes_resolved_secret_to_driver(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "fill", "selector": "#password", "value": "{{brassring.password}}"}]
        execute_browser(vault, actions, driver)
        # The REAL browser must receive the REAL secret value.
        assert ("fill", "#password", SECRET) in driver.calls

    def test_result_never_contains_resolved_secret(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "fill", "selector": "#password", "value": "{{brassring.password}}"}]
        result = execute_browser(vault, actions, driver)
        # The LLM-facing result must NOT contain the plaintext secret.
        assert SECRET not in repr(result)

    def test_result_echoes_placeholder_not_value(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "fill", "selector": "#password", "value": "{{brassring.password}}"}]
        result = execute_browser(vault, actions, driver)
        assert "{{brassring.password}}" in repr(result)

    def test_navigate_resolves_placeholders(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "navigate", "url": "https://x.example.com/u/{{brassring.email}}"}]
        execute_browser(vault, actions, driver)
        assert ("navigate", "https://x.example.com/u/ritvik@example.com") in driver.calls

    def test_click_needs_no_secret(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "click", "selector": "#submit"}]
        execute_browser(vault, actions, driver)
        assert ("click", "#submit") in driver.calls

    def test_read_action_is_sanitized(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        # A hostile page echoes the secret back into the DOM.
        driver.set_page_text("#msg", f"Welcome — your password {SECRET} is set")
        actions = [
            {"action": "fill", "selector": "#password", "value": "{{brassring.password}}"},
            {"action": "read", "selector": "#msg"},
        ]
        result = execute_browser(vault, actions, driver)
        assert SECRET not in repr(result)
        assert "[REDACTED:brassring.password]" in repr(result)

    def test_multi_step_registration_sequence(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [
            {"action": "navigate", "url": "https://signup.example.com"},
            {"action": "fill", "selector": "#email", "value": "{{brassring.email}}"},
            {"action": "fill", "selector": "#password", "value": "{{brassring.password}}"},
            {"action": "click", "selector": "#create"},
        ]
        execute_browser(vault, actions, driver)
        assert len(driver.calls) == 4
        assert ("fill", "#password", SECRET) in driver.calls
        assert ("click", "#create") in driver.calls

    def test_missing_credential_raises(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "fill", "selector": "#x", "value": "{{ghost.token}}"}]
        with pytest.raises(KeyError, match="ghost"):
            execute_browser(vault, actions, driver)

    def test_unknown_action_raises(self, vault):
        from phantomkey.executor.browser import execute_browser

        driver = FakeBrowserDriver()
        actions = [{"action": "teleport", "selector": "#x"}]
        with pytest.raises(ValueError, match="teleport"):
            execute_browser(vault, actions, driver)
