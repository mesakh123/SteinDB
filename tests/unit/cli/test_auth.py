"""Tests for auth commands — register, login, logout, status."""

import pytest
from steindb.cli.config_manager import ConfigManager
from steindb.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def config_dir(tmp_path):
    return tmp_path / ".steindb"


@pytest.fixture(autouse=True)
def _patch_config_dir(monkeypatch, config_dir):
    """Patch ConfigManager to use a temp directory for all auth tests."""
    monkeypatch.setattr(
        "steindb.cli.commands.auth._get_config_manager",
        lambda: ConfigManager(config_dir=config_dir),
    )


class TestAuthRegister:
    def test_register_stores_token_and_email(self, config_dir):
        result = runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        assert result.exit_code == 0
        assert "registered successfully" in result.output.lower()
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("api_key") is not None
        assert mgr.get("api_key").startswith("stdb_free_")
        assert mgr.get("email") == "user@example.com"

    def test_register_shows_token_preview(self, config_dir):
        result = runner.invoke(app, ["auth", "register", "--email", "test@test.com"])
        assert result.exit_code == 0
        assert "Token:" in result.output
        assert "..." in result.output

    def test_register_shows_next_steps(self, config_dir):
        result = runner.invoke(app, ["auth", "register", "--email", "test@test.com"])
        assert result.exit_code == 0
        assert "stein convert" in result.output


class TestAuthLogin:
    def test_login_with_token(self, config_dir):
        result = runner.invoke(app, ["auth", "login", "--token", "stdb_free_abc123def456"])
        assert result.exit_code == 0
        assert "logged in" in result.output.lower()
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("api_key") == "stdb_free_abc123def456"

    def test_login_shows_tier(self, config_dir):
        result = runner.invoke(app, ["auth", "login", "--token", "stdb_solo_abc123def456"])
        assert result.exit_code == 0
        assert "solo" in result.output.lower()

    def test_login_overwrites_existing_token(self, config_dir):
        runner.invoke(app, ["auth", "login", "--token", "stdb_free_old"])
        runner.invoke(app, ["auth", "login", "--token", "stdb_free_new"])
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("api_key") == "stdb_free_new"

    def test_login_requires_token(self):
        result = runner.invoke(app, ["auth", "login"])
        # Should fail or prompt — missing required option
        assert result.exit_code != 0


class TestAuthLogout:
    def test_logout_clears_token_and_email(self, config_dir):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert "logged out" in result.output.lower()
        mgr = ConfigManager(config_dir=config_dir)
        assert mgr.get("api_key") is None
        assert mgr.get("email") is None

    def test_logout_when_not_logged_in(self):
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0

    def test_logout_mentions_rules_still_work(self):
        result = runner.invoke(app, ["auth", "logout"])
        assert "rules-only" in result.output.lower()


class TestAuthUpgrade:
    def test_upgrade_requires_registration(self):
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 1
        assert "register first" in result.output.lower()

    def test_upgrade_shows_current_tier(self, config_dir):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 0
        assert "current tier" in result.output.lower()
        assert "registered" in result.output.lower()

    def test_upgrade_shows_tiers(self, config_dir):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 0
        assert "Solo" in result.output
        assert "Team" in result.output

    def test_upgrade_shows_checkout_url(self, config_dir):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 0
        assert "app.steindb.com/upgrade" in result.output

    def test_upgrade_attempts_browser_open(self, config_dir, monkeypatch):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        opened_urls: list[str] = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened_urls.append(url))
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 0
        assert len(opened_urls) == 1
        assert "app.steindb.com/upgrade" in opened_urls[0]

    def test_upgrade_handles_browser_failure(self, config_dir, monkeypatch):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])

        def _fail(url: str) -> None:
            raise OSError("no browser")

        monkeypatch.setattr("webbrowser.open", _fail)
        result = runner.invoke(app, ["auth", "upgrade"])
        assert result.exit_code == 0
        assert "copy the url" in result.output.lower()


class TestAuthStatus:
    def test_status_shows_tier_info(self, config_dir):
        runner.invoke(app, ["auth", "login", "--token", "stdb_free_abc123def456789012"])
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "authenticated" in result.output.lower()
        assert "registered" in result.output.lower()

    def test_status_shows_email(self, config_dir):
        runner.invoke(app, ["auth", "register", "--email", "user@example.com"])
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "user@example.com" in result.output

    def test_status_when_not_authenticated(self):
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "not authenticated" in result.output.lower()
        assert "stein auth register" in result.output

    def test_status_masks_token(self, config_dir):
        token = "stdb_free_abc123def456789012345678901234567890"
        runner.invoke(app, ["auth", "login", "--token", token])
        result = runner.invoke(app, ["auth", "status"])
        # Full token should NOT be visible
        assert token not in result.output
        # But a masked version should appear
        assert "..." in result.output

    def test_status_shows_na_when_no_email(self, config_dir):
        runner.invoke(app, ["auth", "login", "--token", "stdb_free_abc123def456789012"])
        result = runner.invoke(app, ["auth", "status"])
        assert "N/A" in result.output
