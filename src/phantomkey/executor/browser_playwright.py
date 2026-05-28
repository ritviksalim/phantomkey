# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Playwright-backed BrowserDriver for the browser executor.

This is the real driver used in production. It requires the optional
``browser`` extra so PhantomKey's core stays dependency-free:

    pip install 'phantomkey[browser]'
    playwright install chromium

The Playwright import is deferred until a browser is actually launched, so
this module imports cleanly even when the extra is not installed.
"""

from contextlib import contextmanager
from typing import Any, Iterator


class PlaywrightDriver:
    """BrowserDriver implementation backed by a Playwright Page.

    Satisfies the ``phantomkey.executor.browser.BrowserDriver`` protocol.
    """

    def __init__(self, page: Any):
        self._page = page

    def navigate(self, url: str) -> None:
        self._page.goto(url)

    def fill(self, selector: str, value: str) -> None:
        self._page.fill(selector, value)

    def click(self, selector: str) -> None:
        self._page.click(selector)

    def text_content(self, selector: str) -> str:
        return self._page.text_content(selector) or ""


def _import_sync_playwright() -> Any:
    """Import Playwright's sync API. Isolated so it can be patched in tests."""
    from playwright.sync_api import sync_playwright

    return sync_playwright


@contextmanager
def playwright_browser(headless: bool = True) -> Iterator[PlaywrightDriver]:
    """Launch a Chromium browser and yield a PlaywrightDriver.

    Requires the optional ``browser`` extra. Raises a clear, actionable
    RuntimeError if Playwright is not installed.
    """
    try:
        sync_playwright = _import_sync_playwright()
    except ImportError as exc:
        raise RuntimeError(
            "Browser automation requires the optional 'browser' extra. "
            "Install it with:  pip install 'phantomkey[browser]'  "
            "then:  playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            yield PlaywrightDriver(page)
        finally:
            browser.close()
