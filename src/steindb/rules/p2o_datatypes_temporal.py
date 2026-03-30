# src/steindb/rules/p2o_datatypes_temporal.py
"""PostgreSQL-to-Oracle temporal data type conversion rules.

Converts PostgreSQL temporal types to Oracle equivalents:
  TIMESTAMP -> TIMESTAMP, TIMESTAMP(0) -> DATE,
  TIMESTAMPTZ -> TIMESTAMP WITH TIME ZONE,
  DATE -> DATE (with warning about no time component),
  INTERVAL -> INTERVAL DAY TO SECOND.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2O_TIMESTAMPRule(Rule):  # noqa: N801
    """Convert TIMESTAMP to Oracle TIMESTAMP, with special case TIMESTAMP(0) -> DATE.

    Oracle DATE includes time down to the second (no fractional seconds),
    so TIMESTAMP(0) maps naturally to Oracle DATE.

    Must not match TIMESTAMPTZ (separate rule).
    """

    name = "p2o_timestamp_to_timestamp"
    category = RuleCategory.P2O_DATATYPES_TEMPORAL
    priority = 20
    description = "Convert TIMESTAMP to TIMESTAMP; TIMESTAMP(0) to DATE"

    # Match TIMESTAMP with optional precision, but NOT TIMESTAMPTZ or TIMESTAMP WITH ...
    _pattern = re.compile(
        r"\bTIMESTAMP\s*(?:\(\s*(\d+)\s*\))?(?!\s*(?:WITH|TZ)\b)(?!TZ\b)",
        re.IGNORECASE,
    )

    # Exclude TIMESTAMPTZ
    _tz_pattern = re.compile(r"\bTIMESTAMPTZ\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        # Remove TIMESTAMPTZ occurrences before checking
        cleaned = self._tz_pattern.sub("", sql)
        return bool(self._pattern.search(cleaned))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            precision = m.group(1)
            if precision is not None and int(precision) == 0:
                return "DATE"
            # PG TIMESTAMP precision is 0-6; Oracle supports 0-9.
            # Clamp any precision > 9 (invalid) and warn on > 6 (not from PG).
            if precision is not None:
                p = int(precision)
                if p > 9:
                    return (
                        f"TIMESTAMP(9) /* WARNING: precision {p} exceeds Oracle max 9; clamped */"
                    )
                return f"TIMESTAMP({precision})"
            return "TIMESTAMP"

        # Split out TIMESTAMPTZ tokens so we don't corrupt them
        # Use a two-pass approach: protect TIMESTAMPTZ, then replace TIMESTAMP
        protected = self._tz_pattern.sub("\x00TIMESTAMPTZ\x00", sql)
        result = self._pattern.sub(_replace, protected)
        result = result.replace("\x00TIMESTAMPTZ\x00", "TIMESTAMPTZ")
        return result


class P2O_TIMESTAMPTZRule(Rule):  # noqa: N801
    """Convert TIMESTAMPTZ to TIMESTAMP WITH TIME ZONE.

    PostgreSQL stores TIMESTAMPTZ internally as UTC. Oracle TIMESTAMP WITH TIME ZONE
    preserves the original time zone offset.
    """

    name = "p2o_timestamptz_to_timestamp_tz"
    category = RuleCategory.P2O_DATATYPES_TEMPORAL
    priority = 15  # Before TIMESTAMPRule to claim TIMESTAMPTZ first
    description = "Convert TIMESTAMPTZ to TIMESTAMP WITH TIME ZONE"

    _pattern = re.compile(r"\bTIMESTAMPTZ\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("TIMESTAMP WITH TIME ZONE", sql)


class P2O_DATERule(Rule):  # noqa: N801
    """Convert PostgreSQL DATE to Oracle DATE.

    WARNING: PostgreSQL DATE has no time component; Oracle DATE includes time
    down to the second. This can cause subtle issues if Oracle code assumes
    DATE values have a time component. A warning comment is added.

    Must not match inside TO_DATE or other compound identifiers.
    """

    name = "p2o_date_to_date"
    category = RuleCategory.P2O_DATATYPES_TEMPORAL
    priority = 10
    description = "Convert DATE to DATE (with warning about time component difference)"

    # Match DATE as a standalone type keyword
    _pattern = re.compile(
        r"(?<![A-Za-z_])DATE\b(?!\s*\()",
        re.IGNORECASE,
    )
    _string_literal = re.compile(r"'[^']*'")

    def matches(self, sql: str) -> bool:
        cleaned = self._string_literal.sub("", sql)
        return bool(self._pattern.search(cleaned))

    def apply(self, sql: str) -> str:
        # Split on string literals, only replace in non-literal parts
        parts = self._string_literal.split(sql)
        literals = self._string_literal.findall(sql)

        result_parts: list[str] = []
        for i, part in enumerate(parts):
            result_parts.append(
                self._pattern.sub(
                    "DATE /* WARNING: PG DATE has no time component; Oracle DATE includes time */",
                    part,
                )
            )
            if i < len(literals):
                result_parts.append(literals[i])

        return "".join(result_parts)


class P2O_TIMERule(Rule):  # noqa: N801
    """Convert TIME and TIME WITH TIME ZONE to DATE/TIMESTAMP.

    Oracle has no TIME type. TIME maps to DATE (which includes time in Oracle).
    TIME WITH TIME ZONE maps to TIMESTAMP WITH TIME ZONE.
    """

    name = "p2o_time_to_date"
    category = RuleCategory.P2O_DATATYPES_TEMPORAL
    priority = 25
    description = "Convert TIME to DATE; TIME WITH TIME ZONE to TIMESTAMP WITH TIME ZONE"

    _time_tz_pattern = re.compile(r"\bTIME\s+WITH\s+TIME\s+ZONE\b", re.IGNORECASE)
    _time_pattern = re.compile(r"\bTIME\b(?!\s+WITH|\s+ZONE|STAMP)", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._time_tz_pattern.search(sql)) or bool(self._time_pattern.search(sql))

    def apply(self, sql: str) -> str:
        result = self._time_tz_pattern.sub("TIMESTAMP WITH TIME ZONE", sql)
        return self._time_pattern.sub("DATE", result)


class P2O_INTERVALRule(Rule):  # noqa: N801
    """Convert INTERVAL to INTERVAL DAY TO SECOND.

    PostgreSQL INTERVAL can represent any combination of years, months, days,
    hours, minutes, seconds. Oracle has two separate interval types:
    - INTERVAL YEAR TO MONTH
    - INTERVAL DAY TO SECOND

    Default mapping is INTERVAL DAY TO SECOND as it covers the most common
    use cases (durations). Year-month intervals require manual review.

    Must not match INTERVAL YEAR TO MONTH or INTERVAL DAY TO SECOND
    (already Oracle format).
    """

    name = "p2o_interval_to_interval_ds"
    category = RuleCategory.P2O_DATATYPES_TEMPORAL
    priority = 30
    description = "Convert INTERVAL to INTERVAL DAY TO SECOND"

    # Match bare INTERVAL not followed by YEAR or DAY (already Oracle-qualified)
    _pattern = re.compile(
        r"\bINTERVAL\b(?!\s+(?:YEAR|DAY)\b)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._pattern.search(sql))

    def apply(self, sql: str) -> str:
        return self._pattern.sub("INTERVAL DAY TO SECOND", sql)
