# src/steindb/rules/p2o_syntax_datetime.py
"""P2O date/time function rules: PostgreSQL temporal functions to Oracle equivalents."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BALANCED_PARENS = r"\(([^()]*(?:\([^()]*\))*[^()]*)\)"


def _string_ranges(sql: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"'(?:''|[^'])*'", sql)]


def _is_inside_string(pos: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < pos < end for start, end in ranges)


def _matches_outside_strings(pattern: re.Pattern[str], sql: str) -> bool:
    ranges = _string_ranges(sql)
    return any(not _is_inside_string(m.start(), ranges) for m in pattern.finditer(sql))


def _replace_outside_strings(
    pattern: re.Pattern[str], repl: str | Callable[..., str], sql: str
) -> str:
    ranges = _string_ranges(sql)
    matches = list(pattern.finditer(sql))
    for m in reversed(matches):
        if not _is_inside_string(m.start(), ranges):
            replacement = repl(m) if callable(repl) else m.expand(repl)
            sql = sql[: m.start()] + replacement + sql[m.end() :]
    return sql


# ---------------------------------------------------------------------------
# 1. CURRENT_TIMESTAMP -> SYSDATE
# ---------------------------------------------------------------------------

_CURRENT_TIMESTAMP_RE = re.compile(r"\bCURRENT_TIMESTAMP\b", re.IGNORECASE)


class CurrentTimestampToSysdateRule(Rule):
    name = "current_timestamp_to_sysdate"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 10
    description = "CURRENT_TIMESTAMP -> SYSDATE"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_CURRENT_TIMESTAMP_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_CURRENT_TIMESTAMP_RE, "SYSDATE", sql)


# ---------------------------------------------------------------------------
# 2. clock_timestamp() -> SYSTIMESTAMP
# ---------------------------------------------------------------------------

_CLOCK_TIMESTAMP_RE = re.compile(r"\bclock_timestamp\s*\(\s*\)", re.IGNORECASE)


class ClockTimestampToSystimestampRule(Rule):
    name = "clock_timestamp_to_systimestamp"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 20
    description = "clock_timestamp() -> SYSTIMESTAMP"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_CLOCK_TIMESTAMP_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_CLOCK_TIMESTAMP_RE, "SYSTIMESTAMP", sql)


# ---------------------------------------------------------------------------
# 3. date + INTERVAL '1 day' -> date + 1
#    date + INTERVAL 'N days' -> date + N
# ---------------------------------------------------------------------------

_DATE_INTERVAL_DAYS_RE = re.compile(
    r"(\b\w+(?:\.\w+)?)\s*\+\s*INTERVAL\s+'(\d+)\s+days?'",
    re.IGNORECASE,
)


class DateIntervalDaysRule(Rule):
    name = "date_interval_days_to_arithmetic"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 30
    description = "date + INTERVAL 'N days' -> date + N"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_DATE_INTERVAL_DAYS_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            date_expr = m.group(1)
            n = m.group(2)
            return f"{date_expr} + {n}"

        return _replace_outside_strings(_DATE_INTERVAL_DAYS_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 4. date + (n || ' months')::interval -> ADD_MONTHS(date, n)
# ---------------------------------------------------------------------------

_MONTHS_INTERVAL_RE = re.compile(
    r"(\b\w+(?:\.\w+)?)\s*\+\s*\(\s*(\w+)\s*\|\|\s*'\s*months?\s*'\s*\)\s*::\s*interval",
    re.IGNORECASE,
)


class MonthsIntervalToAddMonthsRule(Rule):
    name = "months_interval_to_add_months"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 40
    description = "date + (n || ' months')::interval -> ADD_MONTHS(date, n)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_MONTHS_INTERVAL_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            date_expr = m.group(1)
            n = m.group(2)
            return f"ADD_MONTHS({date_expr}, {n})"

        return _replace_outside_strings(_MONTHS_INTERVAL_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 5. DATE_TRUNC('day', d) -> TRUNC(d)
# ---------------------------------------------------------------------------

_DATE_TRUNC_DAY_RE = re.compile(
    r"\bDATE_TRUNC\s*\(\s*'day'\s*,\s*(.+?)\s*\)",
    re.IGNORECASE,
)


class DateTruncDayRule(Rule):
    name = "date_trunc_day_to_trunc"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 50
    description = "DATE_TRUNC('day', d) -> TRUNC(d)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_DATE_TRUNC_DAY_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _DATE_TRUNC_DAY_RE,
            lambda m: f"TRUNC({m.group(1).strip()})",
            sql,
        )


# ---------------------------------------------------------------------------
# 6. DATE_TRUNC('month', d) -> TRUNC(d, 'MM')
#    DATE_TRUNC('year', d)  -> TRUNC(d, 'YYYY')
#    DATE_TRUNC('quarter', d) -> TRUNC(d, 'Q')
#    etc.
# ---------------------------------------------------------------------------

# Map PostgreSQL precision to Oracle format model
_PG_TO_ORA_TRUNC_MAP: dict[str, str] = {
    "month": "MM",
    "year": "YYYY",
    "quarter": "Q",
    "hour": "HH",
    "minute": "MI",
    "week": "IW",
    "century": "CC",
}

_DATE_TRUNC_FMT_RE = re.compile(
    r"\bDATE_TRUNC\s*\(\s*'(\w+)'\s*,\s*(.+?)\s*\)",
    re.IGNORECASE,
)


class DateTruncFmtRule(Rule):
    name = "date_trunc_fmt_to_trunc"
    category = RuleCategory.P2O_SYNTAX_DATETIME
    priority = 60
    description = (
        "DATE_TRUNC('month', d) -> TRUNC(d, 'MM'); DATE_TRUNC('year', d) -> TRUNC(d, 'YYYY')"
    )

    def matches(self, sql: str) -> bool:
        if not _matches_outside_strings(_DATE_TRUNC_FMT_RE, sql):
            return False
        # Only match if the precision is in our map (not 'day' which is handled above)
        ranges = _string_ranges(sql)
        for m in _DATE_TRUNC_FMT_RE.finditer(sql):
            if not _is_inside_string(m.start(), ranges):
                prec = m.group(1).lower()
                if prec in _PG_TO_ORA_TRUNC_MAP:
                    return True
        return False

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            prec = m.group(1).lower()
            d = m.group(2).strip()
            ora_fmt = _PG_TO_ORA_TRUNC_MAP.get(prec)
            if ora_fmt:
                return f"TRUNC({d}, '{ora_fmt}')"
            return m.group(0)  # Unknown precision, leave unchanged

        return _replace_outside_strings(_DATE_TRUNC_FMT_RE, _repl, sql)
