# tests/unit/test_p2o_datatypes_numeric.py
"""Unit tests for P2O numeric data type conversion rules."""

from __future__ import annotations

from steindb.rules.base import RuleCategory
from steindb.rules.p2o_datatypes_numeric import (
    P2O_BIGINTRule,
    P2O_DOUBLERule,
    P2O_INTEGERRule,
    P2O_NUMERICRule,
    P2O_REALRule,
    P2O_SERIALRule,
    P2O_SMALLINTRule,
)

# =============================================================================
# P2O_SMALLINTRule
# =============================================================================


class TestP2O_SMALLINTRule:  # noqa: N801
    rule = P2O_SMALLINTRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (priority SMALLINT)")

    def test_no_match_integer(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_no_match_bigint(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id BIGINT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (priority SMALLINT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (priority NUMBER(5))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (a SMALLINT, b SMALLINT)"
        expected = "CREATE TABLE t (a NUMBER(5), b NUMBER(5))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (code SMALLINT)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (code NUMBER(5))"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (status SMALLINT NOT NULL)"
        expected = "CREATE TABLE t (status NUMBER(5) NOT NULL)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# P2O_INTEGERRule
# =============================================================================


class TestP2O_INTEGERRule:  # noqa: N801
    rule = P2O_INTEGERRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches_integer(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_matches_int(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INT)")

    def test_no_match_bigint(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id BIGINT)")

    def test_no_match_smallint(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id SMALLINT)")

    def test_apply_integer(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert self.rule.apply(sql) == "CREATE TABLE t (id NUMBER(10))"

    def test_apply_int(self) -> None:
        sql = "CREATE TABLE t (id INT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (id NUMBER(10))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id INTEGER, count INTEGER)"
        expected = "CREATE TABLE t (id NUMBER(10), count NUMBER(10))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (count INTEGER)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (count NUMBER(10))"

    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (retry_count INTEGER DEFAULT 0)"
        expected = "CREATE TABLE t (retry_count NUMBER(10) DEFAULT 0)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# P2O_BIGINTRule
# =============================================================================


class TestP2O_BIGINTRule:  # noqa: N801
    rule = P2O_BIGINTRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (big_ref BIGINT)")

    def test_no_match_integer(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_no_match_smallint(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id SMALLINT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (big_ref BIGINT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (big_ref NUMBER(19))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (a BIGINT, b BIGINT)"
        expected = "CREATE TABLE t (a NUMBER(19), b NUMBER(19))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (account_id BIGINT)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (account_id NUMBER(19))"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (id BIGINT NOT NULL)"
        expected = "CREATE TABLE t (id NUMBER(19) NOT NULL)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# P2O_NUMERICRule
# =============================================================================


class TestP2O_NUMERICRule:  # noqa: N801
    rule = P2O_NUMERICRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches_numeric_bare(self) -> None:
        assert self.rule.matches("CREATE TABLE t (val NUMERIC)")

    def test_matches_numeric_precision(self) -> None:
        assert self.rule.matches("CREATE TABLE t (val NUMERIC(10))")

    def test_matches_numeric_precision_scale(self) -> None:
        assert self.rule.matches("CREATE TABLE t (price NUMERIC(10,2))")

    def test_matches_decimal(self) -> None:
        assert self.rule.matches("CREATE TABLE t (price DECIMAL(10,2))")

    def test_no_match_integer(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_bare_to_number(self) -> None:
        sql = "CREATE TABLE t (val NUMERIC)"
        assert self.rule.apply(sql) == "CREATE TABLE t (val NUMBER)"

    def test_apply_precision_to_number(self) -> None:
        sql = "CREATE TABLE t (val NUMERIC(10))"
        assert self.rule.apply(sql) == "CREATE TABLE t (val NUMBER(10))"

    def test_apply_precision_scale_to_number(self) -> None:
        sql = "CREATE TABLE t (price NUMERIC(10,2))"
        assert self.rule.apply(sql) == "CREATE TABLE t (price NUMBER(10,2))"

    def test_apply_decimal_to_number(self) -> None:
        sql = "CREATE TABLE t (price DECIMAL(10,2))"
        assert self.rule.apply(sql) == "CREATE TABLE t (price NUMBER(10,2))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (amount NUMERIC(10,2), rate NUMERIC(5,3), val NUMERIC)"
        expected = "CREATE TABLE t (amount NUMBER(10,2), rate NUMBER(5,3), val NUMBER)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (balance NUMERIC(15,2))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (balance NUMBER(15,2))"

    def test_apply_high_precision(self) -> None:
        sql = "CREATE TABLE t (precise_val NUMERIC(38,10))"
        assert self.rule.apply(sql) == "CREATE TABLE t (precise_val NUMBER(38,10))"


# =============================================================================
# P2O_REALRule
# =============================================================================


class TestP2O_REALRule:  # noqa: N801
    rule = P2O_REALRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (temperature REAL)")

    def test_no_match_double(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (val DOUBLE PRECISION)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (temperature REAL)"
        assert self.rule.apply(sql) == "CREATE TABLE t (temperature BINARY_FLOAT)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a REAL, b REAL)"
        expected = "CREATE TABLE t (a BINARY_FLOAT, b BINARY_FLOAT)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (ratio REAL)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (ratio BINARY_FLOAT)"


# =============================================================================
# P2O_DOUBLERule
# =============================================================================


class TestP2O_DOUBLERule:  # noqa: N801
    rule = P2O_DOUBLERule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (distance DOUBLE PRECISION)")

    def test_no_match_real(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (val REAL)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (distance DOUBLE PRECISION)"
        assert self.rule.apply(sql) == "CREATE TABLE t (distance BINARY_DOUBLE)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a DOUBLE PRECISION, b DOUBLE PRECISION)"
        expected = "CREATE TABLE t (a BINARY_DOUBLE, b BINARY_DOUBLE)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (val DOUBLE PRECISION)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (val BINARY_DOUBLE)"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (val double precision)"
        assert self.rule.apply(sql) == "CREATE TABLE t (val BINARY_DOUBLE)"


# =============================================================================
# P2O_SERIALRule
# =============================================================================


class TestP2O_SERIALRule:  # noqa: N801
    rule = P2O_SERIALRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_NUMERIC

    def test_matches_serial(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id SERIAL)")

    def test_matches_bigserial(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id BIGSERIAL)")

    def test_matches_smallserial(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id SMALLSERIAL)")

    def test_no_match_integer(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_serial(self) -> None:
        sql = "CREATE TABLE t (id SERIAL)"
        result = self.rule.apply(sql)
        assert "NUMBER(10)" in result
        assert "SEQUENCE" in result
        assert "TRIGGER" in result

    def test_apply_bigserial(self) -> None:
        sql = "CREATE TABLE t (id BIGSERIAL)"
        result = self.rule.apply(sql)
        assert "NUMBER(19)" in result
        assert "SEQUENCE" in result

    def test_apply_smallserial(self) -> None:
        sql = "CREATE TABLE t (id SMALLSERIAL)"
        result = self.rule.apply(sql)
        assert "NUMBER(5)" in result
        assert "SEQUENCE" in result

    def test_apply_serial_primary_key(self) -> None:
        sql = "CREATE TABLE t (id SERIAL PRIMARY KEY)"
        result = self.rule.apply(sql)
        assert "NUMBER(10)" in result
        assert "PRIMARY KEY" in result

    def test_apply_bigserial_not_null(self) -> None:
        sql = "CREATE TABLE t (id BIGSERIAL NOT NULL)"
        result = self.rule.apply(sql)
        assert "NUMBER(19)" in result
        assert "NOT NULL" in result

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (seq_id SERIAL)"
        result = self.rule.apply(sql)
        assert "NUMBER(10)" in result
        assert "SEQUENCE" in result
