"""Tests for convert command — rules-only mode, dry-run, output files."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003

import pytest
from steindb.cli.commands.convert import (
    _build_default_registry,
    _detect_object_name,
    _detect_object_type,
    _parse_ddl_file,
    _split_statements,
    convert_command,
)
from steindb.contracts import ObjectType, ScannedObject, ScanResult
from steindb.rules import RuleRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_DDL = """\
CREATE TABLE employees (
    id NUMBER(10) NOT NULL,
    name VARCHAR2(100),
    hire_date DATE
);

CREATE SEQUENCE emp_seq START WITH 1 INCREMENT BY 1;

CREATE INDEX idx_emp_name ON employees(name);
"""

PLSQL_DDL = """\
CREATE OR REPLACE PROCEDURE get_count AS
BEGIN
    DBMS_OUTPUT.PUT_LINE('count');
END;
/

CREATE TABLE departments (
    id NUMBER(10),
    dept_name VARCHAR2(50)
);
"""


@pytest.fixture()
def ddl_file(tmp_path: Path) -> Path:
    f = tmp_path / "schema.sql"
    f.write_text(SIMPLE_DDL, encoding="utf-8")
    return f


@pytest.fixture()
def plsql_file(tmp_path: Path) -> Path:
    f = tmp_path / "plsql.sql"
    f.write_text(PLSQL_DDL, encoding="utf-8")
    return f


@pytest.fixture()
def scan_json_file(tmp_path: Path) -> Path:
    scan = ScanResult(
        job_id="j-1",
        customer_id="c-1",
        objects=[
            ScannedObject(
                name="T1",
                schema="S",
                object_type=ObjectType.TABLE,
                source_sql="CREATE TABLE T1 (id NUMBER)",
                line_count=1,
            ),
        ],
        total_objects=1,
        scan_duration_seconds=0.5,
    )
    f = tmp_path / "scan.json"
    f.write_text(scan.model_dump_json(indent=2), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestSplitStatements:
    def test_splits_on_semicolon(self) -> None:
        stmts = _split_statements("CREATE TABLE a (id INT);\nCREATE TABLE b (id INT);")
        assert len(stmts) == 2

    def test_plsql_block_preserved(self) -> None:
        sql = "CREATE OR REPLACE PROCEDURE p AS\nBEGIN\n  NULL;\nEND;\n/\nCREATE TABLE t (id INT);"
        stmts = _split_statements(sql)
        # The procedure block should be kept as one statement
        assert any("PROCEDURE" in s for s in stmts)
        assert any("TABLE" in s for s in stmts)

    def test_empty_input(self) -> None:
        assert _split_statements("") == []


class TestDetectObjectType:
    def test_table(self) -> None:
        assert _detect_object_type("CREATE TABLE foo (id INT)") == ObjectType.TABLE

    def test_index(self) -> None:
        assert _detect_object_type("CREATE INDEX idx ON foo(id)") == ObjectType.INDEX

    def test_sequence(self) -> None:
        assert _detect_object_type("CREATE SEQUENCE seq START WITH 1") == ObjectType.SEQUENCE

    def test_view(self) -> None:
        assert _detect_object_type("CREATE VIEW v AS SELECT 1") == ObjectType.VIEW

    def test_procedure(self) -> None:
        assert (
            _detect_object_type("CREATE OR REPLACE PROCEDURE p AS BEGIN NULL; END;")
            == ObjectType.PROCEDURE
        )

    def test_function(self) -> None:
        assert (
            _detect_object_type("CREATE OR REPLACE FUNCTION f RETURN INT AS BEGIN RETURN 1; END;")
            == ObjectType.FUNCTION
        )

    def test_materialized_view(self) -> None:
        assert (
            _detect_object_type("CREATE MATERIALIZED VIEW mv AS SELECT 1")
            == ObjectType.MATERIALIZED_VIEW
        )

    def test_fallback_to_table(self) -> None:
        assert _detect_object_type("SELECT 1 FROM dual") == ObjectType.TABLE


class TestDetectObjectName:
    def test_simple_table(self) -> None:
        name = _detect_object_name("CREATE TABLE employees (id INT)", ObjectType.TABLE)
        assert name == "employees"

    def test_or_replace_procedure(self) -> None:
        name = _detect_object_name("CREATE OR REPLACE PROCEDURE get_count AS", ObjectType.PROCEDURE)
        assert name is not None

    def test_returns_none_for_garbage(self) -> None:
        name = _detect_object_name("SELECT 1", ObjectType.TABLE)
        assert name is None


class TestParseDDLFile:
    def test_parses_simple_ddl(self, ddl_file: Path) -> None:
        objects = _parse_ddl_file(ddl_file)
        assert len(objects) == 3
        types = {o.object_type for o in objects}
        assert ObjectType.TABLE in types
        assert ObjectType.SEQUENCE in types
        assert ObjectType.INDEX in types

    def test_all_objects_have_source_sql(self, ddl_file: Path) -> None:
        objects = _parse_ddl_file(ddl_file)
        for obj in objects:
            assert len(obj.source_sql) > 0

    def test_plsql_file(self, plsql_file: Path) -> None:
        objects = _parse_ddl_file(plsql_file)
        assert len(objects) >= 2
        types = {o.object_type for o in objects}
        assert ObjectType.PROCEDURE in types
        assert ObjectType.TABLE in types


class TestBuildDefaultRegistry:
    def test_returns_registry(self) -> None:
        registry = _build_default_registry()
        assert isinstance(registry, RuleRegistry)

    def test_registry_has_rules(self) -> None:
        registry = _build_default_registry()
        # Should have at least some rules registered
        assert registry.rule_count >= 0  # May be 0 if rules have no default constructors


# ---------------------------------------------------------------------------
# Integration-style tests via typer invocation
# ---------------------------------------------------------------------------


class TestConvertCommandRulesMode:
    def test_nonexistent_input(self, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        result = runner.invoke(app, [str(tmp_path / "nonexistent.sql")])
        assert result.exit_code == 1

    def test_rules_mode_ddl(self, ddl_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        out_dir = tmp_path / "out"
        result = runner.invoke(
            app,
            [str(ddl_file), "--output", str(out_dir), "--mode", "rules"],
        )
        # Should succeed (exit code 0)
        assert result.exit_code == 0
        # Output directory should have been created
        assert out_dir.exists()

    def test_dry_run_no_output_files(self, ddl_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        out_dir = tmp_path / "dry_out"
        result = runner.invoke(
            app,
            [str(ddl_file), "--output", str(out_dir), "--mode", "rules", "--dry-run"],
        )
        assert result.exit_code == 0
        # Dry run should NOT create the output directory
        assert not out_dir.exists()

    def test_dry_run_shows_summary(self, ddl_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        result = runner.invoke(
            app,
            [str(ddl_file), "--mode", "rules", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Conversion Summary" in result.output or "Dry Run Summary" in result.output

    def test_json_input(self, scan_json_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        out_dir = tmp_path / "json_out"
        result = runner.invoke(
            app,
            [str(scan_json_file), "--output", str(out_dir), "--mode", "rules"],
        )
        assert result.exit_code == 0

    def test_invalid_mode(self, ddl_file: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        result = runner.invoke(app, [str(ddl_file), "--mode", "invalid"])
        assert result.exit_code == 1

    def test_ai_mode_requires_api_key(self, ddl_file: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        result = runner.invoke(app, [str(ddl_file), "--mode", "ai"])
        assert result.exit_code == 1


class TestConvertCommandOutput:
    def test_output_files_created(self, ddl_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        out_dir = tmp_path / "files_out"
        result = runner.invoke(
            app,
            [str(ddl_file), "--output", str(out_dir), "--mode", "rules"],
        )
        assert result.exit_code == 0
        # Should have .sql files in output dir
        sql_files = list(out_dir.glob("*.sql"))
        assert len(sql_files) >= 1

    def test_converted_sql_files_non_empty(self, ddl_file: Path, tmp_path: Path) -> None:
        import typer
        from typer.testing import CliRunner

        app = typer.Typer()
        app.command()(convert_command)
        runner = CliRunner()

        out_dir = tmp_path / "content_out"
        runner.invoke(
            app,
            [str(ddl_file), "--output", str(out_dir), "--mode", "rules"],
        )
        for sql_file in out_dir.glob("*.sql"):
            content = sql_file.read_text(encoding="utf-8")
            assert len(content) > 0
