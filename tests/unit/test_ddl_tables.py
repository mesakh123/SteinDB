"""Tests for DDL table rules — CREATE TABLE, CTAS, COMMENT, RENAME."""

from __future__ import annotations

from steindb.rules.ddl_tables import (
    CommentRule,
    CreateTableRule,
    CTASRule,
    DisableConstraintRule,
    EnableConstraintRule,
    RenameTableRule,
)


class TestCreateTableRule:
    def setup_method(self) -> None:
        self.rule = CreateTableRule()

    def test_matches_default_sysdate(self) -> None:
        sql = "CREATE TABLE t (created DATE DEFAULT SYSDATE)"
        assert self.rule.matches(sql)

    def test_matches_global_temporary(self) -> None:
        sql = "CREATE GLOBAL TEMPORARY TABLE temp_results (id INTEGER)"
        assert self.rule.matches(sql)

    def test_no_match_plain_create(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_default_sysdate(self) -> None:
        sql = "CREATE TABLE logs (id INTEGER, created_at TIMESTAMP DEFAULT SYSDATE, message VARCHAR(4000))"  # noqa: E501
        result = self.rule.apply(sql)
        assert (
            result
            == "CREATE TABLE logs (id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, message VARCHAR(4000))"  # noqa: E501
        )

    def test_apply_global_temporary_delete_rows(self) -> None:
        sql = (
            "CREATE GLOBAL TEMPORARY TABLE temp_results (\n"
            "  id INTEGER,\n"
            "  result VARCHAR(100)\n"
            ") ON COMMIT DELETE ROWS"
        )
        result = self.rule.apply(sql)
        assert "CREATE TEMP TABLE temp_results" in result
        assert "ON COMMIT DELETE ROWS" in result
        assert "GLOBAL" not in result

    def test_apply_global_temporary_preserve_rows(self) -> None:
        sql = (
            "CREATE GLOBAL TEMPORARY TABLE session_data (\n"
            "  session_id VARCHAR(64),\n"
            "  payload TEXT\n"
            ") ON COMMIT PRESERVE ROWS"
        )
        result = self.rule.apply(sql)
        assert "CREATE TEMP TABLE session_data" in result
        assert "ON COMMIT PRESERVE ROWS" in result


class TestCTASRule:
    def setup_method(self) -> None:
        self.rule = CTASRule()

    def test_matches_ctas(self) -> None:
        sql = "CREATE TABLE emp_backup AS SELECT * FROM employees"
        assert self.rule.matches(sql)

    def test_no_match_regular_create(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_basic_ctas(self) -> None:
        sql = "CREATE TABLE emp_backup AS SELECT * FROM employees"
        result = self.rule.apply(sql)
        assert result == sql  # pass-through

    def test_apply_ctas_with_where(self) -> None:
        sql = "CREATE TABLE active_emp AS SELECT id, name FROM employees WHERE status = 'ACTIVE'"
        result = self.rule.apply(sql)
        assert result == sql


class TestCommentRule:
    def setup_method(self) -> None:
        self.rule = CommentRule()

    def test_matches_comment_on_table(self) -> None:
        sql = "COMMENT ON TABLE employees IS 'Employee master table'"
        assert self.rule.matches(sql)

    def test_matches_comment_on_column(self) -> None:
        sql = "COMMENT ON COLUMN employees.salary IS 'Annual salary in USD'"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_comment_on_table(self) -> None:
        sql = "COMMENT ON TABLE employees IS 'Employee master table'"
        result = self.rule.apply(sql)
        assert result == sql

    def test_apply_comment_on_column(self) -> None:
        sql = "COMMENT ON COLUMN employees.salary IS 'Annual salary in USD'"
        result = self.rule.apply(sql)
        assert result == sql


class TestRenameTableRule:
    def setup_method(self) -> None:
        self.rule = RenameTableRule()

    def test_matches_rename(self) -> None:
        sql = "RENAME employees TO staff"
        assert self.rule.matches(sql)

    def test_no_match_alter_rename_column(self) -> None:
        sql = "ALTER TABLE employees RENAME COLUMN emp_name TO full_name"
        assert not self.rule.matches(sql)

    def test_no_match_create(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_rename(self) -> None:
        sql = "RENAME employees TO staff"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees RENAME TO staff"


class TestEnableConstraintRule:
    def setup_method(self) -> None:
        self.rule = EnableConstraintRule()

    def test_matches(self) -> None:
        sql = "ALTER TABLE employees ENABLE CONSTRAINT pk_emp"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "ALTER TABLE employees ADD CONSTRAINT pk_emp PRIMARY KEY (id)"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "ALTER TABLE employees ENABLE CONSTRAINT pk_emp"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees VALIDATE CONSTRAINT pk_emp"


class TestDisableConstraintRule:
    def setup_method(self) -> None:
        self.rule = DisableConstraintRule()

    def test_matches(self) -> None:
        sql = "ALTER TABLE employees DISABLE CONSTRAINT pk_emp"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "ALTER TABLE employees DROP CONSTRAINT pk_emp"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "ALTER TABLE employees DISABLE CONSTRAINT pk_emp"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees ALTER CONSTRAINT pk_emp NOT VALID"
