# tests/unit/test_p2o_datatypes_basic.py
"""Unit tests for P2O basic data type conversion rules (string, binary, special types)."""

from __future__ import annotations

from steindb.rules.base import RuleCategory
from steindb.rules.p2o_datatypes_basic import (
    P2O_BOOLEANRule,
    P2O_BYTEARule,
    P2O_JSONBRule,
    P2O_TEXTRule,
    P2O_UUIDRule,
    P2O_VARCHARRule,
    P2O_XMLRule,
)

# =============================================================================
# P2O_VARCHARRule
# =============================================================================


class TestP2O_VARCHARRule:  # noqa: N801
    rule = P2O_VARCHARRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches_simple(self) -> None:
        assert self.rule.matches("CREATE TABLE t (name VARCHAR(100))")

    def test_no_match_varchar2(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR2(100))")

    def test_no_match_text(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name TEXT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR(100))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR2(100))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR(100), email VARCHAR(255))"
        expected = "CREATE TABLE t (name VARCHAR2(100), email VARCHAR2(255))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (name VARCHAR(200))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (name VARCHAR2(200))"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (name varchar(100))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR2(100))"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR(100) NOT NULL)"
        expected = "CREATE TABLE t (name VARCHAR2(100) NOT NULL)"
        assert self.rule.apply(sql) == expected

    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (status VARCHAR(20) DEFAULT 'ACTIVE')"
        expected = "CREATE TABLE t (status VARCHAR2(20) DEFAULT 'ACTIVE')"
        assert self.rule.apply(sql) == expected


# =============================================================================
# P2O_TEXTRule
# =============================================================================


class TestP2O_TEXTRule:  # noqa: N801
    rule = P2O_TEXTRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (content TEXT)")

    def test_no_match_varchar(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR(100))")

    def test_no_match_clob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (content CLOB)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (content TEXT)"
        assert self.rule.apply(sql) == "CREATE TABLE t (content CLOB)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (a TEXT, name VARCHAR(50), b TEXT)"
        expected = "CREATE TABLE t (a CLOB, name VARCHAR(50), b CLOB)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (notes TEXT)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (notes CLOB)"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (content text)"
        assert self.rule.apply(sql) == "CREATE TABLE t (content CLOB)"


# =============================================================================
# P2O_BYTEARule
# =============================================================================


class TestP2O_BYTEARule:  # noqa: N801
    rule = P2O_BYTEARule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (photo BYTEA)")

    def test_no_match_blob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (photo BLOB)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (photo BYTEA)"
        assert self.rule.apply(sql) == "CREATE TABLE t (photo BLOB)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a BYTEA, name VARCHAR(50), b BYTEA)"
        expected = "CREATE TABLE t (a BLOB, name VARCHAR(50), b BLOB)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (data BYTEA)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (data BLOB)"


# =============================================================================
# P2O_UUIDRule
# =============================================================================


class TestP2O_UUIDRule:  # noqa: N801
    rule = P2O_UUIDRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id UUID)")

    def test_no_match_raw(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id RAW(16))")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (id UUID)"
        assert self.rule.apply(sql) == "CREATE TABLE t (id RAW(16))"

    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (id UUID DEFAULT gen_random_uuid())"
        expected = "CREATE TABLE t (id RAW(16) DEFAULT gen_random_uuid())"
        assert self.rule.apply(sql) == expected

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id UUID, ref_id UUID)"
        expected = "CREATE TABLE t (id RAW(16), ref_id RAW(16))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (guid UUID)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (guid RAW(16))"


# =============================================================================
# P2O_XMLRule
# =============================================================================


class TestP2O_XMLRule:  # noqa: N801
    rule = P2O_XMLRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (config XML)")

    def test_no_match_xmltype(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (config XMLTYPE)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (config XML)"
        assert self.rule.apply(sql) == "CREATE TABLE t (config XMLTYPE)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a XML, b XML)"
        expected = "CREATE TABLE t (a XMLTYPE, b XMLTYPE)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (metadata XML)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (metadata XMLTYPE)"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (config xml)"
        assert self.rule.apply(sql) == "CREATE TABLE t (config XMLTYPE)"


# =============================================================================
# P2O_JSONBRule
# =============================================================================


class TestP2O_JSONBRule:  # noqa: N801
    rule = P2O_JSONBRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches_jsonb(self) -> None:
        assert self.rule.matches("CREATE TABLE t (data JSONB)")

    def test_matches_json(self) -> None:
        assert self.rule.matches("CREATE TABLE t (data JSON)")

    def test_no_match_text(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (data TEXT)")

    def test_no_match_clob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (data CLOB)")

    def test_apply_jsonb(self) -> None:
        sql = "CREATE TABLE t (data JSONB)"
        result = self.rule.apply(sql)
        assert "CLOB" in result
        assert "WARNING" in result
        assert "JSONB" in result
        assert "Oracle 21c" in result

    def test_apply_json(self) -> None:
        sql = "CREATE TABLE t (data JSON)"
        result = self.rule.apply(sql)
        assert "CLOB" in result
        assert "WARNING" in result
        assert "JSON" in result
        assert "Oracle 21c" in result

    def test_apply_jsonb_preserves_context(self) -> None:
        sql = "CREATE TABLE t (id INTEGER, data JSONB NOT NULL)"
        result = self.rule.apply(sql)
        assert "id INTEGER" in result
        assert "CLOB" in result
        assert "NOT NULL" in result

    def test_apply_multi_json_types(self) -> None:
        sql = "CREATE TABLE t (meta JSONB, config JSON)"
        result = self.rule.apply(sql)
        # Both should be converted; each replacement produces "CLOB /* ...->CLOB... */"
        assert "JSONB->CLOB" in result
        assert "JSON->CLOB" in result
        assert "JSONB" not in result.replace("JSONB->CLOB", "")
        assert result.startswith("CREATE TABLE t (meta CLOB")

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (payload JSONB)"
        result = self.rule.apply(sql)
        assert "CLOB" in result
        assert "WARNING" in result


# =============================================================================
# P2O_BOOLEANRule
# =============================================================================


class TestP2O_BOOLEANRule:  # noqa: N801
    rule = P2O_BOOLEANRule()

    def test_category(self) -> None:
        assert self.rule.category == RuleCategory.P2O_DATATYPES_BASIC

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (is_active BOOLEAN)")

    def test_no_match_number(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (flag NUMBER(1))")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (is_active BOOLEAN)"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active NUMBER(1))"

    def test_apply_with_default_true(self) -> None:
        sql = "CREATE TABLE t (is_active BOOLEAN DEFAULT TRUE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active NUMBER(1) DEFAULT 1)"

    def test_apply_with_default_false(self) -> None:
        sql = "CREATE TABLE t (is_active BOOLEAN DEFAULT FALSE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active NUMBER(1) DEFAULT 0)"

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (is_active BOOLEAN NOT NULL)"
        assert self.rule.apply(sql) == "CREATE TABLE t (is_active NUMBER(1) NOT NULL)"

    def test_apply_with_default_true_not_null(self) -> None:
        sql = "CREATE TABLE t (is_active BOOLEAN DEFAULT TRUE NOT NULL)"
        expected = "CREATE TABLE t (is_active NUMBER(1) DEFAULT 1 NOT NULL)"
        assert self.rule.apply(sql) == expected

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id INTEGER, is_active BOOLEAN, has_access BOOLEAN)"
        expected = "CREATE TABLE t (id INTEGER, is_active NUMBER(1), has_access NUMBER(1))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (is_verified BOOLEAN)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (is_verified NUMBER(1))"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (active boolean)"
        assert self.rule.apply(sql) == "CREATE TABLE t (active NUMBER(1))"
