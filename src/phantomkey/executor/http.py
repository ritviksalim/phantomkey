# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""HTTP request executor — executes templated requests with injected credentials."""

from typing import Any, Optional

import httpx

from phantomkey.executor.sanitizer import sanitize
from phantomkey.executor.template import resolve_template
from phantomkey.vault.store import Vault


def execute_http(
    vault: Vault,
    url: str,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    body: Optional[str] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute an HTTP request with credential placeholders resolved.

    All {{cred.field}} placeholders in url, headers, and body are resolved
    from the vault. The response is sanitized to remove any echoed secrets.

    Returns:
        Dict with status_code, headers, and sanitized body.
    """
    all_secrets: dict[str, str] = {}

    # Resolve placeholders in URL
    resolved_url, url_secrets = resolve_template(url, vault)
    all_secrets.update(url_secrets)

    # Resolve placeholders in headers
    resolved_headers: dict[str, str] = {}
    if headers:
        for k, v in headers.items():
            resolved_v, h_secrets = resolve_template(v, vault)
            resolved_headers[k] = resolved_v
            all_secrets.update(h_secrets)

    # Resolve placeholders in body
    resolved_body: Optional[str] = None
    if body:
        resolved_body, body_secrets = resolve_template(body, vault)
        all_secrets.update(body_secrets)

    # Execute the request
    response = httpx.request(
        method=method,
        url=resolved_url,
        headers=resolved_headers or None,
        content=resolved_body.encode() if resolved_body else None,
        timeout=timeout,
    )

    # Sanitize the response
    sanitized_body = sanitize(response.text, all_secrets)
    sanitized_headers = {
        k: sanitize(v, all_secrets) for k, v in response.headers.items()
    }

    return {
        "status_code": response.status_code,
        "headers": sanitized_headers,
        "body": sanitized_body,
    }