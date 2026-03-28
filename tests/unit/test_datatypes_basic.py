# tests/unit/test_datatypes_basic.py
"""Unit tests for basic data type conversion rules (string and binary types)."""

from __future__ import annotations

from steindb.rules.datatypes_basic import (
    BFILERule,
    BLOBRule,
    CHARRule,
    CLOBRule,
    LONGRAWRule,
    LONGRule,
    NVARCHAR2Rule,
    RAWRule,
    VARCHAR2Rule,
)

# =============================================================================
# VARCHAR2Rule
# =============================================================================


class TestVARCHAR2Rule:
    rule = VARCHAR2Rule()

    def test_matches_simple(self) -> None:
        assert self.rule.matches("CREATE TABLE t (name VARCHAR2(100))")

    def test_matches_byte_semantics(self) -> None:
        assert self.rule.matches("CREATE TABLE t (name VARCHAR2(100 BYTE))")

    def test_matches_char_semantics(self) -> None:
        assert self.rule.matches("CREATE TABLE t (name VARCHAR2(100 CHAR))")

    def test_no_match_varchar(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR(100))")

    def test_no_match_text(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name TEXT)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(100))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR(100))"

    def test_apply_byte(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(100 BYTE))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR(100))"

    def test_apply_char(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(100 CHAR))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR(100))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(100), email VARCHAR2(255 CHAR))"
        expected = "CREATE TABLE t (name VARCHAR(100), email VARCHAR(255))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (name VARCHAR2(200))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (name VARCHAR(200))"

    def test_apply_case_insensitive(self) -> None:
        sql = "CREATE TABLE t (name varchar2(100))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR(100))"

    def test_apply_with_default(self) -> None:
        sql = "CREATE TABLE t (status VARCHAR2(20) DEFAULT 'ACTIVE')"
        expected = "CREATE TABLE t (status VARCHAR(20) DEFAULT 'ACTIVE')"
        assert self.rule.apply(sql) == expected

    def test_apply_with_not_null(self) -> None:
        sql = "CREATE TABLE t (name VARCHAR2(100) NOT NULL)"
        expected = "CREATE TABLE t (name VARCHAR(100) NOT NULL)"
        assert self.rule.apply(sql) == expected


# =============================================================================
# NVARCHAR2Rule
# =============================================================================


class TestNVARCHAR2Rule:
    rule = NVARCHAR2Rule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (name NVARCHAR2(200))")

    def test_no_match_varchar2(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR2(100))")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (name NVARCHAR2(200))"
        assert self.rule.apply(sql) == "CREATE TABLE t (name VARCHAR(200))"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (a NVARCHAR2(50), b NVARCHAR2(100))"
        expected = "CREATE TABLE t (a VARCHAR(50), b VARCHAR(100))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (name NVARCHAR2(200))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (name VARCHAR(200))"


# =============================================================================
# CHARRule
# =============================================================================


class TestCHARRule:
    rule = CHARRule()

    def test_matches_nchar(self) -> None:
        assert self.rule.matches("CREATE TABLE t (code NCHAR(10))")

    def test_no_match_char(self) -> None:
        # CHAR(n) stays CHAR(n) — we only match NCHAR
        assert not self.rule.matches("CREATE TABLE t (code CHAR(10))")

    def test_no_match_varchar(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (name VARCHAR(100))")

    def test_apply_nchar(self) -> None:
        sql = "CREATE TABLE t (code NCHAR(10))"
        assert self.rule.apply(sql) == "CREATE TABLE t (code CHAR(10))"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a NCHAR(5), b NCHAR(10))"
        expected = "CREATE TABLE t (a CHAR(5), b CHAR(10))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (code NCHAR(20))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (code CHAR(20))"


# =============================================================================
# CLOBRule
# =============================================================================


class TestCLOBRule:
    rule = CLOBRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (content CLOB)")

    def test_no_match_blob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (content BLOB)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (content CLOB)"
        assert self.rule.apply(sql) == "CREATE TABLE t (content TEXT)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (a CLOB, name VARCHAR(50), b CLOB)"
        expected = "CREATE TABLE t (a TEXT, name VARCHAR(50), b TEXT)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (notes CLOB)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (notes TEXT)"


# =============================================================================
# LONGRule
# =============================================================================


class TestLONGRule:
    rule = LONGRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (description LONG)")

    def test_no_match_long_raw(self) -> None:
        # Must not match LONG RAW (separate rule)
        assert not self.rule.matches("CREATE TABLE t (image LONG RAW)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (description LONG)"
        assert self.rule.apply(sql) == "CREATE TABLE t (description TEXT)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (id NUMBER(9), description LONG)"
        expected = "CREATE TABLE t (id NUMBER(9), description TEXT)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (description LONG)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (description TEXT)"


# =============================================================================
# BLOBRule
# =============================================================================


class TestBLOBRule:
    rule = BLOBRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (photo BLOB)")

    def test_no_match_clob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (content CLOB)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (photo BLOB)"
        assert self.rule.apply(sql) == "CREATE TABLE t (photo BYTEA)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a BLOB, name VARCHAR(50), b BLOB)"
        expected = "CREATE TABLE t (a BYTEA, name VARCHAR(50), b BYTEA)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (data BLOB)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (data BYTEA)"


# =============================================================================
# RAWRule
# =============================================================================


class TestRAWRule:
    rule = RAWRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (hash RAW(32))")

    def test_matches_raw_16(self) -> None:
        assert self.rule.matches("CREATE TABLE t (guid RAW(16))")

    def test_no_match_long_raw(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (image LONG RAW)")

    def test_apply_raw_32_to_bytea(self) -> None:
        sql = "CREATE TABLE t (hash RAW(32))"
        assert self.rule.apply(sql) == "CREATE TABLE t (hash BYTEA)"

    def test_apply_raw_16_to_uuid(self) -> None:
        sql = "CREATE TABLE t (guid RAW(16))"
        assert self.rule.apply(sql) == "CREATE TABLE t (guid UUID)"

    def test_apply_multi_column(self) -> None:
        sql = "CREATE TABLE t (guid RAW(16), hash RAW(32))"
        expected = "CREATE TABLE t (guid UUID, hash BYTEA)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (token RAW(64))"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (token BYTEA)"


# =============================================================================
# BFILERule
# =============================================================================


class TestBFILERule:
    rule = BFILERule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (attachment BFILE)")

    def test_no_match_blob(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (data BLOB)")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (attachment BFILE)"
        assert self.rule.apply(sql) == "CREATE TABLE t (attachment BYTEA)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a BFILE, b BFILE)"
        expected = "CREATE TABLE t (a BYTEA, b BYTEA)"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (doc BFILE)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (doc BYTEA)"


# =============================================================================
# LONGRAWRule
# =============================================================================


class TestLONGRAWRule:
    rule = LONGRAWRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE TABLE t (image LONG RAW)")

    def test_no_match_long(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (description LONG)")

    def test_no_match_raw(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (hash RAW(32))")

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE t (image LONG RAW)"
        assert self.rule.apply(sql) == "CREATE TABLE t (image BYTEA)"

    def test_apply_multi(self) -> None:
        sql = "CREATE TABLE t (a LONG RAW, name VARCHAR(50))"
        expected = "CREATE TABLE t (a BYTEA, name VARCHAR(50))"
        assert self.rule.apply(sql) == expected

    def test_apply_alter_table(self) -> None:
        sql = "ALTER TABLE t ADD (data LONG RAW)"
        assert self.rule.apply(sql) == "ALTER TABLE t ADD (data BYTEA)"
