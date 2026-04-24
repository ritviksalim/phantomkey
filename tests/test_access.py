# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""Tests for phantomkey.auth.access — written BEFORE implementation (TDD)."""

import pytest
from pathlib import Path


@pytest.fixture
def vault(tmp_path):
    from phantomkey.vault.store import Vault

    v = Vault(tmp_path / ".phantomkey")
    v.init(b"pw")
    return v


class TestAccessControl:
    def test_unrestricted_credential_allows_any_agent(self, vault):
        from phantomkey.auth.access import check_access

        vault.add("open-cred", fields={"key": "val"}, access_policy=None)
        cred = vault.get("open-cred")
        assert check_access(cred, agent_id="any-agent") is True
        assert check_access(cred, agent_id=None) is True

    def test_restricted_credential_allows_listed_agent(self, vault):
        from phantomkey.auth.access import check_access

        vault.add("restricted", fields={"key": "val"}, access_policy=["claude-code", "my-bot"])
        cred = vault.get("restricted")
        assert check_access(cred, agent_id="claude-code") is True
        assert check_access(cred, agent_id="my-bot") is True

    def test_restricted_credential_denies_unlisted_agent(self, vault):
        from phantomkey.auth.access import check_access

        vault.add("restricted", fields={"key": "val"}, access_policy=["claude-code"])
        cred = vault.get("restricted")
        assert check_access(cred, agent_id="other-agent") is False

    def test_restricted_credential_denies_anonymous(self, vault):
        from phantomkey.auth.access import check_access

        vault.add("restricted", fields={"key": "val"}, access_policy=["claude-code"])
        cred = vault.get("restricted")
        assert check_access(cred, agent_id=None) is False

    def test_empty_access_policy_denies_all(self, vault):
        from phantomkey.auth.access import check_access

        vault.add("locked-down", fields={"key": "val"}, access_policy=[])
        cred = vault.get("locked-down")
        assert check_access(cred, agent_id="claude-code") is False