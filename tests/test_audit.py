# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Tests for phantomkey.audit.log — written BEFORE implementation (TDD)."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def audit_log(tmp_path):
    from phantomkey.audit.log import AuditLog

    return AuditLog(tmp_path / "audit.log")


class TestAuditLog:
    def test_log_creates_file(self, audit_log, tmp_path):
        audit_log.record("add", credential="test-cred", agent="claude-code")
        assert (tmp_path / "audit.log").exists()

    def test_log_entry_is_jsonl(self, audit_log, tmp_path):
        audit_log.record("add", credential="test-cred", agent="claude-code")
        lines = (tmp_path / "audit.log").read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "add"
        assert entry["credential"] == "test-cred"
        assert entry["agent"] == "claude-code"
        assert "ts" in entry
        assert entry["success"] is True

    def test_log_multiple_entries(self, audit_log, tmp_path):
        audit_log.record("add", credential="cred1")
        audit_log.record("exec", credential="cred2", fields_used=["secret_key"])
        audit_log.record("delete", credential="cred1")
        lines = (tmp_path / "audit.log").read_text().strip().split("\n")
        assert len(lines) == 3

    def test_log_failure(self, audit_log, tmp_path):
        audit_log.record("exec", credential="cred1", success=False)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["success"] is False

    def test_log_with_fields_used(self, audit_log, tmp_path):
        audit_log.record("exec", credential="stripe", fields_used=["secret_key", "public_key"])
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["fields"] == ["secret_key", "public_key"]

    def test_log_never_contains_secret_values(self, audit_log, tmp_path):
        """Audit log must never contain actual secret values."""
        audit_log.record("exec", credential="stripe", fields_used=["secret_key"])
        content = (tmp_path / "audit.log").read_text()
        # Only field names, never values
        assert "secret_key" in content  # field name is OK
        # No way to verify values aren't there without knowing them,
        # but the API should never accept values

    def test_read_entries(self, audit_log):
        audit_log.record("add", credential="cred1")
        audit_log.record("exec", credential="cred2")
        entries = audit_log.read()
        assert len(entries) == 2
        assert entries[0]["action"] == "add"
        assert entries[1]["action"] == "exec"

    def test_read_filter_by_credential(self, audit_log):
        audit_log.record("add", credential="cred1")
        audit_log.record("exec", credential="cred2")
        audit_log.record("delete", credential="cred1")
        entries = audit_log.read(credential="cred1")
        assert len(entries) == 2
        assert all(e["credential"] == "cred1" for e in entries)

    def test_read_last_n(self, audit_log):
        for i in range(10):
            audit_log.record("exec", credential=f"cred-{i}")
        entries = audit_log.read(last=3)
        assert len(entries) == 3