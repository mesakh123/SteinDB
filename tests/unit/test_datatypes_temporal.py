# tests/unit/test_datatypes_temporal.py
"""Unit tests for temporal data type conversion rules."""

from __future__ import annotations

from steindb.rules.datatypes_temporal import (
    DATERule,
    INTERVALDSRule,
    INTERVALYMRule,
    TIMESTAMPLTZRule,
    TIMESTAMPRule,
    TIMESTAMPTZRule,
    XMLTYPERule,
)

# =============================================================================
# DATERule
# =============================================================================


class TestDATERule:
    rule = DATERule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (created DATE)")

    def test_no_match_timestamp(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (created TIMESTAMP(0))")

    def test_no_match_to_date(self) -> None:
        # Should not match TO_DATE function
        assert not self.rule.matches("SELECT TO_DATE('2024-01-01', 'YYYY-MM-DD') FROM DUAL")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (created DATE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (created TIMESTAMP(0))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (start_date DATE, end_date DATE)"
        expected = "CREATE TABLE t (start_date TIMESTAMP(0), end_date TIMESTAMP(0))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (created DATE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (created TIMESTAMP(0))"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (created date)"
        assert self.rule.apply(sql) == "CREATE TABLE t (created TIMESTAMP(0))"

    def test_apply_preserves_default(self) -> None:
        sql = "CREATE TABLE t (created DATE DEFAULT SYSDATE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (created TIMESTAMP(0) DEFAULT SYSDATE)"

    def test_no_match_update_date(self) -> None:
        # Should not match DATE inside string literals
        assert not self.rule.matches("SELECT 'DATE' FROM t")


# =============================================================================
# TIMESTAMPRule
# =============================================================================


class TestTIMESTAMPRule:
    rule = TIMESTAMPRule()

    def test_matches_timestamp(self) -> None:
        assert self.rule.matches("CREATE TABLE t (created_at TIMESTAMP)")

    def test_matches_timestamp_precision(self) -> None:
        assert self.rule.matches("CREATE TABLE t (event_time TIMESTAMP(6))")

    def test_no_match_timestamp_tz(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)")

    def test_no_match_timestamp_ltz(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH LOCAL TIME ZONE)")

    def test_apply_simple(self) -> None:
        # TIMESTAMP stays TIMESTAMP
        sql = "CREATE TABLE t (created_at TIMESTAMP)"
        assert self.rule.apply(sql) == "CREATE TABLE t (created_at TIMESTAMP)"

    def test_apply_with_precision(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP(6))"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMP(6))"

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (created TIMESTAMP(3))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (created TIMESTAMP(3))"


# =============================================================================
# TIMESTAMPTZRule
# =============================================================================


class TestTIMESTAMPTZRule:
    rule = TIMESTAMPTZRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)")

    def test_no_match_timestamp(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP)")

    def test_no_match_ltz(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH LOCAL TIME ZONE)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMPTZ)"

    def test_apply_with_precision(self) -> None:
        sql = "CREATE TABLE t (event_time TIMESTAMP(6) WITH TIME ZONE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (event_time TIMESTAMPTZ)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a TIMESTAMP WITH TIME ZONE, b TIMESTAMP WITH TIME ZONE)"
        expected = "CREATE TABLE t (a TIMESTAMPTZ, b TIMESTAMPTZ)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (event TIMESTAMP WITH TIME ZONE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (event TIMESTAMPTZ)"


# =============================================================================
# TIMESTAMPLTZRule
# =============================================================================


class TestTIMESTAMPLTZRule:
    rule = TIMESTAMPLTZRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (login_time TIMESTAMP WITH LOCAL TIME ZONE)")

    def test_no_match_tz(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (event_time TIMESTAMP WITH TIME ZONE)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (login_time TIMESTAMP WITH LOCAL TIME ZONE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (login_time TIMESTAMPTZ)"

    def test_apply_with_precision(self) -> None:
        sql = "CREATE TABLE t (login_time TIMESTAMP(6) WITH LOCAL TIME ZONE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (login_time TIMESTAMPTZ)"

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (login TIMESTAMP WITH LOCAL TIME ZONE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (login TIMESTAMPTZ)"


# =============================================================================
# INTERVALYMRule
# =============================================================================


class TestINTERVALYMRule:
    rule = INTERVALYMRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (tenure INTERVAL YEAR TO MONTH)")

    def test_no_match_ds(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (duration INTERVAL DAY TO SECOND)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (tenure INTERVAL YEAR TO MONTH)"
        assert self.rule.apply(sql) == "CREATE TABLE t (tenure INTERVAL)"

    def test_apply_with_precision(self) -> None:
        sql = "CREATE TABLE t (tenure INTERVAL YEAR(4) TO MONTH)"
        assert self.rule.apply(sql) == "CREATE TABLE t (tenure INTERVAL)"

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (period INTERVAL YEAR TO MONTH)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (period INTERVAL)"


# =============================================================================
# INTERVALDSRule
# =============================================================================


class TestINTERVALDSRule:
    rule = INTERVALDSRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (duration INTERVAL DAY TO SECOND)")

    def test_no_match_ym(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (tenure INTERVAL YEAR TO MONTH)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (duration INTERVAL DAY TO SECOND)"
        assert self.rule.apply(sql) == "CREATE TABLE t (duration INTERVAL)"

    def test_apply_with_precision(self) -> None:
        sql = "CREATE TABLE t (duration INTERVAL DAY(4) TO SECOND(6))"
        assert self.rule.apply(sql) == "CREATE TABLE t (duration INTERVAL)"

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (wait_time INTERVAL DAY TO SECOND)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (wait_time INTERVAL)"


# =============================================================================
# XMLTYPERule
# =============================================================================


class TestXMLTYPERule:
    rule = XMLTYPERule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (config XMLTYPE)")

    def test_no_match_xml(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (config XML)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (config XMLTYPE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (config XML)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a XMLTYPE, b XMLTYPE)"
        expected = "CREATE TABLE t (a XML, b XML)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (metadata XMLTYPE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (metadata XML)"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (config xmltype)"
        assert self.rule.apply(sql) == "CREATE TABLE t (config XML)"
