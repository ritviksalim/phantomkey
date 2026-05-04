# Copyright 2026 Ritvik Salim
# SPDX-License-Identifier: Apache-2.0

"""Tests for phantomkey CLI — written BEFORE implementation (TDD)."""

import json
import os
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def vault_dir(tmp_path):
    return tmp_path / ".phantomkey"


@pytest.fixture
def cli_env(vault_dir):
    """Set up environment for CLI tests."""
    return {
        "PHANTOMKEY_VAULT_DIR": str(vault_dir),
        "PHANTOMKEY_MASTER_KEY": "test-password",
    }


@pytest.fixture
def runner():
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def app():
    from phantomkey.cli import app

    return app


@pytest.fixture
def initialized_env(runner, app, cli_env):
    """Return cli_env after running init."""
    result = runner.invoke(app, ["init", "--no-recovery"], env=cli_env)
    assert result.exit_code == 0
    return cli_env


class TestInit:
    def test_init_creates_vault(self, runner, app, cli_env, vault_dir):
        result = runner.invoke(app, ["init", "--no-recovery"], env=cli_env)
        assert result.exit_code == 0
        assert (vault_dir / "vault.pk").exists()
        assert "initialized" in result.output.lower() or "created" in result.output.lower()

    def test_init_twice_fails(self, runner, app, cli_env):
        runner.invoke(app, ["init", "--no-recovery"], env=cli_env)
        result = runner.invoke(app, ["init", "--no-recovery"], env=cli_env)
        assert result.exit_code != 0 or "already exists" in result.output.lower()


class TestStatus:
    def test_status_shows_info(self, runner, app, initialized_env):
        result = runner.invoke(app, ["status"], env=initialized_env)
        assert result.exit_code == 0
        # Should show credential count
        assert "0" in result.output  # 0 credentials


class TestAdd:
    def test_add_credential(self, runner, app, initialized_env):
        result = runner.invoke(
            app,
            ["add", "github", "--field", "token=ghp_123", "--service", "github.com"],
            env=initialized_env,
        )
        assert result.exit_code == 0
        assert "github" in result.output.lower()

    def test_add_with_type_and_tags(self, runner, app, initialized_env):
        result = runner.invoke(
            app,
            [
                "add", "stripe",
                "--type", "api_key",
                "--field", "key=sk_test_123",
                "--tag", "production",
                "--tag", "billing",
            ],
            env=initialized_env,
        )
        assert result.exit_code == 0

    def test_add_multiple_fields(self, runner, app, initialized_env):
        result = runner.invoke(
            app,
            [
                "add", "db-prod",
                "--field", "username=admin",
                "--field", "password=secret",
                "--field", "host=db.example.com",
            ],
            env=initialized_env,
        )
        assert result.exit_code == 0

    def test_add_duplicate_fails(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "github", "--field", "token=ghp_123"],
            env=initialized_env,
        )
        result = runner.invoke(
            app,
            ["add", "github", "--field", "token=ghp_456"],
            env=initialized_env,
        )
        assert result.exit_code != 0 or "already exists" in result.output.lower()


class TestGet:
    def test_get_shows_metadata(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "github", "--field", "token=ghp_123", "--service", "github.com"],
            env=initialized_env,
        )
        result = runner.invoke(app, ["get", "github"], env=initialized_env)
        assert result.exit_code == 0
        assert "github" in result.output
        assert "github.com" in result.output

    def test_get_nonexistent(self, runner, app, initialized_env):
        result = runner.invoke(app, ["get", "nonexistent"], env=initialized_env)
        assert result.exit_code != 0 or "not found" in result.output.lower()


class TestList:
    def test_list_empty(self, runner, app, initialized_env):
        result = runner.invoke(app, ["list"], env=initialized_env)
        assert result.exit_code == 0

    def test_list_shows_credentials(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "cred1", "--field", "k=v", "--tag", "prod"],
            env=initialized_env,
        )
        runner.invoke(
            app,
            ["add", "cred2", "--field", "k=v", "--tag", "staging"],
            env=initialized_env,
        )
        result = runner.invoke(app, ["list"], env=initialized_env)
        assert result.exit_code == 0
        assert "cred1" in result.output
        assert "cred2" in result.output

    def test_list_filter_by_tag(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "cred1", "--field", "k=v", "--tag", "prod"],
            env=initialized_env,
        )
        runner.invoke(
            app,
            ["add", "cred2", "--field", "k=v", "--tag", "staging"],
            env=initialized_env,
        )
        result = runner.invoke(app, ["list", "--tag", "prod"], env=initialized_env)
        assert result.exit_code == 0
        assert "cred1" in result.output


class TestRemove:
    def test_rm_credential(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "github", "--field", "token=ghp_123"],
            env=initialized_env,
        )
        result = runner.invoke(app, ["rm", "github"], env=initialized_env)
        assert result.exit_code == 0

        # Verify it's gone
        result = runner.invoke(app, ["get", "github"], env=initialized_env)
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_rm_nonexistent(self, runner, app, initialized_env):
        result = runner.invoke(app, ["rm", "nonexistent"], env=initialized_env)
        assert result.exit_code != 0 or "not found" in result.output.lower()


class TestUpdate:
    def test_update_field(self, runner, app, initialized_env):
        runner.invoke(
            app,
            ["add", "cred1", "--field", "user=admin", "--field", "pass=old"],
            env=initialized_env,
        )
        result = runner.invoke(
            app,
            ["update", "cred1", "--field", "pass=new"],
            env=initialized_env,
        )
        assert result.exit_code == 0