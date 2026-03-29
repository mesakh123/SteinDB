"""Tests for syntax_datetime rules."""

from __future__ import annotations

from steindb.rules.syntax_datetime import (
    ADDMONTHSRule,
    DateArithmeticRule,
    LASTDAYRule,
    SYSDATERule,
    SYSTIMESTAMPRule,
    TRUNCDateRule,
)


class TestSYSDATERule:
    rule = SYSDATERule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT SYSDATE FROM DUAL")

    def test_matches_case_insensitive(self) -> None:
        assert self.rule.matches("SELECT sysdate FROM DUAL")

    def test_no_match_in_string(self) -> None:
        assert not self.rule.matches("SELECT 'SYSDATE' FROM t")

    def test_no_match_systimestamp(self) -> None:
        assert not self.rule.matches("SELECT SYSTIMESTAMP FROM DUAL")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT SYSDATE FROM DUAL")
        assert "CURRENT_TIMESTAMP" in result
        assert "SYSDATE" not in result

    def test_apply_preserves_context(self) -> None:
        sql = "INSERT INTO t (created_at) VALUES (SYSDATE)"
        result = self.rule.apply(sql)
        assert "CURRENT_TIMESTAMP" in result


class TestSYSTIMESTAMPRule:
    rule = SYSTIMESTAMPRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT SYSTIMESTAMP FROM DUAL")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT SYSDATE FROM DUAL")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT SYSTIMESTAMP FROM DUAL")
        assert "clock_timestamp()" in result


class TestADDMONTHSRule:
    rule = ADDMONTHSRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT ADD_MONTHS(hire_date, 6) FROM emp")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT hire_date FROM emp")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT ADD_MONTHS(hire_date, 6) FROM emp")
        assert "hire_date + (6 || ' months')::interval" in result

    def test_apply_negative(self) -> None:
        result = self.rule.apply("SELECT ADD_MONTHS(SYSDATE, -3) FROM DUAL")
        assert "SYSDATE + (-3 || ' months')::interval" in result


class TestLASTDAYRule:
    rule = LASTDAYRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT LAST_DAY(hire_date) FROM emp")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT LAST_DAY(hire_date) FROM emp")
        assert "DATE_TRUNC('month', hire_date)" in result
        assert "INTERVAL '1 month - 1 day'" in result
        assert "::date" in result


class TestTRUNCDateRule:
    rule = TRUNCDateRule()

    def test_matches_bare(self) -> None:
        assert self.rule.matches("SELECT TRUNC(hire_date) FROM emp")

    def test_matches_with_format(self) -> None:
        assert self.rule.matches("SELECT TRUNC(hire_date, 'MM') FROM emp")

    def test_apply_bare(self) -> None:
        result = self.rule.apply("SELECT TRUNC(hire_date) FROM emp")
        assert "DATE_TRUNC('day', hire_date)" in result

    def test_apply_month(self) -> None:
        result = self.rule.apply("SELECT TRUNC(hire_date, 'MM') FROM emp")
        assert "DATE_TRUNC('month', hire_date)" in result

    def test_apply_year(self) -> None:
        result = self.rule.apply("SELECT TRUNC(created_at, 'YYYY') FROM t")
        assert "DATE_TRUNC('year', created_at)" in result

    def test_skips_numeric_trunc(self) -> None:
        # Plain numeric argument should be left alone
        result = self.rule.apply("SELECT TRUNC(123.45) FROM t")
        assert result == "SELECT TRUNC(123.45) FROM t"


class TestDateArithmeticRule:
    rule = DateArithmeticRule()

    def test_matches_date_column(self) -> None:
        assert self.rule.matches("SELECT hire_date + 7 FROM emp")

    def test_no_match_plain_number(self) -> None:
        assert not self.rule.matches("SELECT price + 7 FROM products")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT hire_date + 7 FROM emp")
        assert "hire_date + interval '7 days'" in result

    def test_apply_current_timestamp(self) -> None:
        result = self.rule.apply("SELECT CURRENT_TIMESTAMP + 30 FROM t")
        assert "CURRENT_TIMESTAMP + interval '30 days'" in result
