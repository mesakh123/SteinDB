"""Tests for P2O syntax_misc rules."""

from __future__ import annotations

from steindb.rules.p2o_syntax_misc import (
    CurrentUserToUserRule,
    ExceptToMinusRule,
    GenerateSeriesToConnectByRule,
    LimitToFetchFirstRule,
    OnConflictToMergeRule,
    SelectFromDualRule,
)


class TestStringLiteralHelpers:
    """Cover _is_inside_string returning True (line 22) and
    _matches_outside_strings / _replace_outside_strings when all matches
    are inside strings (branches 29->28, 40->39)."""

    def test_limit_inside_string_not_matched(self) -> None:
        """LIMIT inside a string literal should not match (line 22, branch 29->28)."""
        rule = LimitToFetchFirstRule()
        sql = "SELECT 'LIMIT 10' FROM employees"
        assert not rule.matches(sql)

    def test_except_inside_string_not_matched(self) -> None:
        """EXCEPT inside a string literal should not be replaced (branch 40->39)."""
        rule = ExceptToMinusRule()
        sql = "SELECT 'EXCEPT clause' FROM t"
        assert not rule.matches(sql)

    def test_on_conflict_inside_string_not_matched(self) -> None:
        """ON CONFLICT inside a string literal should not match."""
        rule = OnConflictToMergeRule()
        sql = "SELECT 'INSERT INTO t (x) VALUES (1) ON CONFLICT (x) DO UPDATE SET y = 2' FROM t"
        assert not rule.matches(sql)


class TestLimitToFetchFirstRule:
    rule = LimitToFetchFirstRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT * FROM employees LIMIT 10")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM employees WHERE id = 1")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT * FROM employees LIMIT 10")
        assert "FETCH FIRST 10 ROWS ONLY" in result
        assert "LIMIT" not in result

    def test_apply_limit_1(self) -> None:
        result = self.rule.apply("SELECT * FROM employees LIMIT 1")
        assert "FETCH FIRST 1 ROWS ONLY" in result


class TestExceptToMinusRule:
    rule = ExceptToMinusRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT id FROM active EXCEPT SELECT id FROM banned")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT id FROM active MINUS SELECT id FROM banned")

    def test_no_match_exception(self) -> None:
        """Should not match EXCEPTION keyword."""
        assert not self.rule.matches("WHEN EXCEPTION THEN")

    def test_apply(self) -> None:
        sql = "SELECT id FROM active EXCEPT SELECT id FROM banned"
        result = self.rule.apply(sql)
        assert "MINUS" in result
        assert "EXCEPT" not in result


class TestCurrentUserToUserRule:
    rule = CurrentUserToUserRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT CURRENT_USER")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT USER FROM DUAL")

    def test_apply(self) -> None:
        result = self.rule.apply("INSERT INTO audit_log (created_by) VALUES (CURRENT_USER)")
        assert "USER" in result
        assert "CURRENT_USER" not in result


class TestSelectFromDualRule:
    rule = SelectFromDualRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT 1")

    def test_matches_with_semicolon(self) -> None:
        assert self.rule.matches("SELECT 1 + 1;")

    def test_no_match_has_from(self) -> None:
        assert not self.rule.matches("SELECT 1 FROM employees")

    def test_no_match_not_select(self) -> None:
        assert not self.rule.matches("INSERT INTO t VALUES (1)")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT 1")
        assert result == "SELECT 1 FROM DUAL"

    def test_apply_with_semicolon(self) -> None:
        result = self.rule.apply("SELECT 1 + 1;")
        assert result == "SELECT 1 + 1 FROM DUAL;"

    def test_apply_expression(self) -> None:
        result = self.rule.apply("SELECT SYSDATE")
        assert result == "SELECT SYSDATE FROM DUAL"


class TestGenerateSeriesToConnectByRule:
    rule = GenerateSeriesToConnectByRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT generate_series(1, 100)")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM t")

    def test_apply_from_1(self) -> None:
        result = self.rule.apply("SELECT generate_series(1, 100)")
        assert "SELECT LEVEL FROM DUAL CONNECT BY LEVEL <= 100" in result

    def test_apply_from_n(self) -> None:
        result = self.rule.apply("SELECT generate_series(5, n)")
        assert "LEVEL + 4" in result
        assert "CONNECT BY" in result


class TestOnConflictToMergeRule:
    rule = OnConflictToMergeRule()

    def test_matches(self) -> None:
        sql = (
            "INSERT INTO target (id, val) VALUES (1, 'x') "
            "ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val"
        )
        assert self.rule.matches(sql)

    def test_no_match_insert(self) -> None:
        sql = "INSERT INTO target (id, val) VALUES (1, 'x')"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = (
            "INSERT INTO target (id, val) VALUES (1, 'x') "
            "ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val"
        )
        result = self.rule.apply(sql)
        assert "MERGE INTO" in result
        assert "USING" in result
        assert "WHEN MATCHED" in result
        assert "WHEN NOT MATCHED" in result
        assert "ON CONFLICT" not in result

    def test_apply_replaces_excluded(self) -> None:
        sql = (
            "INSERT INTO employees (id, name) VALUES (1, 'Alice') "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
        )
        result = self.rule.apply(sql)
        assert "s.name" in result
        assert "EXCLUDED" not in result

    def test_apply_structure(self) -> None:
        sql = (
            "INSERT INTO t (id, val) VALUES (1, 'a') "
            "ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val"
        )
        result = self.rule.apply(sql)
        assert "MERGE INTO t t " in result
        assert "FROM DUAL" in result
        assert "ON (t.id = s.id)" in result

    def test_apply_no_regex_match_returns_unchanged(self) -> None:
        """Line 213: apply() called on SQL that _ON_CONFLICT_RE.search doesn't match.

        The _matches_outside_strings helper checks with string-aware logic,
        but apply() uses raw regex. Construct a case where the string-aware
        match succeeds but the raw regex doesn't. Since that's hard to trigger
        naturally, we directly call apply on non-matching SQL to cover the guard.
        """
        rule = OnConflictToMergeRule()
        sql = "INSERT INTO t (id) VALUES (1)"
        result = rule.apply(sql)
        assert result == sql
