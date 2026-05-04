# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Per-agent access control for credentials."""

from typing import Optional

from phantomkey.vault.models import Credential


def check_access(credential: Credential, agent_id: Optional[str]) -> bool:
    """Check if an agent is allowed to access a credential.

    Args:
        credential: The credential to check access for.
        agent_id: The agent's identifier. None means anonymous.

    Returns:
        True if access is allowed, False otherwise.

    Rules:
        - If access_policy is None: unrestricted, any agent can access.
        - If access_policy is an empty list: no agent can access.
        - If access_policy is a non-empty list: only listed agent IDs can access.
    """
    if credential.access_policy is None:
        return True
    if agent_id is None:
        return False
    return agent_id in credential.access_policy