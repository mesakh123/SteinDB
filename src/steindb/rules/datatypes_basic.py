# src/steindb/rules/datatypes_basic.py
"""String and binary data type conversion rules.

Converts Oracle string/binary types to PostgreSQL equivalents:
  VARCHAR2(n) -> VARCHAR(n), NVARCHAR2(n) -> VARCHAR(n),
  NCHAR(n) -> CHAR(n), CLOB -> TEXT, LONG -> TEXT,
  BLOB -> BYTEA, RAW(n) -> BYTEA (RAW(16) -> UUID),
  BFILE -> BYTEA, LONG RAW -> BYTEA.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class VARCHAR2Rule(Rule):
    """Convert VARCHAR2(n) to VARCHAR(n).

    Handles VARCHAR2(n), VARCHAR2(n BYTE), and VARCHAR2(n CHAR).
    """

    name = "varchar2_to_varchar"
    category = RuleCategory.DATATYPES_BASIC
    priority = 10
    description = "Convert VARCHAR2(n) to VARCHAR(n)"

    _pattern = re.compile(
        r"\bVARCHAR2\s*\(\s*(\d+)\s*(?:BYTE|CHAR)?\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub(r"VARCHAR(\1)", sql)


class NVARCHAR2Rule(Rule):
    """Convert NVARCHAR2(n) to VARCHAR(n).

    PostgreSQL uses UTF-8 natively, so no separate NVARCHAR type is needed.
    """

    name = "nvarchar2_to_varchar"
    category = RuleCategory.DATATYPES_BASIC
    priority = 11
    description = "Convert NVARCHAR2(n) to VARCHAR(n)"

    _pattern = re.compile(
        r"\bNVARCHAR2\s*\(\s*(\d+)\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub(r"VARCHAR(\1)", sql)


class CHARRule(Rule):
    """Convert NCHAR(n) to CHAR(n).

    CHAR(n) stays CHAR(n) in PostgreSQL (no transformation needed).
    NCHAR(n) becomes CHAR(n) since PostgreSQL is Unicode-native.
    """

    name = "nchar_to_char"
    category = RuleCategory.DATATYPES_BASIC
    priority = 12
    description = "Convert NCHAR(n) to CHAR(n)"

    _pattern = re.compile(
        r"\bNCHAR\s*\(\s*(\d+)\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub(r"CHAR(\1)", sql)


class CLOBRule(Rule):
    """Convert CLOB to TEXT.

    PostgreSQL TEXT type is effectively unlimited, same as Oracle CLOB.
    """

    name = "clob_to_text"
    category = RuleCategory.DATATYPES_BASIC
    priority = 20
    description = "Convert CLOB to TEXT"

    _pattern = re.compile(r"\bCLOB\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("TEXT", sql)


class LONGRule(Rule):
    """Convert LONG to TEXT.

    LONG is deprecated in Oracle. Must not match LONG RAW (separate rule).
    """

    name = "long_to_text"
    category = RuleCategory.DATATYPES_BASIC
    priority = 21
    description = "Convert LONG to TEXT"

    # Negative lookahead to avoid matching LONG RAW
    _pattern = re.compile(r"\bLONG\b(?!\s+RAW\b)", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("TEXT", sql)


class BLOBRule(Rule):
    """Convert BLOB to BYTEA."""

    name = "blob_to_bytea"
    category = RuleCategory.DATATYPES_BASIC
    priority = 30
    description = "Convert BLOB to BYTEA"

    _pattern = re.compile(r"\bBLOB\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BYTEA", sql)


class RAWRule(Rule):
    """Convert RAW(n) to BYTEA, with special case RAW(16) to UUID.

    Must not match LONG RAW (separate rule).
    """

    name = "raw_to_bytea_or_uuid"
    category = RuleCategory.DATATYPES_BASIC
    priority = 31
    description = "Convert RAW(n) to BYTEA; RAW(16) to UUID"

    # Negative lookbehind for LONG to avoid matching LONG RAW
    _pattern = re.compile(
        r"(?<!\bLONG\s)\bRAW\s*\(\s*(\d+)\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            size = int(m.group(1))
            if size == 16:
                return "UUID"
            return "BYTEA"

        return self._pattern.sub(_replace, sql)


class BFILERule(Rule):
    """Convert BFILE to BYTEA.

    BFILE is read-only external file reference in Oracle; load content into BYTEA.
    """

    name = "bfile_to_bytea"
    category = RuleCategory.DATATYPES_BASIC
    priority = 32
    description = "Convert BFILE to BYTEA"

    _pattern = re.compile(r"\bBFILE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BYTEA", sql)


class LONGRAWRule(Rule):
    """Convert LONG RAW to BYTEA.

    LONG RAW is deprecated in Oracle. Runs before LONGRule to avoid conflict.
    """

    name = "long_raw_to_bytea"
    category = RuleCategory.DATATYPES_BASIC
    priority = 5  # Before LONGRule to avoid partial match
    description = "Convert LONG RAW to BYTEA"

    _pattern = re.compile(r"\bLONG\s+RAW\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BYTEA", sql)
