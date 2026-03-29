# tests/unit/test_p2o_datatypes_temporal.py
"""Unit tests for P2O temporal data type conversion rules."""

from __future__ import annotations

from steindb.rules.base import RuleCategory
from steindb.rules.p2o_datatypes_temporal import (
    P2O_DATERule,
    P2O_INTERVALRule,
    P2O_TIMESTAMPRule,
    P2O_TIMESTAMPTZRule,
)

# =============================================================================
# P2O_TIMESTAMPRule
# =============================================================================


class TestP2O_TIMESTAMPRule:  # noqa: N801
    rule = P2O_TIMESTAMPRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_TEMPORAL

    def test_matches_timestamp(self) -> None:
        assert self.rule.matches("CREATE TABLE t (created_at TIMESTAMP)")

    def test_matches_timestamp_precision(self) -> None:
        assert self.rule.matches("CREATE TABLE t (event_time TIMESTAMP(6))")

    def test_matches_timestamp_0(self) -> None:
        assert self.rule.matches("CREATE TABLE t (created TIMESTAMP(0))")

    def test_no_match_timestamptz(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMPTZ)")

    def test_no_match_date(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (created DATE)")

    def test_apply_timestamp_stays(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP)"
        assert self.rule.apply(sql) == "CREATE TABLE t (created_at TIMESTAMP)"

    def test_apply_timestamp_6_stays(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP(6))"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMP(6))"

    def test_apply_timestamp_0_to_date(self) -> None:
        sql = "CREATE TABLE t (created TIMESTAMP(0))"
        assert self.rule.apply(sql) == "CREATE TABLE t (created DATE)"

    def test_apply_timestamp_3_stays(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP(3))"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMP(3))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (created TIMESTAMP(0), updated TIMESTAMP(6))"
        expected = "CREATE TABLE t (created DATE, updated TIMESTAMP(6))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (created TIMESTAMP(0))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (created DATE)"

    def test_apply_does_not_touch_timestamptz(self) -> None:
        sql = "CREATE TABLE t (a TIMESTAMP, b TIMESTAMPTZ)"
        result = self.rule.apply(sql)
        assert "TIMESTAMPTZ" in result
        assert result.startswith("CREATE TABLE t (a TIMESTAMP, b TIMESTAMPTZ)")


# =============================================================================
# P2O_TIMESTAMPTZRule
# =============================================================================


class TestP2O_TIMESTAMPTZRule:  # noqa: N801
    rule = P2O_TIMESTAMPTZRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_TEMPORAL

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (event_time TIMESTAMPTZ)")

    def test_no_match_timestamp(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP)")

    def test_no_match_timestamp_with_tz(self) -> None:
        # Already Oracle format
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMPTZ)"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a TIMESTAMPTZ, b TIMESTAMPTZ)"
        expected = "CREATE TABLE t (a TIMESTAMP WITH TIME ZONE, b TIMESTAMP WITH TIME ZONE)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (event TIMESTAMPTZ)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (event TIMESTAMP WITH TIME ZONE)"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (created TIMESTAMPTZ NOT NULL)"
        expected = "CREATE TABLE t (created TIMESTAMP WITH TIME ZONE NOT NULL)"
        assert self.rule.apply(sql) == expected

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (event timestamptz)"
        assert self.rule.apply(sql) == "CREATE TABLE t (event TIMESTAMP WITH TIME ZONE)"


# =============================================================================
# P2O_DATERule
# =============================================================================


class TestP2O_DATERule:  # noqa: N801
    rule = P2O_DATERule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_TEMPORAL

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (birth_date DATE)")

    def test_no_match_timestamp(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (created TIMESTAMP)")

    def test_no_match_to_date(self) -> None:
        assert not self.rule.matches("SELECT TO_DATE('2024-01-01', 'YYYY-MM-DD')")

    def test_no_match_string_literal(self) -> None:
        assert not self.rule.matches("SELECT 'DATE' FROM t")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (birth_date DATE)"
        result = self.rule.apply(sql)
        assert "DATE" in result
        assert "WARNING" in result
        assert "no time component" in result

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (start_date DATE, end_date DATE)"
        result = self.rule.apply(sql)
        assert result.count("WARNING") == 2

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (created DATE)"
        result = self.rule.apply(sql)
        assert "DATE" in result
        assert "WARNING" in result

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (created date)"
        result = self.rule.apply(sql)
        assert "WARNING" in result

    def test_apply_preserves_default(self) -> None:
        sql = "CREATE TABLE t (created DATE DEFAULT CURRENT_DATE)"
        result = self.rule.apply(sql)
        assert "DEFAULT CURRENT_DATE" in result
        assert "WARNING" in result

    def test_apply_preserves_string_literal_containing_date(self) -> None:
        """Line 124: exercise the path where string literals are interleaved with SQL parts."""
        sql = "CREATE TABLE t (birth_date DATE DEFAULT '2024-01-01')"
        result = self.rule.apply(sql)
        assert "WARNING" in result
        # The string literal '2024-01-01' should be preserved unchanged
        assert "'2024-01-01'" in result

    def test_apply_string_literal_with_date_word(self) -> None:
        """Ensure DATE inside a string literal is not replaced, but DATE outside is."""
        sql = "CREATE TABLE t (col DATE, label VARCHAR(20) DEFAULT 'DATE_FIELD')"
        result = self.rule.apply(sql)
        # The column type DATE should get the WARNING
        assert "WARNING" in result
        # The string 'DATE_FIELD' should be preserved as-is
        assert "'DATE_FIELD'" in result


# =============================================================================
# P2O_INTERVALRule
# =============================================================================


class TestP2O_INTERVALRule:  # noqa: N801
    rule = P2O_INTERVALRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_TEMPORAL

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (duration INTERVAL)")

    def test_no_match_interval_day_to_second(self) -> None:
        # Already Oracle format
        assert not self.rule.matches("CREATE TABLE t (duration INTERVAL DAY TO SECOND)")

    def test_no_match_interval_year_to_month(self) -> None:
        # Already Oracle format
        assert not self.rule.matches("CREATE TABLE t (tenure INTERVAL YEAR TO MONTH)")

    def test_no_match_timestamp(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (created TIMESTAMP)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (duration INTERVAL)"
        assert self.rule.apply(sql) == "CREATE TABLE t (duration INTERVAL DAY TO SECOND)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (wait_time INTERVAL, cooldown INTERVAL)"
        expected = (
            "CREATE TABLE t (wait_time INTERVAL DAY TO SECOND, cooldown INTERVAL DAY TO SECOND)"
        )
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (timeout INTERVAL)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (timeout INTERVAL DAY TO SECOND)"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (duration INTERVAL NOT NULL)"
        expected = "CREATE TABLE t (duration INTERVAL DAY TO SECOND NOT NULL)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# TIMESTAMP precision validation (from PDF validation 2026-03-28)
# Oracle TIMESTAMP: precision 0-9, default 6
# PG TIMESTAMP: precision 0-6, default 6 (microseconds)
# =============================================================================


class TestTimestampPrecisionValidation:
    """Validate TIMESTAMP precision handling against Oracle/PG PDF specs."""

    rule = P2O_TIMESTAMPRule()

    def test_precision_0_maps_to_date(self) -> None:
        """TIMESTAMP(0) -> DATE: correct per Oracle spec (DATE includes time to seconds)."""
        sql = "CREATE TABLE t (ts TIMESTAMP(0))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ts DATE)"

    def test_precision_1_stays(self) -> None:
        sql = "CREATE TABLE t (ts TIMESTAMP(1))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ts TIMESTAMP(1))"

    def test_precision_3_stays(self) -> None:
        """Millisecond precision valid in both PG (0-6) and Oracle (0-9)."""
        sql = "CREATE TABLE t (ts TIMESTAMP(3))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ts TIMESTAMP(3))"

    def test_precision_6_stays(self) -> None:
        """Default microsecond precision for both PG and Oracle."""
        sql = "CREATE TABLE t (ts TIMESTAMP(6))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ts TIMESTAMP(6))"

    def test_precision_over_9_clamped(self) -> None:
        """Precision > 9 exceeds Oracle max, should be clamped with warning."""
        sql = "CREATE TABLE t (ts TIMESTAMP(12))"
        result = self.rule.apply(sql)
        assert "TIMESTAMP(9)" in result
        assert "WARNING" in result
        assert "clamped" in result
