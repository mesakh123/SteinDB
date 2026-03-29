"""Tests for verify command — verification flow, status display."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003
from unittest.mock import AsyncMock, patch

import pytest
import typer
from steindb.cli.commands.verify import (
    _collect_sql_files,
    _status_style,
    verify_command,
)
from steindb.contracts import Issue, VerifyResult, VerifyStatus
from typer.testing import CliRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

runner = CliRunner()


def _make_app() -> typer.Typer:
    app = typer.Typer()
    app.command()(verify_command)
    return app


@pytest.fixture()
def app() -> typer.Typer:
    return _make_app()


@pytest.fixture()
def single_sql_file(tmp_path: Path) -> Path:
    f = tmp_path / "test_table.sql"
    f.write_text("CREATE TABLE test_table (id INTEGER NOT NULL);", encoding="utf-8")
    return f


@pytest.fixture()
def sql_dir(tmp_path: Path) -> Path:
    d = tmp_path / "converted"
    d.mkdir()
    (d / "table_a.sql").write_text("CREATE TABLE a (id INTEGER);", encoding="utf-8")
    (d / "table_b.sql").write_text("CREATE TABLE b (name TEXT);", encoding="utf-8")
    (d / "readme.txt").write_text("ignore me", encoding="utf-8")  # not .sql
    return d


def _make_green_result(name: str = "test") -> VerifyResult:
    return VerifyResult(
        object_name=name,
        object_type="TABLE",
        status=VerifyStatus.GREEN,
        confidence=0.95,
        parse_valid=True,
        explain_valid=True,
        issues=[],
    )


def _make_red_result(name: str = "bad") -> VerifyResult:
    return VerifyResult(
        object_name=name,
        object_type="TABLE",
        status=VerifyStatus.RED,
        confidence=0.1,
        parse_valid=False,
        explain_valid=False,
        issues=[
            Issue(code="PARSE_FAIL", message="Syntax error", severity="error"),
        ],
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestCollectSqlFiles:
    def test_single_file(self, single_sql_file: Path) -> None:
        files = _collect_sql_files(single_sql_file)
        assert len(files) == 1
        assert files[0] == single_sql_file

    def test_directory(self, sql_dir: Path) -> None:
        files = _collect_sql_files(sql_dir)
        assert len(files) == 2  # only .sql files
        names = {f.name for f in files}
        assert "table_a.sql" in names
        assert "table_b.sql" in names
        assert "readme.txt" not in names

    def test_nonexistent(self, tmp_path: Path) -> None:
        files = _collect_sql_files(tmp_path / "nope")
        assert files == []


class TestStatusStyle:
    def test_green(self) -> None:
        style = _status_style(VerifyStatus.GREEN)
        assert "green" in style.lower() or "GREEN" in style

    def test_yellow(self) -> None:
        style = _status_style(VerifyStatus.YELLOW)
        assert "yellow" in style.lower() or "YELLOW" in style

    def test_red(self) -> None:
        style = _status_style(VerifyStatus.RED)
        assert "red" in style.lower() or "RED" in style


# ---------------------------------------------------------------------------
# Command integration tests (with mocked Verifier)
# ---------------------------------------------------------------------------


class TestVerifyCommandFlow:
    def test_nonexistent_input(self, app: typer.Typer, tmp_path: Path) -> None:
        result = runner.invoke(app, [str(tmp_path / "nope.sql")])
        assert result.exit_code == 1

    def test_no_sql_files(self, app: typer.Typer, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(app, [str(empty_dir)])
        assert result.exit_code == 0

    @patch("steindb.cli.commands.verify.Verifier")
    def test_single_file_green(
        self, mock_verifier_cls, app: typer.Typer, single_sql_file: Path
    ) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_green_result("test_table"))

        result = runner.invoke(app, [str(single_sql_file)])
        assert result.exit_code == 0
        assert "1 green" in result.output

    @patch("steindb.cli.commands.verify.Verifier")
    def test_single_file_red_exits_1(
        self, mock_verifier_cls, app: typer.Typer, single_sql_file: Path
    ) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_red_result("test_table"))

        result = runner.invoke(app, [str(single_sql_file)])
        assert result.exit_code == 1
        assert "1 red" in result.output

    @patch("steindb.cli.commands.verify.Verifier")
    def test_directory_multiple_files(
        self, mock_verifier_cls, app: typer.Typer, sql_dir: Path
    ) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_green_result())

        result = runner.invoke(app, [str(sql_dir)])
        assert result.exit_code == 0
        assert "2 green" in result.output


class TestVerifyCommandReportFormats:
    @patch("steindb.cli.commands.verify.Verifier")
    def test_table_format(self, mock_verifier_cls, app: typer.Typer, single_sql_file: Path) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_green_result("test_table"))

        result = runner.invoke(app, [str(single_sql_file), "--report", "table"])
        assert result.exit_code == 0
        assert "Verification Results" in result.output

    @patch("steindb.cli.commands.verify.Verifier")
    def test_json_format(self, mock_verifier_cls, app: typer.Typer, single_sql_file: Path) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_green_result("test_table"))

        result = runner.invoke(app, [str(single_sql_file), "--report", "json"])
        assert result.exit_code == 0
        # Output should contain valid JSON
        assert "test_table" in result.output

    @patch("steindb.cli.commands.verify.Verifier")
    def test_html_format(self, mock_verifier_cls, app: typer.Typer, single_sql_file: Path) -> None:
        mock_verifier = mock_verifier_cls.return_value
        mock_verifier.verify = AsyncMock(return_value=_make_green_result("test_table"))

        result = runner.invoke(app, [str(single_sql_file), "--report", "html"])
        assert result.exit_code == 0
        assert "Verification Results" in result.output


class TestVerifyCommandSummary:
    @patch("steindb.cli.commands.verify.Verifier")
    def test_summary_counts(self, mock_verifier_cls, app: typer.Typer, sql_dir: Path) -> None:
        mock_verifier = mock_verifier_cls.return_value
        # First call green, second call red
        mock_verifier.verify = AsyncMock(
            side_effect=[_make_green_result("a"), _make_red_result("b")]
        )

        result = runner.invoke(app, [str(sql_dir)])
        # Should exit 1 because there's a red result
        assert result.exit_code == 1
        assert "1 green" in result.output
        assert "1 red" in result.output
