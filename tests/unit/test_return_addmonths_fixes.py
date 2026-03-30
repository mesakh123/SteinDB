# tests/unit/test_return_addmonths_fixes.py
"""Tests for BUG 4 (RETURN without parens) and BUG 6 (ADD_MONTHS with variables)."""

from __future__ import annotations

from steindb.contracts.models import ScannedObject
from steindb.rules.engine import O2PRuleEngine
from steindb.rules.loader import create_direction_registry
from steindb.rules.plsql_basic import ReturnToReturnsRule
from steindb.rules.syntax_datetime import ADDMONTHSRule


class TestReturnWithoutParens:
    rule = ReturnToReturnsRule()

    def test_matches_without_parens(self) -> None:
        sql = "CREATE OR REPLACE FUNCTION get_count RETURN NUMBER IS"
        assert self.rule.matches(sql)

    def test_apply_without_parens(self) -> None:
        sql = "CREATE OR REPLACE FUNCTION get_count RETURN NUMBER IS"
        result = self.rule.apply(sql)
        assert "RETURNS NUMBER" in result
        assert "RETURN NUMBER" not in result

    def test_matches_with_parens(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURN VARCHAR2 IS"
        assert self.rule.matches(sql)

    def test_apply_with_parens(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURN VARCHAR2 IS"
        result = self.rule.apply(sql)
        assert "RETURNS VARCHAR2" in result

    def test_body_return_not_converted(self) -> None:
        assert not self.rule.matches("RETURN v_name;")
        assert not self.rule.matches("RETURN 42;")

    def test_return_without_parens_via_engine(self) -> None:
        sql = """CREATE OR REPLACE FUNCTION get_count RETURN NUMBER IS
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM employees;
  RETURN v_count;
END;"""
        registry = create_direction_registry("o2p")
        engine = O2PRuleEngine(registry)
        obj = ScannedObject(
            name="test",
            object_type="FUNCTION",
            source_sql=sql,
            schema="PUBLIC",
            line_count=6,
        )
        result = engine.convert(obj)
        assert "RETURNS" in result.target_sql, f"RETURN not converted: {result.target_sql}"


class TestAddMonthsIntervalMath:
    rule = ADDMONTHSRule()

    def test_literal_uses_interval_math(self) -> None:
        result = self.rule.apply("SELECT ADD_MONTHS(hire_date, 6) FROM emp")
        assert "ADD_MONTHS" not in result
        assert "* interval '1 month'" in result
        assert "||" not in result

    def test_variable_uses_interval_math(self) -> None:
        result = self.rule.apply("SELECT ADD_MONTHS(hire_date, v_months) FROM emp")
        assert "ADD_MONTHS" not in result
        assert "* interval '1 month'" in result
        assert "||" not in result

    def test_negative_literal(self) -> None:
        result = self.rule.apply("SELECT ADD_MONTHS(SYSDATE, -3) FROM DUAL")
        assert "(-3 * interval '1 month')" in result
        assert "||" not in result

    def test_variable_via_engine(self) -> None:
        sql = "SELECT ADD_MONTHS(hire_date, v_months) FROM employees"
        registry = create_direction_registry("o2p")
        engine = O2PRuleEngine(registry)
        obj = ScannedObject(
            name="test",
            object_type="TABLE",
            source_sql=sql,
            schema="PUBLIC",
            line_count=1,
        )
        result = engine.convert(obj)
        assert "ADD_MONTHS" not in result.target_sql
        assert "||" not in result.target_sql
