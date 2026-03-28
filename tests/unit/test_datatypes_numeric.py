# tests/unit/test_datatypes_numeric.py
"""Unit tests for numeric data type conversion rules."""

from __future__ import annotations

from steindb.rules.datatypes_numeric import (
    BINARYDOUBLERule,
    BINARYFLOATRule,
    BooleanDetectionRule,
    FLOATRule,
    NUMBEROptimizationRule,
)

# =============================================================================
# NUMBEROptimizationRule
# =============================================================================


class TestNUMBEROptimizationRule:
    rule = NUMBEROptimizationRule()

    # --- matches ---
    def test_matches_number_bare(self) -> None:
        assert self.rule.matches("CREATE TABLE t (val NUMBER)")

    def test_matches_number_with_precision(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id NUMBER(9))")

    def test_matches_number_with_scale(self) -> None:
        assert self.rule.matches("CREATE TABLE t (price NUMBER(10,2))")

    def test_matches_number_star(self) -> None:
        assert self.rule.matches("CREATE TABLE t (val NUMBER(*))")

    def test_no_match_varchar(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR(100))")

    # --- apply: SMALLINT (1-4, 0) ---
    def test_apply_number_1_to_smallint(self) -> None:
        sql = "CREATE TABLE t (flag NUMBER(1))"
        assert self.rule.apply(sql) == "CREATE TABLE t (flag SMALLINT)"

    def test_apply_number_2_to_smallint(self) -> None:
        sql = "CREATE TABLE t (priority NUMBER(2))"
        assert self.rule.apply(sql) == "CREATE TABLE t (priority SMALLINT)"

    def test_apply_number_4_to_smallint(self) -> None:
        sql = "CREATE TABLE t (code NUMBER(4))"
        assert self.rule.apply(sql) == "CREATE TABLE t (code SMALLINT)"

    def test_apply_number_4_0_to_smallint(self) -> None:
        sql = "CREATE TABLE t (status NUMBER(4,0))"
        assert self.rule.apply(sql) == "CREATE TABLE t (status SMALLINT)"

    # --- apply: INTEGER (5-9, 0) ---
    def test_apply_number_5_to_integer(self) -> None:
        sql = "CREATE TABLE t (zip_code NUMBER(5))"
        assert self.rule.apply(sql) == "CREATE TABLE t (zip_code INTEGER)"

    def test_apply_number_9_to_integer(self) -> None:
        sql = "CREATE TABLE t (id NUMBER(9))"
        assert self.rule.apply(sql) == "CREATE TABLE t (id INTEGER)"

    # --- apply: BIGINT (10-18, 0) ---
    def test_apply_number_10_to_bigint(self) -> None:
        sql = "CREATE TABLE t (account_id NUMBER(10))"
        assert self.rule.apply(sql) == "CREATE TABLE t (account_id BIGINT)"

    def test_apply_number_18_to_bigint(self) -> None:
        sql = "CREATE TABLE t (big_ref NUMBER(18))"
        assert self.rule.apply(sql) == "CREATE TABLE t (big_ref BIGINT)"

    # --- apply: NUMERIC(p) for 19+ ---
    def test_apply_number_19_to_numeric(self) -> None:
        sql = "CREATE TABLE t (huge_id NUMBER(19))"
        assert self.rule.apply(sql) == "CREATE TABLE t (huge_id NUMERIC(19))"

    def test_apply_number_38_to_numeric(self) -> None:
        sql = "CREATE TABLE t (oracle_max NUMBER(38))"
        assert self.rule.apply(sql) == "CREATE TABLE t (oracle_max NUMERIC(38))"

    # --- apply: NUMERIC(p,s) for scale > 0 ---
    def test_apply_number_10_2_to_numeric(self) -> None:
        sql = "CREATE TABLE t (price NUMBER(10,2))"
        assert self.rule.apply(sql) == "CREATE TABLE t (price NUMERIC(10,2))"

    def test_apply_number_5_3_to_numeric(self) -> None:
        sql = "CREATE TABLE t (rate NUMBER(5,3))"
        assert self.rule.apply(sql) == "CREATE TABLE t (rate NUMERIC(5,3))"

    # --- apply: bare NUMBER → NUMERIC ---
    def test_apply_number_bare_to_numeric(self) -> None:
        sql = "CREATE TABLE t (val NUMBER)"
        assert self.rule.apply(sql) == "CREATE TABLE t (val NUMERIC)"

    # --- apply: NUMBER(*) → NUMERIC ---
    def test_apply_number_star_to_numeric(self) -> None:
        sql = "CREATE TABLE t (val NUMBER(*))"
        assert self.rule.apply(sql) == "CREATE TABLE t (val NUMERIC)"

    # --- multi-column ---
    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id NUMBER(9), status NUMBER(2), amount NUMBER(10,2), big_ref NUMBER(18))"  # noqa: E501
        expected = (
            "CREATE TABLE t (id INTEGER, status SMALLINT, amount NUMERIC(10,2), big_ref BIGINT)"
        )
        assert self.rule.apply(sql) == expected

    # --- ALTER TABLE ---
    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (count NUMBER(9))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (count INTEGER)"

    # --- default preserved ---
    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (retry_count NUMBER(4) DEFAULT 0)"
        expected = "CREATE TABLE t (retry_count SMALLINT DEFAULT 0)"
        assert self.rule.apply(sql) == expected

    # --- NOT NULL preserved ---
    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (id NUMBER(9) NOT NULL)"
        expected = "CREATE TABLE t (id INTEGER NOT NULL)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# BooleanDetectionRule
# =============================================================================


class TestBooleanDetectionRule:
    rule = BooleanDetectionRule()

    def test_matches_is_prefix(self) -> None:
        assert self.rule.matches("CREATE TABLE t (is_active NUMBER(1,0))")

    def test_matches_has_prefix(self) -> None:
        assert self.rule.matches("CREATE TABLE t (has_access NUMBER(1,0))")

    def test_no_match_no_prefix(self) -> None:
        # flag NUMBER(1,0) without boolean prefix should NOT match
        assert not self.rule.matches("CREATE TABLE t (flag NUMBER(1,0))")

    def test_no_match_number_9(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (is_count NUMBER(9))")

    def test_apply_is_active(self) -> None:
        sql = "CREATE TABLE t (is_active NUMBER(1,0))"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active BOOLEAN)"

    def test_apply_has_access(self) -> None:
        sql = "CREATE TABLE t (has_access NUMBER(1,0))"
        assert self.rule.apply(sql) == "CREATE TABLE t (has_access BOOLEAN)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id NUMBER(9), is_active NUMBER(1,0), has_flag NUMBER(1,0))"
        expected = "CREATE TABLE t (id NUMBER(9), is_active BOOLEAN, has_flag BOOLEAN)"
        assert self.rule.apply(sql) == expected

    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (is_active NUMBER(1,0) DEFAULT 1 NOT NULL)"
        expected = "CREATE TABLE t (is_active BOOLEAN DEFAULT TRUE NOT NULL)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (is_verified NUMBER(1,0))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (is_verified BOOLEAN)"

    def test_matches_can_prefix(self) -> None:
        assert self.rule.matches("CREATE TABLE t (can_edit NUMBER(1,0))")

    def test_apply_number_1_no_scale(self) -> None:
        """NUMBER(1) without explicit ,0 should also be detected for boolean prefixes."""
        sql = "CREATE TABLE t (is_active NUMBER(1))"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active BOOLEAN)"


# =============================================================================
# FLOATRule
# =============================================================================


class TestFLOATRule:
    rule = FLOATRule()

    def test_matches_float_bare(self) -> None:
        assert self.rule.matches("CREATE TABLE t (ratio FLOAT)")

    def test_matches_float_precision(self) -> None:
        assert self.rule.matches("CREATE TABLE t (ratio FLOAT(24))")

    def test_no_match_binary_float(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (val BINARY_FLOAT)")

    def test_apply_float_bare_to_double(self) -> None:
        sql = "CREATE TABLE t (ratio FLOAT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (ratio DOUBLE PRECISION)"

    def test_apply_float_1_to_real(self) -> None:
        sql = "CREATE TABLE t (ratio FLOAT(1))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ratio REAL)"

    def test_apply_float_24_to_real(self) -> None:
        sql = "CREATE TABLE t (ratio FLOAT(24))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ratio REAL)"

    def test_apply_float_25_to_double(self) -> None:
        sql = "CREATE TABLE t (ratio FLOAT(25))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ratio DOUBLE PRECISION)"

    def test_apply_float_126_to_double(self) -> None:
        sql = "CREATE TABLE t (ratio FLOAT(126))"
        assert self.rule.apply(sql) == "CREATE TABLE t (ratio DOUBLE PRECISION)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a FLOAT, b FLOAT(10))"
        expected = "CREATE TABLE t (a DOUBLE PRECISION, b REAL)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (ratio FLOAT)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (ratio DOUBLE PRECISION)"


# =============================================================================
# BINARYFLOATRule
# =============================================================================


class TestBINARYFLOATRule:
    rule = BINARYFLOATRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (temperature BINARY_FLOAT)")

    def test_no_match_float(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (ratio FLOAT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (temperature BINARY_FLOAT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (temperature REAL)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a BINARY_FLOAT, b BINARY_FLOAT)"
        expected = "CREATE TABLE t (a REAL, b REAL)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (val BINARY_FLOAT)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (val REAL)"


# =============================================================================
# BINARYDOUBLERule
# =============================================================================


class TestBINARYDOUBLERule:
    rule = BINARYDOUBLERule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (distance BINARY_DOUBLE)")

    def test_no_match_binary_float(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (val BINARY_FLOAT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (distance BINARY_DOUBLE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (distance DOUBLE PRECISION)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a BINARY_DOUBLE, b BINARY_DOUBLE)"
        expected = "CREATE TABLE t (a DOUBLE PRECISION, b DOUBLE PRECISION)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (val BINARY_DOUBLE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (val DOUBLE PRECISION)"
