# src/steindb/rules/p2o_datatypes_numeric.py
"""PostgreSQL-to-Oracle numeric data type conversion rules.

Converts PostgreSQL numeric types to Oracle equivalents:
  SMALLINT -> NUMBER(5), INTEGER -> NUMBER(10), BIGINT -> NUMBER(19),
  NUMERIC(p,s) -> NUMBER(p,s), NUMERIC -> NUMBER,
  REAL -> BINARY_FLOAT, DOUBLE PRECISION -> BINARY_DOUBLE,
  SERIAL/BIGSERIAL -> NUMBER + SEQUENCE + TRIGGER.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2O_SMALLINTRule(Rule):  # noqa: N801
    """Convert SMALLINT to NUMBER(5).

    Must not match SMALLSERIAL (separate rule).
    """

    name = "p2o_smallint_to_number5"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 10
    description = "Convert SMALLINT to NUMBER(5)"

    _pattern = re.compile(r"\bSMALLINT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("NUMBER(5)", sql)


class P2O_INTEGERRule(Rule):  # noqa: N801
    """Convert INTEGER (INT) to NUMBER(10).

    Must not match BIGINT or SMALLINT (handled by other rules).
    """

    name = "p2o_integer_to_number10"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 11
    description = "Convert INTEGER to NUMBER(10)"

    # Match INTEGER or INT but not BIGINT/SMALLINT
    _pattern = re.compile(
        r"(?<!\w)(?:INTEGER|INT)\b(?!EGER|4|8|2)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("NUMBER(10)", sql)


class P2O_BIGINTRule(Rule):  # noqa: N801
    """Convert BIGINT to NUMBER(19)."""

    name = "p2o_bigint_to_number19"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 9  # Before INTEGERRule to avoid partial match
    description = "Convert BIGINT to NUMBER(19)"

    _pattern = re.compile(r"\bBIGINT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("NUMBER(19)", sql)


class P2O_NUMERICRule(Rule):  # noqa: N801
    """Convert NUMERIC(p,s) to NUMBER(p,s), NUMERIC(p) to NUMBER(p), NUMERIC to NUMBER.

    Also handles DECIMAL as an alias for NUMERIC.
    """

    name = "p2o_numeric_to_number"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 20
    description = "Convert NUMERIC(p,s) to NUMBER(p,s)"

    _pattern_with_args = re.compile(
        r"\b(?:NUMERIC|DECIMAL)\s*\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)",
        re.IGNORECASE,
    )
    _pattern_bare = re.compile(
        r"\b(?:NUMERIC|DECIMAL)\b(?!\s*\()",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern_with_args.search(sql) or self._pattern_bare.search(sql))

    def apply(self, sql: str) -> str:
        def _replace_with_args(m: re.Match[str]) -> str:
            precision = m.group(1)
            scale = m.group(2)
            if scale is not None:
                return f"NUMBER({precision},{scale})"
            return f"NUMBER({precision})"

        result = self._pattern_with_args.sub(_replace_with_args, sql)
        result = self._pattern_bare.sub("NUMBER", result)
        return result


class P2O_REALRule(Rule):  # noqa: N801
    """Convert REAL (float4) to BINARY_FLOAT."""

    name = "p2o_real_to_binary_float"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 30
    description = "Convert REAL to BINARY_FLOAT"

    _pattern = re.compile(r"\bREAL\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BINARY_FLOAT", sql)


class P2O_DOUBLERule(Rule):  # noqa: N801
    """Convert DOUBLE PRECISION (float8) to BINARY_DOUBLE."""

    name = "p2o_double_to_binary_double"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 31
    description = "Convert DOUBLE PRECISION to BINARY_DOUBLE"

    _pattern = re.compile(r"\bDOUBLE\s+PRECISION\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("BINARY_DOUBLE", sql)


class P2O_SERIALRule(Rule):  # noqa: N801
    """Convert SERIAL/BIGSERIAL/SMALLSERIAL to NUMBER + SEQUENCE comment.

    Oracle has no auto-increment column type prior to 12c IDENTITY columns.
    This rule converts the type and adds a comment indicating that a SEQUENCE
    and TRIGGER must be created separately.

    SERIAL -> NUMBER(10), BIGSERIAL -> NUMBER(19), SMALLSERIAL -> NUMBER(5).
    """

    name = "p2o_serial_to_number_sequence"
    category = RuleCategory.P2O_DATATYPES_NUMERIC
    priority = 5  # Before integer rules to claim SERIAL first
    description = "Convert SERIAL/BIGSERIAL to NUMBER + SEQUENCE + TRIGGER"

    _pattern_bigserial = re.compile(r"\bBIGSERIAL\b", re.IGNORECASE)
    _pattern_smallserial = re.compile(r"\bSMALLSERIAL\b", re.IGNORECASE)
    _pattern_serial = re.compile(r"\bSERIAL\b(?![\w])", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(
            self._pattern_bigserial.search(sql)
            or self._pattern_smallserial.search(sql)
            or self._pattern_serial.search(sql)
        )

    def apply(self, sql: str) -> str:
        # Order matters: BIGSERIAL and SMALLSERIAL before SERIAL
        result = self._pattern_bigserial.sub(
            "NUMBER(19) /* TODO: CREATE SEQUENCE + TRIGGER for auto-increment */",
            sql,
        )
        result = self._pattern_smallserial.sub(
            "NUMBER(5) /* TODO: CREATE SEQUENCE + TRIGGER for auto-increment */",
            result,
        )
        result = self._pattern_serial.sub(
            "NUMBER(10) /* TODO: CREATE SEQUENCE + TRIGGER for auto-increment */",
            result,
        )
        return result
