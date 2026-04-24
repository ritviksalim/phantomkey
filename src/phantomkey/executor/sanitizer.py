# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Response sanitizer — strip secrets from output before returning to agents."""

from urllib.parse import quote


def sanitize(text: str, secrets: dict[str, str]) -> str:
    """Replace any occurrence of secret values in text with [REDACTED:key].

    Checks exact match and URL-encoded variants.
    Processes longer secrets first to avoid partial replacements.
    """
    if not secrets:
        return text

    # Sort by value length descending so longer secrets are replaced first
    sorted_secrets = sorted(secrets.items(), key=lambda kv: len(kv[1]), reverse=True)

    for key, value in sorted_secrets:
        if not value:
            continue
        # Replace URL-encoded variant first (it's longer, avoids partial match issues)
        url_encoded = quote(value, safe="")
        if url_encoded != value:
            text = text.replace(url_encoded, f"[REDACTED:{key}]")
        # Replace exact match
        text = text.replace(value, f"[REDACTED:{key}]")

    return text