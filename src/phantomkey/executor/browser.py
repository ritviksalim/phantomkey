# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Browser action executor — runs templated browser actions with blind injection.

The agent emits a list of browser actions containing {{cred.field}} placeholders.
This executor resolves placeholders against the vault and drives a BrowserDriver,
so the real credential value reaches the browser but never the agent's context.

PhantomKey core takes no hard browser dependency: the executor is written against
the BrowserDriver protocol. The real Playwright-backed driver ships separately as
an optional extra; tests use a fake driver.
"""

from typing import Any, Protocol

from phantomkey.executor.sanitizer import sanitize
from phantomkey.executor.template import resolve_template
from phantomkey.vault.store import Vault


class BrowserDriver(Protocol):
    """Minimal browser-driver interface the executor depends on."""

    def navigate(self, url: str) -> None: ...

    def fill(self, selector: str, value: str) -> None: ...

    def click(self, selector: str) -> None: ...

    def text_content(self, selector: str) -> str: ...


def execute_browser(
    vault: Vault,
    actions: list[dict[str, Any]],
    driver: BrowserDriver,
) -> dict[str, Any]:
    """Execute a sequence of browser actions with credential placeholders resolved.

    Each action is a dict with an ``action`` key. Supported actions:

      - ``{"action": "navigate", "url": ...}``  — ``url`` may contain placeholders
      - ``{"action": "fill", "selector": ..., "value": ...}`` — ``value`` may
        contain placeholders
      - ``{"action": "click", "selector": ...}``
      - ``{"action": "read", "selector": ...}`` — extracts text content, sanitized

    {{cred.field}} placeholders in ``url`` and ``value`` are resolved from the
    vault and passed to the driver. The returned result echoes the ORIGINAL
    actions (placeholders intact, never resolved) and sanitizes any extracted
    page text, so no plaintext secret reaches the caller.

    Raises:
        KeyError: a referenced credential or field is not in the vault.
        ValueError: an unknown action type.
    """
    all_secrets: dict[str, str] = {}
    extracted: dict[str, str] = {}

    for action in actions:
        kind = action.get("action")
        if kind == "navigate":
            resolved_url, secrets = resolve_template(action["url"], vault)
            all_secrets.update(secrets)
            driver.navigate(resolved_url)
        elif kind == "fill":
            resolved_value, secrets = resolve_template(action["value"], vault)
            all_secrets.update(secrets)
            driver.fill(action["selector"], resolved_value)
        elif kind == "click":
            driver.click(action["selector"])
        elif kind == "read":
            text = driver.text_content(action["selector"])
            extracted[action["selector"]] = sanitize(text, all_secrets)
        else:
            raise ValueError(f"Unknown browser action: {kind!r}")

    return {
        "actions_performed": len(actions),
        "actions": actions,
        "extracted": extracted,
    }
