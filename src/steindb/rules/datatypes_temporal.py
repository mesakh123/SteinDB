# src/steindb/rules/datatypes_temporal.py
"""Temporal (date/time) and XML data type conversion rules.

Converts Oracle temporal types to PostgreSQL equivalents:
  DATE -> TIMESTAMP(0) (Oracle DATE includes time to the second!),
  TIMESTAMP -> TIMESTAMP, TIMESTAMP(p) -> TIMESTAMP(p),
  TIMESTAMP WITH TIME ZONE -> TIMESTAMPTZ,
  TIMESTAMP WITH LOCAL TIME ZONE -> TIMESTAMPTZ,
  INTERVAL YEAR TO MONTH -> INTERVAL,
  INTERVAL DAY TO SECOND -> INTERVAL,
  XMLTYPE -> XML.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class DATERule(Rule):
    """Convert Oracle DATE to PostgreSQL TIMESTAMP(0).

    Oracle DATE includes a time component (down to the second, no fractional
    seconds), so it must map to TIMESTAMP(0), not PostgreSQL DATE (which is
    date-only) and not TIMESTAMP (which defaults to microsecond precision).

    Must not match:
    - TO_DATE function calls
    - DATE inside string literals
    - SYSDATE, UPDATE_DATE etc. (word boundary handles this)
    """

    name = "date_to_timestamp"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 10
    description = "Convert DATE to TIMESTAMP(0) (Oracle DATE includes time to the second)"

    # Match DATE as a standalone type keyword, not preceded by TO_ or other prefixes
    # and not followed by other type-related words.
    # Use negative lookbehind for TO_, and word boundary.
    _pattern = re.compile(
        r"(?<![A-Za-z_])DATE\b(?!\s*\()",
        re.IGNORECASE,
    )

    # Pattern to detect if the match is inside a string literal
    _string_literal = re.compile(r"'[^']*'")

    def matches(self, sql: str) -> bool:
        # Remove string literals before checking
        cleaned = self._string_literal.sub("", sql)
        return bool(self._pattern.search(cleaned))

    def apply(self, sql: str) -> str:
        # We need to avoid replacing DATE inside string literals.
        # Split on string literals, only replace in non-literal parts.
        parts = self._string_literal.split(sql)
        literals = self._string_literal.findall(sql)

        result_parts: list[str] = []
        for i, part in enumerate(parts):
            result_parts.append(self._pattern.sub("TIMESTAMP(0)", part))
            if i < len(literals):
                result_parts.append(literals[i])

        return "".join(result_parts)


class TIMESTAMPRule(Rule):
    """Keep TIMESTAMP and TIMESTAMP(p) as-is.

    This rule exists for completeness; TIMESTAMP maps directly.
    It must NOT match TIMESTAMP WITH TIME ZONE or TIMESTAMP WITH LOCAL TIME ZONE.
    """

    name = "timestamp_to_timestamp"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 20
    description = "TIMESTAMP stays TIMESTAMP (identity mapping)"

    _pattern = re.compile(
        r"\bTIMESTAMP\b(?:\s*\(\s*\d+\s*\))?(?!\s+WITH\b)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        # Identity — no transformation needed
        return sql


class TIMESTAMPTZRule(Rule):
    """Convert TIMESTAMP WITH TIME ZONE to TIMESTAMPTZ.

    Also handles TIMESTAMP(p) WITH TIME ZONE.
    Must not match TIMESTAMP WITH LOCAL TIME ZONE.
    """

    name = "timestamp_tz_to_timestamptz"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 15  # Before TIMESTAMPRule
    description = "Convert TIMESTAMP WITH TIME ZONE to TIMESTAMPTZ"

    _pattern = re.compile(
        r"\bTIMESTAMP\s*(?:\(\s*\d+\s*\))?\s+WITH\s+TIME\s+ZONE\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("TIMESTAMPTZ", sql)


class TIMESTAMPLTZRule(Rule):
    """Convert TIMESTAMP WITH LOCAL TIME ZONE to TIMESTAMPTZ.

    Also handles TIMESTAMP(p) WITH LOCAL TIME ZONE.
    """

    name = "timestamp_ltz_to_timestamptz"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 14  # Before TIMESTAMPTZRule
    description = "Convert TIMESTAMP WITH LOCAL TIME ZONE to TIMESTAMPTZ"

    _pattern = re.compile(
        r"\bTIMESTAMP\s*(?:\(\s*\d+\s*\))?\s+WITH\s+LOCAL\s+TIME\s+ZONE\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("TIMESTAMPTZ", sql)


class INTERVALYMRule(Rule):
    """Convert INTERVAL YEAR TO MONTH to INTERVAL.

    Handles optional precision: INTERVAL YEAR(p) TO MONTH.
    """

    name = "interval_ym_to_interval"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 30
    description = "Convert INTERVAL YEAR TO MONTH to INTERVAL"

    _pattern = re.compile(
        r"\bINTERVAL\s+YEAR\s*(?:\(\s*\d+\s*\))?\s+TO\s+MONTH\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("INTERVAL", sql)


class INTERVALDSRule(Rule):
    """Convert INTERVAL DAY TO SECOND to INTERVAL.

    Handles optional precision: INTERVAL DAY(p) TO SECOND(s).
    """

    name = "interval_ds_to_interval"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 31
    description = "Convert INTERVAL DAY TO SECOND to INTERVAL"

    _pattern = re.compile(
        r"\bINTERVAL\s+DAY\s*(?:\(\s*\d+\s*\))?\s+TO\s+SECOND\s*(?:\(\s*\d+\s*\))?",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("INTERVAL", sql)


class XMLTYPERule(Rule):
    """Convert XMLTYPE to XML."""

    name = "xmltype_to_xml"
    category = RuleCategory.DATATYPES_TEMPORAL
    priority = 40
    description = "Convert XMLTYPE to XML"

    _pattern = re.compile(r"\bXMLTYPE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("XML", sql)
