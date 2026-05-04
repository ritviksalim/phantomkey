# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Template engine — parse and resolve {{cred.field}} placeholders."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phantomkey.vault.store import Vault

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)\}\}")


def find_placeholders(text: str) -> list[tuple[str, str]]:
    """Find all {{credential.field}} placeholders in text.

    Returns list of (credential_name, field_name) tuples.
    """
    return PLACEHOLDER_RE.findall(text)


def resolve_template(template: str, vault: "Vault") -> tuple[str, dict[str, str]]:
    """Resolve all placeholders in a template string.

    Returns:
        (resolved_string, {placeholder_key: secret_value}) for sanitization.

    Raises:
        KeyError: If a credential or field is not found.
    """
    secrets_used: dict[str, str] = {}

    def replacer(match: re.Match) -> str:
        cred_name = match.group(1)
        field_name = match.group(2)
        value = vault.get_field(cred_name, field_name)
        secrets_used[f"{cred_name}.{field_name}"] = value
        return value

    resolved = PLACEHOLDER_RE.sub(replacer, template)
    return resolved, secrets_used