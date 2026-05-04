# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Fire-and-forget email registration webhook."""

import httpx


def send_registration(email: str, webhook_url: str) -> bool:
    """POST email to a webhook URL. Returns True on success, False on failure.

    This is fire-and-forget — failures are silently ignored so they
    never block vault initialization.
    """
    if not webhook_url:
        return False
    try:
        response = httpx.post(
            webhook_url,
            json={"email": email},
            timeout=5.0,
        )
        return response.is_success
    except Exception:
        return False