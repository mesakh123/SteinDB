# src/steindb/rules/p2o_datatypes_basic.py
"""PostgreSQL-to-Oracle string, binary, and special data type conversion rules.

Converts PostgreSQL string/binary types to Oracle equivalents:
  VARCHAR(n) -> VARCHAR2(n), TEXT -> CLOB,
  BYTEA -> BLOB, UUID -> RAW(16),
  XML -> XMLTYPE, JSONB -> CLOB (lossy), JSON -> CLOB (lossy),
  BOOLEAN -> NUMBER(1).
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2O_VARCHARRule(Rule):  # noqa: N801
    """Convert VARCHAR(n) to VARCHAR2(n).

    Must not match VARCHAR2 (already Oracle type).
    """

    name = "p2o_varchar_to_varchar2"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 10
    description = "Convert VARCHAR(n) to VARCHAR2(n)"

    # Match VARCHAR(n) but NOT VARCHAR2(n) — negative lookahead for digit after VARCHAR
    _pattern = re.compile(
        r"\bVARCHAR\s*\(\s*(\d+)\s*\)(?!\s*2)",
        re.IGNORECASE,
    )
    # Negative lookbehind to ensure we don't match VARCHAR2
    _exclude = re.compile(r"\bVARCHAR2\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        if self._exclude.search(sql):
            # Only match if there's a plain VARCHAR in addition to VARCHAR2
            cleaned = self._exclude.sub("", sql)
            return bool(self._pattern.search(cleaned))
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        # Replace VARCHAR(n) but not VARCHAR2(n)
        # Use a pattern that ensures VARCHAR is not followed by "2"
        pattern = re.compile(
            r"\bVARCHAR(?!2)\s*\(\s*(\d+)\s*\)",
            re.IGNORECASE,
        )
        return pattern.sub(r"VARCHAR2(\1)", sql)


class P2O_BareVARCHARRule(Rule):  # noqa: N801
    """Convert bare VARCHAR (no size) to VARCHAR2.

    In PL/pgSQL function parameters, VARCHAR without size is common.
    """

    name = "p2o_bare_varchar_to_varchar2"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 15
    description = "Convert bare VARCHAR (no size) to VARCHAR2"

    _pattern = re.compile(r"\bVARCHAR(?!2)\b(?!\s*\()", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("VARCHAR2", sql)


class P2O_TEXTRule(Rule):  # noqa: N801
    """Convert TEXT to CLOB.

    PostgreSQL TEXT is effectively unlimited, maps to Oracle CLOB.
    """

    name = "p2o_text_to_clob"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 20
    description = "Convert TEXT to CLOB"

    _pattern = re.compile(r"\bTEXT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("CLOB", sql)


class P2O_BYTEARule(Rule):  # noqa: N801
    """Convert BYTEA to BLOB."""

    name = "p2o_bytea_to_blob"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 30
    description = "Convert BYTEA to BLOB"

    _pattern = re.compile(r"\bBYTEA\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BLOB", sql)


class P2O_UUIDRule(Rule):  # noqa: N801
    """Convert UUID to RAW(16).

    Oracle stores UUIDs as 16-byte RAW values. Use SYS_GUID() for generation.
    """

    name = "p2o_uuid_to_raw16"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 31
    description = "Convert UUID to RAW(16)"

    _pattern = re.compile(r"\bUUID\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("RAW(16)", sql)


class P2O_XMLRule(Rule):  # noqa: N801
    """Convert XML to XMLTYPE."""

    name = "p2o_xml_to_xmltype"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 40
    description = "Convert XML to XMLTYPE"

    # Match XML but not XMLTYPE (already Oracle)
    _pattern = re.compile(r"\bXML\b(?!TYPE)", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("XMLTYPE", sql)


class P2O_JSONBRule(Rule):  # noqa: N801
    """Convert JSONB and JSON to CLOB.

    LOSSY: Oracle CLOB loses native JSON operators (->>, @>, ?).
    Adds a warning comment to the output.
    Also handles plain JSON type.
    """

    name = "p2o_jsonb_to_clob"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 50
    description = "Convert JSONB/JSON to CLOB (lossy — loses native JSON operations)"

    # Single pattern matching both JSONB and JSON (JSONB first via alternation order)
    _pattern = re.compile(r"\bJSONB?\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            matched = m.group(0).upper()
            return (
                f"CLOB /* WARNING: {matched}->CLOB is lossy; native JSON operators lost. "
                f"Oracle 21c+ supports native JSON type — consider using JSON if target >= 21c */"
            )

        return self._pattern.sub(_replace, sql)


class P2O_INETRule(Rule):  # noqa: N801
    """Convert INET and CIDR to VARCHAR2(45).

    Oracle has no native network address type. VARCHAR2(45) accommodates
    the longest possible IPv6 address with CIDR prefix.
    """

    name = "p2o_inet_to_varchar2"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 55
    description = "Convert INET/CIDR to VARCHAR2(45)"

    _pattern = re.compile(r"\b(?:INET|CIDR)\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("VARCHAR2(45)", sql)


class P2O_BOOLEANRule(Rule):  # noqa: N801
    """Convert BOOLEAN to NUMBER(1).

    Oracle has no native BOOLEAN type for table columns.
    TRUE -> 1, FALSE -> 0. Adds CHECK constraint comment.
    """

    name = "p2o_boolean_to_number1"
    category = RuleCategory.P2O_DATATYPES_BASIC
    priority = 5  # Before other rules to claim BOOLEAN first
    description = "Convert BOOLEAN to NUMBER(1) with CHECK constraint"

    _pattern = re.compile(r"\bBOOLEAN\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        # Replace BOOLEAN with NUMBER(1)
        result = self._pattern.sub("NUMBER(1)", sql)
        # Convert DEFAULT TRUE/FALSE to DEFAULT 1/0
        result = re.sub(
            r"(NUMBER\(1\)\s+DEFAULT\s+)TRUE\b",
            r"\g<1>1",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(NUMBER\(1\)\s+DEFAULT\s+)FALSE\b",
            r"\g<1>0",
            result,
            flags=re.IGNORECASE,
        )
        return result
