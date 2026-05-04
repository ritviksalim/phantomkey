# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Tests for phantomkey.executor.sanitizer — written BEFORE implementation (TDD)."""

import pytest
from urllib.parse import quote


class TestSanitize:
    def test_redacts_exact_match(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {"stripe.key": "sk_live_abc123"}
        text = "Your key is sk_live_abc123, enjoy!"
        result = sanitize(text, secrets)
        assert "sk_live_abc123" not in result
        assert "[REDACTED:stripe.key]" in result

    def test_redacts_multiple_secrets(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {
            "db.user": "admin",
            "db.pass": "p@ssw0rd!",
        }
        text = "Connected as admin with password p@ssw0rd!"
        result = sanitize(text, secrets)
        assert "admin" not in result
        assert "p@ssw0rd!" not in result

    def test_redacts_url_encoded_variant(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {"db.pass": "p@ss!word&special"}
        url_encoded = quote("p@ss!word&special", safe="")
        text = f"param={url_encoded}"
        result = sanitize(text, secrets)
        assert url_encoded not in result
        assert "[REDACTED:db.pass]" in result

    def test_no_secrets_returns_unchanged(self):
        from phantomkey.executor.sanitizer import sanitize

        text = "nothing secret here"
        result = sanitize(text, {})
        assert result == text

    def test_no_match_returns_unchanged(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {"api.key": "sk_live_xyz"}
        text = "no secrets echoed here"
        result = sanitize(text, secrets)
        assert result == text

    def test_redacts_multiple_occurrences(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {"api.key": "sk_live_abc"}
        text = "key=sk_live_abc and again sk_live_abc"
        result = sanitize(text, secrets)
        assert "sk_live_abc" not in result
        assert result.count("[REDACTED:api.key]") == 2

    def test_redacts_in_json_response(self):
        from phantomkey.executor.sanitizer import sanitize

        secrets = {"stripe.key": "sk_test_123456"}
        text = '{"api_key": "sk_test_123456", "status": "ok"}'
        result = sanitize(text, secrets)
        assert "sk_test_123456" not in result

    def test_longer_secrets_redacted_first(self):
        """If one secret is a substring of another, longer should be redacted first."""
        from phantomkey.executor.sanitizer import sanitize

        secrets = {
            "short": "abc",
            "long": "abcdef",
        }
        text = "value is abcdef"
        result = sanitize(text, secrets)
        assert "[REDACTED:long]" in result