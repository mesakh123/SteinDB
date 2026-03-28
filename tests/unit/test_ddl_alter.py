"""Tests for DDL ALTER TABLE rules — ADD, MODIFY, DROP column conversions."""

from __future__ import annotations

from steindb.rules.ddl_alter import (
    AlterAddColumnRule,
    AlterDropColumnRule,
    AlterModifyColumnRule,
    AlterModifyNotNullRule,
)


class TestAlterAddColumnRule:
    def setup_method(self) -> None:
        self.rule = AlterAddColumnRule()

    def test_matches(self) -> None:
        sql = "ALTER TABLE employees ADD (email VARCHAR(255))"
        assert self.rule.matches(sql)

    def test_no_match_without_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_no_match_add_constraint(self) -> None:
        sql = "ALTER TABLE employees ADD CONSTRAINT pk_emp PRIMARY KEY (id)"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "ALTER TABLE employees ADD (email VARCHAR(255))"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees ADD COLUMN email VARCHAR(255)"

    def test_apply_with_not_null(self) -> None:
        sql = "ALTER TABLE employees ADD (phone VARCHAR(20) NOT NULL)"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees ADD COLUMN phone VARCHAR(20) NOT NULL"


class TestAlterModifyColumnRule:
    def setup_method(self) -> None:
        self.rule = AlterModifyColumnRule()

    def test_matches_type_change(self) -> None:
        sql = "ALTER TABLE employees MODIFY (name VARCHAR(200))"
        assert self.rule.matches(sql)

    def test_no_match_without_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_no_match_not_null_only(self) -> None:
        # Pure NOT NULL modification handled by AlterModifyNotNullRule
        sql = "ALTER TABLE employees MODIFY (email NOT NULL)"
        assert not self.rule.matches(sql)

    def test_apply_type_change(self) -> None:
        sql = "ALTER TABLE employees MODIFY (name VARCHAR(200))"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees ALTER COLUMN name TYPE VARCHAR(200)"

    def test_apply_type_with_not_null(self) -> None:
        sql = "ALTER TABLE employees MODIFY (email VARCHAR(255) NOT NULL)"
        result = self.rule.apply(sql)
        assert "ALTER COLUMN email TYPE VARCHAR(255)" in result
        assert "ALTER COLUMN email SET NOT NULL" in result


class TestAlterModifyNotNullRule:
    def setup_method(self) -> None:
        self.rule = AlterModifyNotNullRule()

    def test_matches(self) -> None:
        sql = "ALTER TABLE employees MODIFY (email NOT NULL)"
        assert self.rule.matches(sql)

    def test_no_match_type_change(self) -> None:
        sql = "ALTER TABLE employees MODIFY (name VARCHAR(200))"
        assert not self.rule.matches(sql)

    def test_no_match_without_alter(self) -> None:
        sql = "CREATE TABLE t (id INTEGER NOT NULL)"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "ALTER TABLE employees MODIFY (email NOT NULL)"
        result = self.rule.apply(sql)
        assert result == "ALTER TABLE employees ALTER COLUMN email SET NOT NULL"


class TestAlterDropColumnRule:
    def setup_method(self) -> None:
        self.rule = AlterDropColumnRule()

    def test_matches(self) -> None:
        sql = "ALTER TABLE employees DROP COLUMN middle_name"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "ALTER TABLE employees ADD (email VARCHAR(255))"
        assert not self.rule.matches(sql)

    def test_apply_pass_through(self) -> None:
        sql = "ALTER TABLE employees DROP COLUMN middle_name"
        result = self.rule.apply(sql)
        assert result == sql  # same syntax in PostgreSQL


class TestAlterAddColumnEdgeCases:
    """Cover uncovered branches in AlterAddColumnRule."""

    def test_no_match_add_constraint_in_parens(self) -> None:
        """Cover line 39: ADD CONSTRAINT is excluded."""
        rule = AlterAddColumnRule()
        sql = "ALTER TABLE employees ADD CONSTRAINT pk_id PRIMARY KEY (id)"
        assert not rule.matches(sql)

    def test_no_match_no_add_paren(self) -> None:
        """Cover line 42 return False: ALTER TABLE without ADD ( pattern."""
        rule = AlterAddColumnRule()
        sql = "ALTER TABLE employees DROP COLUMN name"
        assert not rule.matches(sql)


class TestAlterModifyColumnEdgeCases:
    """Cover uncovered branches in AlterModifyColumnRule."""

    def test_no_match_no_modify_paren(self) -> None:
        """Cover line 74: MODIFY without parentheses doesn't match."""
        rule = AlterModifyColumnRule()
        sql = "ALTER TABLE employees MODIFY name VARCHAR(200)"
        assert not rule.matches(sql)

    def test_matches_type_ending_with_not_null(self) -> None:
        """Cover line 84: MODIFY with type + NOT NULL returns True."""
        rule = AlterModifyColumnRule()
        sql = "ALTER TABLE employees MODIFY (email VARCHAR(255) NOT NULL)"
        assert rule.matches(sql)

    def test_no_match_when_pattern_doesnt_find(self) -> None:
        """Cover line 77->85: MODIFY( present but _PATTERN doesn't match -> m is None -> return bool(m)=False."""  # noqa: E501
        rule = AlterModifyColumnRule()
        # MODIFY( with content that doesn't match the expected pattern
        sql = "ALTER TABLE employees MODIFY()"
        assert not rule.matches(sql)
