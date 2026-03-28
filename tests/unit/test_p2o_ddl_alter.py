"""Tests for P2O DDL ALTER TABLE rules."""

from __future__ import annotations

from steindb.rules.p2o_ddl_alter import (
    P2OAlterAddColumnRule,
    P2OAlterColumnSetNotNullRule,
    P2OAlterColumnTypeRule,
    P2OAlterDropColumnRule,
)


class TestP2OAlterAddColumnRule:
    def setup_method(self) -> None:
        self.rule = P2OAlterAddColumnRule()

    def test_matches_add_column(self) -> None:
        sql = "ALTER TABLE employees ADD COLUMN email VARCHAR(255)"
        assert self.rule.matches(sql)

    def test_no_match_oracle_style(self) -> None:
        sql = "ALTER TABLE employees ADD (email VARCHAR2(255))"
        assert not self.rule.matches(sql)

    def test_no_match_non_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_add_column(self) -> None:
        sql = "ALTER TABLE employees ADD COLUMN email VARCHAR(255)"
        result = self.rule.apply(sql)
        assert "ADD (email VARCHAR(255))" in result
        assert "ADD COLUMN" not in result

    def test_apply_add_column_with_not_null(self) -> None:
        sql = "ALTER TABLE employees ADD COLUMN status VARCHAR(20) NOT NULL"
        result = self.rule.apply(sql)
        assert "ADD (status VARCHAR(20) NOT NULL)" in result


class TestP2OAlterColumnTypeRule:
    def setup_method(self) -> None:
        self.rule = P2OAlterColumnTypeRule()

    def test_matches_alter_column_type(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary TYPE NUMERIC(12,2)"
        assert self.rule.matches(sql)

    def test_no_match_non_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_no_match_set_not_null(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary SET NOT NULL"
        assert not self.rule.matches(sql)

    def test_apply_alter_column_type(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary TYPE NUMERIC(12,2)"
        result = self.rule.apply(sql)
        assert "MODIFY (salary NUMERIC(12,2))" in result
        assert "ALTER COLUMN" not in result

    def test_apply_alter_column_type_simple(self) -> None:
        sql = "ALTER TABLE t ALTER COLUMN name TYPE TEXT"
        result = self.rule.apply(sql)
        assert "MODIFY (name TEXT)" in result


class TestP2OAlterColumnSetNotNullRule:
    def setup_method(self) -> None:
        self.rule = P2OAlterColumnSetNotNullRule()

    def test_matches_set_not_null(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary SET NOT NULL"
        assert self.rule.matches(sql)

    def test_no_match_type_change(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary TYPE NUMERIC(12,2)"
        assert not self.rule.matches(sql)

    def test_no_match_non_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER NOT NULL)"
        assert not self.rule.matches(sql)

    def test_apply_set_not_null(self) -> None:
        sql = "ALTER TABLE employees ALTER COLUMN salary SET NOT NULL"
        result = self.rule.apply(sql)
        assert "MODIFY (salary NOT NULL)" in result
        assert "ALTER COLUMN" not in result


class TestP2OAlterDropColumnRule:
    def setup_method(self) -> None:
        self.rule = P2OAlterDropColumnRule()

    def test_matches_drop_column(self) -> None:
        sql = "ALTER TABLE employees DROP COLUMN middle_name"
        assert self.rule.matches(sql)

    def test_no_match_non_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_drop_column_passthrough(self) -> None:
        sql = "ALTER TABLE employees DROP COLUMN middle_name"
        result = self.rule.apply(sql)
        assert result == sql  # Same syntax in Oracle
