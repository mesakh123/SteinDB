"""Tests for CLI scaffolding — entry point, version, help, subcommands."""

from steindb.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_help_shows_branding():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "SteinDB" in result.output


def test_all_subcommands_registered():
    for cmd in ["scan", "convert", "verify", "report", "auth", "config"]:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, f"Command '{cmd}' not registered"


def test_auth_subcommands():
    for sub in ["login", "logout", "status"]:
        result = runner.invoke(app, ["auth", sub, "--help"])
        assert result.exit_code == 0, f"Auth subcommand '{sub}' not registered"


def test_config_subcommands():
    for sub in ["set", "get", "list"]:
        result = runner.invoke(app, ["config", sub, "--help"])
        assert result.exit_code == 0, f"Config subcommand '{sub}' not registered"


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer returns exit code 0 when showing help via --help,
    # but exit code 2 when no_args_is_help triggers (no args given).
    # The important thing is it shows help text.
    assert "SteinDB" in result.output
