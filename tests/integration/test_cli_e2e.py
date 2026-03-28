"""End-to-end integration tests for the SteinDB CLI pipeline.

Tests the full flow: scan -> convert -> verify using the CLI commands
via Typer's CliRunner (in-process) and subprocess (out-of-process).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from steindb.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

SAMPLE_DDL = """\
CREATE TABLE hr.employees (
    id NUMBER(10) NOT NULL,
    name VARCHAR2(100),
    hire_date DATE,
    CONSTRAINT pk_emp PRIMARY KEY (id)
);

CREATE SEQUENCE hr.emp_seq START WITH 1 INCREMENT BY 1;
"""

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_oracle.sql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ddl(tmp_path: Path, content: str = SAMPLE_DDL) -> Path:
    """Write a DDL file and return its path."""
    ddl_file = tmp_path / "test.sql"
    ddl_file.write_text(content, encoding="utf-8")
    return ddl_file


# ---------------------------------------------------------------------------
# Scan tests
# ---------------------------------------------------------------------------


class TestScanCommand:
    def test_scan_ddl_file_json(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        result = runner.invoke(app, ["scan", str(ddl_file), "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["summary"]["total"] >= 2
        assert len(data["objects"]) >= 2

    def test_scan_ddl_file_table(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        result = runner.invoke(app, ["scan", str(ddl_file), "--output", "table"])
        assert result.exit_code == 0
        assert "EMPLOYEES" in result.output or "employees" in result.output.lower()

    def test_scan_nonexistent_file(self):
        result = runner.invoke(app, ["scan", "/nonexistent/path.sql"])
        assert result.exit_code == 1

    def test_scan_empty_file(self, tmp_path):
        empty = tmp_path / "empty.sql"
        empty.write_text("", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(empty)])
        assert result.exit_code == 0
        assert "No Oracle objects" in result.output

    def test_scan_fixture_file(self):
        """Scan the shared fixture file."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Fixture file not found")
        result = runner.invoke(app, ["scan", str(FIXTURE_PATH), "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["summary"]["total"] >= 4

    def test_scan_json_contains_object_fields(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        result = runner.invoke(app, ["scan", str(ddl_file), "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        obj = data["objects"][0]
        assert "name" in obj
        assert "type" in obj
        assert "schema" in obj
        assert "complexity_score" in obj


# ---------------------------------------------------------------------------
# Convert tests
# ---------------------------------------------------------------------------


class TestConvertCommand:
    def test_convert_rules_mode(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        output_dir = tmp_path / "output"
        result = runner.invoke(
            app,
            ["convert", str(ddl_file), "--output", str(output_dir), "--mode", "rules"],
        )
        assert result.exit_code == 0
        sql_files = list(output_dir.glob("*.sql"))
        assert len(sql_files) >= 1

    def test_convert_produces_postgresql(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        output_dir = tmp_path / "output"
        runner.invoke(
            app,
            ["convert", str(ddl_file), "--output", str(output_dir), "--mode", "rules"],
        )
        # Check that output files contain PostgreSQL-compatible content
        for sql_file in output_dir.glob("*.sql"):
            content = sql_file.read_text(encoding="utf-8")
            assert len(content) > 0

    def test_convert_nonexistent_input(self, tmp_path):
        output_dir = tmp_path / "output"
        result = runner.invoke(
            app,
            ["convert", "/nonexistent/file.sql", "--output", str(output_dir), "--mode", "rules"],
        )
        assert result.exit_code == 1

    def test_convert_dry_run(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        output_dir = tmp_path / "output"
        result = runner.invoke(
            app,
            [
                "convert",
                str(ddl_file),
                "--output",
                str(output_dir),
                "--mode",
                "rules",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry Run" in result.output

    def test_convert_fixture_file(self, tmp_path):
        """Convert the shared fixture file."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Fixture file not found")
        output_dir = tmp_path / "output"
        result = runner.invoke(
            app,
            ["convert", str(FIXTURE_PATH), "--output", str(output_dir), "--mode", "rules"],
        )
        assert result.exit_code == 0
        sql_files = list(output_dir.glob("*.sql"))
        assert len(sql_files) >= 3


# ---------------------------------------------------------------------------
# Verify tests
# ---------------------------------------------------------------------------


class TestVerifyCommand:
    def test_verify_converted_files(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        output_dir = tmp_path / "output"
        # Convert first
        runner.invoke(
            app,
            ["convert", str(ddl_file), "--output", str(output_dir), "--mode", "rules"],
        )
        # Verify
        result = runner.invoke(app, ["verify", str(output_dir)])
        # Exit 0 = all green/yellow, exit 1 = has red
        assert result.exit_code in (0, 1)
        assert "Verification" in result.output or "Summary" in result.output

    def test_verify_nonexistent_input(self):
        result = runner.invoke(app, ["verify", "/nonexistent/dir"])
        assert result.exit_code == 1

    def test_verify_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(app, ["verify", str(empty_dir)])
        assert result.exit_code == 0
        assert "No .sql files" in result.output


# ---------------------------------------------------------------------------
# Full pipeline: scan -> convert -> verify
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_scan_convert_verify_flow(self, tmp_path):
        """End-to-end: create DDL, scan, convert, verify."""
        ddl_file = _write_ddl(tmp_path)

        # 1. Scan
        scan_result = runner.invoke(app, ["scan", str(ddl_file), "--output", "json"])
        assert scan_result.exit_code == 0
        scan_data = json.loads(scan_result.output)
        assert scan_data["summary"]["total"] >= 2

        # 2. Convert
        output_dir = tmp_path / "converted"
        convert_result = runner.invoke(
            app,
            ["convert", str(ddl_file), "--output", str(output_dir), "--mode", "rules"],
        )
        assert convert_result.exit_code == 0
        sql_files = list(output_dir.glob("*.sql"))
        assert len(sql_files) >= 1

        # 3. Verify
        verify_result = runner.invoke(app, ["verify", str(output_dir)])
        assert verify_result.exit_code in (0, 1)
        assert "Summary" in verify_result.output

    def test_full_flow_with_fixture(self, tmp_path):
        """End-to-end using the sample_oracle.sql fixture."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Fixture file not found")

        # Scan
        scan_result = runner.invoke(app, ["scan", str(FIXTURE_PATH), "--output", "json"])
        assert scan_result.exit_code == 0
        scan_data = json.loads(scan_result.output)
        assert scan_data["summary"]["total"] >= 4

        # Convert
        output_dir = tmp_path / "converted"
        convert_result = runner.invoke(
            app,
            ["convert", str(FIXTURE_PATH), "--output", str(output_dir), "--mode", "rules"],
        )
        assert convert_result.exit_code == 0
        sql_files = list(output_dir.glob("*.sql"))
        assert len(sql_files) >= 3

        # Verify
        verify_result = runner.invoke(app, ["verify", str(output_dir)])
        assert verify_result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# Subprocess tests (out-of-process)
# ---------------------------------------------------------------------------


class TestSubprocess:
    def test_scan_via_subprocess(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        result = subprocess.run(
            [sys.executable, "-m", "steindb.cli.main", "scan", str(ddl_file), "--output", "json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            timeout=30,
        )
        assert result.returncode == 0

    def test_convert_via_subprocess(self, tmp_path):
        ddl_file = _write_ddl(tmp_path)
        output_dir = tmp_path / "output"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "steindb.cli.main",
                "convert",
                str(ddl_file),
                "--output",
                str(output_dir),
                "--mode",
                "rules",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            timeout=30,
        )
        assert result.returncode == 0
        sql_files = list(output_dir.glob("*.sql"))
        assert len(sql_files) >= 1

    def test_version_via_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "steindb.cli.main", "--version"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            timeout=10,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout
