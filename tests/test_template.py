# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Tests for phantomkey.executor.template — written BEFORE implementation (TDD)."""

import pytest
from pathlib import Path
from phantomkey.vault.store import Vault


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path / ".phantomkey")
    v.init(b"pw")
    v.add("stripe", fields={"secret_key": "sk_live_abc123", "public_key": "pk_live_xyz"})
    v.add("github", fields={"token": "ghp_secrettoken789"}, service="github.com")
    v.add("db-prod", fields={"username": "admin", "password": "p@ss!word&special"})
    return v


class TestFindPlaceholders:
    def test_single_placeholder(self):
        from phantomkey.executor.template import find_placeholders

        result = find_placeholders("Bearer {{stripe.secret_key}}")
        assert result == [("stripe", "secret_key")]

    def test_multiple_placeholders(self):
        from phantomkey.executor.template import find_placeholders

        text = "{{db-prod.username}}:{{db-prod.password}}@host"
        result = find_placeholders(text)
        assert ("db-prod", "username") in result
        assert ("db-prod", "password") in result
        assert len(result) == 2

    def test_no_placeholders(self):
        from phantomkey.executor.template import find_placeholders

        result = find_placeholders("no placeholders here")
        assert result == []

    def test_placeholder_with_hyphens(self):
        from phantomkey.executor.template import find_placeholders

        result = find_placeholders("{{my-api-key.token}}")
        assert result == [("my-api-key", "token")]

    def test_placeholder_with_underscores(self):
        from phantomkey.executor.template import find_placeholders

        result = find_placeholders("{{my_api.secret_key}}")
        assert result == [("my_api", "secret_key")]


class TestResolveTemplate:
    def test_resolve_single(self, vault):
        from phantomkey.executor.template import resolve_template

        resolved, secrets = resolve_template("Bearer {{stripe.secret_key}}", vault)
        assert resolved == "Bearer sk_live_abc123"
        assert secrets == {"stripe.secret_key": "sk_live_abc123"}

    def test_resolve_multiple(self, vault):
        from phantomkey.executor.template import resolve_template

        template = "{{db-prod.username}}:{{db-prod.password}}@host"
        resolved, secrets = resolve_template(template, vault)
        assert resolved == "admin:p@ss!word&special@host"
        assert len(secrets) == 2

    def test_resolve_no_placeholders(self, vault):
        from phantomkey.executor.template import resolve_template

        resolved, secrets = resolve_template("plain text", vault)
        assert resolved == "plain text"
        assert secrets == {}

    def test_resolve_missing_credential_raises(self, vault):
        from phantomkey.executor.template import resolve_template

        with pytest.raises(KeyError, match="nonexistent"):
            resolve_template("{{nonexistent.field}}", vault)

    def test_resolve_missing_field_raises(self, vault):
        from phantomkey.executor.template import resolve_template

        with pytest.raises(KeyError, match="nonexistent_field"):
            resolve_template("{{stripe.nonexistent_field}}", vault)

    def test_resolve_across_credentials(self, vault):
        from phantomkey.executor.template import resolve_template

        template = "stripe={{stripe.secret_key}} github={{github.token}}"
        resolved, secrets = resolve_template(template, vault)
        assert "sk_live_abc123" in resolved
        assert "ghp_secrettoken789" in resolved
        assert len(secrets) == 2