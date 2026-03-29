"""Tests for PL/SQL control flow rules."""

from __future__ import annotations

from steindb.rules.plsql_control_flow import (
    CursorForLoopRule,
    ExceptionHandlingRule,
    ExitWhenRule,
)


class TestExceptionHandlingRule:
    rule = ExceptionHandlingRule()

    def test_matches_dup_val(self) -> None:
        assert self.rule.matches("WHEN DUP_VAL_ON_INDEX THEN")

    def test_matches_no_data_found(self) -> None:
        assert self.rule.matches("WHEN NO_DATA_FOUND THEN")

    def test_no_match(self) -> None:
        assert not self.rule.matches("WHEN OTHERS THEN")

    def test_apply_dup_val(self) -> None:
        sql = "EXCEPTION WHEN DUP_VAL_ON_INDEX THEN"
        result = self.rule.apply(sql)
        assert "WHEN UNIQUE_VIOLATION" in result

    def test_apply_no_data_found(self) -> None:
        sql = "EXCEPTION WHEN NO_DATA_FOUND THEN"
        result = self.rule.apply(sql)
        assert "WHEN NO_DATA_FOUND" in result  # Same in PG

    def test_apply_too_many_rows(self) -> None:
        sql = "WHEN TOO_MANY_ROWS THEN"
        result = self.rule.apply(sql)
        assert "WHEN TOO_MANY_ROWS" in result  # Same in PG

    def test_apply_value_error(self) -> None:
        sql = "WHEN VALUE_ERROR THEN"
        result = self.rule.apply(sql)
        assert "WHEN DATA_EXCEPTION" in result

    def test_apply_zero_divide(self) -> None:
        sql = "WHEN ZERO_DIVIDE THEN"
        result = self.rule.apply(sql)
        assert "WHEN DIVISION_BY_ZERO" in result

    def test_apply_multiple(self) -> None:
        sql = "EXCEPTION\nWHEN DUP_VAL_ON_INDEX THEN NULL;\nWHEN ZERO_DIVIDE THEN NULL;"
        result = self.rule.apply(sql)
        assert "UNIQUE_VIOLATION" in result
        assert "DIVISION_BY_ZERO" in result

    def test_case_insensitive(self) -> None:
        sql = "when dup_val_on_index then"
        result = self.rule.apply(sql)
        assert "UNIQUE_VIOLATION" in result


class TestCursorForLoopRule:
    rule = CursorForLoopRule()

    def test_matches(self) -> None:
        assert self.rule.matches("FOR rec IN cur LOOP")

    def test_no_match(self) -> None:
        assert not self.rule.matches("WHILE x > 0 LOOP")

    def test_apply_passthrough(self) -> None:
        sql = "FOR rec IN cur LOOP\n  DBMS_OUTPUT.PUT_LINE(rec.name);\nEND LOOP;"
        result = self.rule.apply(sql)
        assert result == sql  # Pass-through


class TestExitWhenRule:
    rule = ExitWhenRule()

    def test_matches(self) -> None:
        assert self.rule.matches("EXIT WHEN v_done;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("EXIT;")

    def test_apply_passthrough(self) -> None:
        sql = "EXIT WHEN v_count > 100;"
        result = self.rule.apply(sql)
        assert result == sql  # Pass-through
