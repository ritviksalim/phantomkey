# Copyright (c) 2026 Ritvik Salim. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

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


class TestExecBrowser:
    def _fake_browser_module(self, monkeypatch, calls):
        from contextlib import contextmanager
        from phantomkey.executor import browser_playwright

        class FakeDriver:
            def navigate(self, url):
                calls.append(("navigate", url))

            def fill(self, selector, value):
                calls.append(("fill", selector, value))

            def click(self, selector):
                calls.append(("click", selector))

            def text_content(self, selector):
                return ""

        @contextmanager
        def fake_browser(headless=True):
            yield FakeDriver()

        monkeypatch.setattr(browser_playwright, "playwright_browser", fake_browser)

    def test_exec_browser_blind_injection(self, runner, app, initialized_env, monkeypatch):
        runner.invoke(app, ["add", "site", "--field", "password=p@ss"], env=initialized_env)
        calls = []
        self._fake_browser_module(monkeypatch, calls)
        result = runner.invoke(
            app,
            ["exec-browser", "--actions",
             '[{"action":"fill","selector":"#pw","value":"{{site.password}}"}]'],
            env=initialized_env,
        )
        assert result.exit_code == 0
        assert ("fill", "#pw", "p@ss") in calls
        assert "p@ss" not in result.output

    def test_exec_browser_invalid_json(self, runner, app, initialized_env):
        result = runner.invoke(app, ["exec-browser", "--actions", "not json"], env=initialized_env)
        assert result.exit_code != 0


class TestVersion:
    def test_version_flag_exits_zero(self, runner, app):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_flag_prints_version(self, runner, app):
        from phantomkey import __version__

        result = runner.invoke(app, ["--version"])
        assert __version__ in result.output

    def test_version_flag_needs_no_vault(self, runner, app):
        # --version must work without an initialized vault or master key.
        result = runner.invoke(app, ["--version"], env={})
        assert result.exit_code == 0
        assert "phantomkey" in result.output.lower()
