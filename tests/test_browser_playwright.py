# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.executor.browser_playwright — written BEFORE implementation (TDD).

These tests use a mocked Playwright Page; they never launch a real browser.
End-to-end browser testing requires `pip install 'phantomkey[browser]'` and
`playwright install chromium`.
"""

from unittest.mock import MagicMock

import pytest

from phantomkey.vault.store import Vault


class TestPlaywrightDriver:
    def test_navigate_calls_page_goto(self):
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        page = MagicMock()
        PlaywrightDriver(page).navigate("https://example.com")
        page.goto.assert_called_once_with("https://example.com")

    def test_fill_calls_page_fill(self):
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        page = MagicMock()
        PlaywrightDriver(page).fill("#password", "s3cret")
        page.fill.assert_called_once_with("#password", "s3cret")

    def test_click_calls_page_click(self):
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        page = MagicMock()
        PlaywrightDriver(page).click("#submit")
        page.click.assert_called_once_with("#submit")

    def test_text_content_returns_page_text(self):
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        page = MagicMock()
        page.text_content.return_value = "hello"
        assert PlaywrightDriver(page).text_content("#msg") == "hello"

    def test_text_content_empty_string_when_page_returns_none(self):
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        page = MagicMock()
        page.text_content.return_value = None
        assert PlaywrightDriver(page).text_content("#msg") == ""

    def test_driver_is_usable_by_execute_browser(self, tmp_path):
        # The driver must satisfy the BrowserDriver protocol that execute_browser
        # depends on — and blind injection must hold end-to-end.
        from phantomkey.executor.browser import execute_browser
        from phantomkey.executor.browser_playwright import PlaywrightDriver

        v = Vault(tmp_path / ".phantomkey")
        v.init(b"pw")
        v.add("site", fields={"password": "p@ssw0rd"})

        page = MagicMock()
        result = execute_browser(
            v,
            [{"action": "fill", "selector": "#p", "value": "{{site.password}}"}],
            PlaywrightDriver(page),
        )
        # real value reaches the page, placeholder stays in the result
        page.fill.assert_called_once_with("#p", "p@ssw0rd")
        assert "p@ssw0rd" not in repr(result)
        assert "{{site.password}}" in repr(result)


class TestPlaywrightBrowser:
    def test_missing_playwright_raises_helpful_error(self, monkeypatch):
        from phantomkey.executor import browser_playwright

        def boom():
            raise ImportError("playwright not installed")

        monkeypatch.setattr(browser_playwright, "_import_sync_playwright", boom)
        with pytest.raises(RuntimeError, match=r"phantomkey\[browser\]"):
            with browser_playwright.playwright_browser():
                pass
