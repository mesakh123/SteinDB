"""Tests for P2O syntax_datetime rules."""

from __future__ import annotations

from steindb.rules.p2o_syntax_datetime import (
    ClockTimestampToSystimestampRule,
    CurrentTimestampToSysdateRule,
    DateIntervalDaysRule,
    DateTruncDayRule,
    DateTruncFmtRule,
    MonthsIntervalToAddMonthsRule,
)


class TestCurrentTimestampToSysdateRule:
    rule = CurrentTimestampToSysdateRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT CURRENT_TIMESTAMP FROM t")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT SYSDATE FROM t")

    def test_no_match_in_string(self) -> None:
        assert not self.rule.matches("SELECT 'CURRENT_TIMESTAMP' FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT CURRENT_TIMESTAMP FROM t")
        assert result == "SELECT SYSDATE FROM t"

    def test_apply_in_insert(self) -> None:
        sql = "INSERT INTO t (created_at) VALUES (CURRENT_TIMESTAMP)"
        result = self.rule.apply(sql)
        assert "SYSDATE" in result
        assert "CURRENT_TIMESTAMP" not in result


class TestClockTimestampToSystimestampRule:
    rule = ClockTimestampToSystimestampRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT clock_timestamp() FROM t")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT SYSTIMESTAMP FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT clock_timestamp() FROM t")
        assert "SYSTIMESTAMP" in result
        assert "clock_timestamp" not in result


class TestDateIntervalDaysRule:
    rule = DateIntervalDaysRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT hire_date + INTERVAL '1 day' FROM t")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT hire_date + 1 FROM t")

    def test_apply_single_day(self) -> None:
        result = self.rule.apply("SELECT hire_date + INTERVAL '1 day' FROM t")
        assert "hire_date + 1" in result
        assert "INTERVAL" not in result

    def test_apply_multiple_days(self) -> None:
        result = self.rule.apply("SELECT start_date + INTERVAL '30 days' FROM t")
        assert "start_date + 30" in result


class TestMonthsIntervalToAddMonthsRule:
    rule = MonthsIntervalToAddMonthsRule()

    def test_matches(self) -> None:
        sql = "SELECT hire_date + (n || ' months')::interval FROM t"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT ADD_MONTHS(d, 3) FROM t")

    def test_apply(self) -> None:
        sql = "SELECT hire_date + (n || ' months')::interval FROM t"
        result = self.rule.apply(sql)
        assert "ADD_MONTHS(hire_date, n)" in result


class TestDateTruncDayRule:
    rule = DateTruncDayRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT DATE_TRUNC('day', created_at) FROM t")

    def test_no_match_month(self) -> None:
        # The 'day' rule should match 'day' specifically
        assert not self.rule.matches("SELECT DATE_TRUNC('month', created_at) FROM t")

    def test_apply(self) -> None:
        result = self.rule.apply("SELECT DATE_TRUNC('day', created_at) FROM t")
        assert "TRUNC(created_at)" in result
        assert "DATE_TRUNC" not in result


class TestDateTruncFmtRule:
    rule = DateTruncFmtRule()

    def test_matches_month(self) -> None:
        assert self.rule.matches("SELECT DATE_TRUNC('month', created_at) FROM t")

    def test_matches_year(self) -> None:
        assert self.rule.matches("SELECT DATE_TRUNC('year', created_at) FROM t")

    def test_no_match_day(self) -> None:
        # 'day' is not in the format map for this rule
        assert not self.rule.matches("SELECT DATE_TRUNC('day', created_at) FROM t")

    def test_apply_month(self) -> None:
        result = self.rule.apply("SELECT DATE_TRUNC('month', created_at) FROM t")
        assert "TRUNC(created_at, 'MM')" in result

    def test_apply_year(self) -> None:
        result = self.rule.apply("SELECT DATE_TRUNC('year', created_at) FROM t")
        assert "TRUNC(created_at, 'YYYY')" in result

    def test_apply_quarter(self) -> None:
        result = self.rule.apply("SELECT DATE_TRUNC('quarter', d) FROM t")
        assert "TRUNC(d, 'Q')" in result

    def test_apply_week(self) -> None:
        result = self.rule.apply("SELECT DATE_TRUNC('week', d) FROM t")
        assert "TRUNC(d, 'IW')" in result
