# src/steindb/rules/datatypes_numeric.py
"""Numeric data type conversion rules.

Converts Oracle numeric types to PostgreSQL equivalents:
  NUMBER(p,s) -> SMALLINT/INTEGER/BIGINT/NUMERIC depending on precision/scale,
  FLOAT -> DOUBLE PRECISION/REAL, BINARY_FLOAT -> REAL,
  BINARY_DOUBLE -> DOUBLE PRECISION.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class BooleanDetectionRule(Rule):
    """Detect NUMBER(1,0) or NUMBER(1) columns with boolean-like names.

    Columns named with is_, has_, or can_ prefix and NUMBER(1,0) or NUMBER(1)
    type are converted to BOOLEAN. Also converts DEFAULT 1/0 to DEFAULT TRUE/FALSE.

    Runs BEFORE NUMBEROptimizationRule to claim boolean columns first.
    """

    name = "boolean_detection"
    category = RuleCategory.DATATYPES_NUMERIC
    priority = 5  # Before NUMBEROptimizationRule
    description = "Convert NUMBER(1,0) with boolean-like names to BOOLEAN"

    # Match column_name NUMBER(1) or NUMBER(1,0) where column_name starts with is_/has_/can_
    _pattern = re.compile(
        r"\b((?:is|has|can)_\w+)\s+NUMBER\s*\(\s*1\s*(?:,\s*0\s*)?\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        result = self._pattern.sub(r"\1 BOOLEAN", sql)
        # Convert DEFAULT 1/0 after BOOLEAN to DEFAULT TRUE/FALSE
        result = re.sub(
            r"(BOOLEAN\s+DEFAULT\s+)1\b",
            r"\1TRUE",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(BOOLEAN\s+DEFAULT\s+)0\b",
            r"\1FALSE",
            result,
            flags=re.IGNORECASE,
        )
        return result


class NUMBEROptimizationRule(Rule):
    """Convert NUMBER(p,s) to the optimal PostgreSQL integer/numeric type.

    Mapping:
      NUMBER (bare)     -> NUMERIC
      NUMBER(*)         -> NUMERIC
      NUMBER(1-4, 0)    -> SMALLINT
      NUMBER(5-9, 0)    -> INTEGER
      NUMBER(10-18, 0)  -> BIGINT
      NUMBER(19+, 0)    -> NUMERIC(p)
      NUMBER(p, s>0)    -> NUMERIC(p, s)
      NUMBER(p) (no s)  -> treated as NUMBER(p, 0)
    """

    name = "number_optimization"
    category = RuleCategory.DATATYPES_NUMERIC
    priority = 10
    description = "Convert NUMBER(p,s) to optimal PostgreSQL type"

    # Match NUMBER with optional precision/scale
    _pattern_with_args = re.compile(
        r"\bNUMBER\s*\(\s*(\*|\d+)\s*(?:,\s*(\d+)\s*)?\)",
        re.IGNORECASE,
    )
    _pattern_bare = re.compile(
        r"\bNUMBER\b(?!\s*\()",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern_with_args.search(sql) or self._pattern_bare.search(sql))

    def apply(self, sql: str) -> str:
        def _replace_with_args(m: re.Match[str]) -> str:
            precision_str = m.group(1)
            scale_str = m.group(2)

            # NUMBER(*) -> NUMERIC
            if precision_str == "*":
                return "NUMERIC"

            precision = int(precision_str)
            scale = int(scale_str) if scale_str is not None else 0

            # With scale > 0 -> NUMERIC(p,s)
            if scale > 0:
                return f"NUMERIC({precision},{scale})"

            # Integer optimization based on precision
            if 1 <= precision <= 4:
                return "SMALLINT"
            elif 5 <= precision <= 9:
                return "INTEGER"
            elif 10 <= precision <= 18:
                return "BIGINT"
            else:
                return f"NUMERIC({precision})"

        result = self._pattern_with_args.sub(_replace_with_args, sql)
        result = self._pattern_bare.sub("NUMERIC", result)
        return result


class FLOATRule(Rule):
    """Convert FLOAT to PostgreSQL floating-point type.

    FLOAT (bare)      -> DOUBLE PRECISION
    FLOAT(1-24)       -> REAL
    FLOAT(25-126)     -> DOUBLE PRECISION
    """

    name = "float_to_pg_float"
    category = RuleCategory.DATATYPES_NUMERIC
    priority = 20
    description = "Convert FLOAT to REAL or DOUBLE PRECISION"

    # Match FLOAT with optional precision, but NOT BINARY_FLOAT
    _pattern_with_precision = re.compile(
        r"(?<!\w)FLOAT\s*\(\s*(\d+)\s*\)",
        re.IGNORECASE,
    )
    _pattern_bare = re.compile(
        r"(?<!\w)FLOAT\b(?!\s*\()",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern_with_precision.search(sql) or self._pattern_bare.search(sql))

    def apply(self, sql: str) -> str:
        def _replace_precision(m: re.Match[str]) -> str:
            precision = int(m.group(1))
            if 1 <= precision <= 24:
                return "REAL"
            return "DOUBLE PRECISION"

        result = self._pattern_with_precision.sub(_replace_precision, sql)
        result = self._pattern_bare.sub("DOUBLE PRECISION", result)
        return result


class BINARYFLOATRule(Rule):
    """Convert BINARY_FLOAT to REAL (float4)."""

    name = "binary_float_to_real"
    category = RuleCategory.DATATYPES_NUMERIC
    priority = 30
    description = "Convert BINARY_FLOAT to REAL"

    _pattern = re.compile(r"\bBINARY_FLOAT\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("REAL", sql)


class BINARYDOUBLERule(Rule):
    """Convert BINARY_DOUBLE to DOUBLE PRECISION (float8)."""

    name = "binary_double_to_double_precision"
    category = RuleCategory.DATATYPES_NUMERIC
    priority = 31
    description = "Convert BINARY_DOUBLE to DOUBLE PRECISION"

    _pattern = re.compile(r"\bBINARY_DOUBLE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("DOUBLE PRECISION", sql)
