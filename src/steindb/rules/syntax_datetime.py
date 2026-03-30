# src/steindb/rules/syntax_datetime.py
"""Date/Time function rules: Oracle temporal functions to PostgreSQL equivalents."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# Helpers (shared with syntax_functions but kept local to avoid circular deps)
# ---------------------------------------------------------------------------

_BALANCED_PARENS = r"\(([^()]*(?:\([^()]*\))*[^()]*)\)"


def _string_ranges(sql: str) -> list[tuple[int, int]]:
    """Return (start, end) ranges of single-quoted string literals in *sql*."""
    return [(m.start(), m.end()) for m in re.finditer(r"'(?:''|[^'])*'", sql)]


def _is_inside_string(pos: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < pos < end for start, end in ranges)


def _matches_outside_strings(pattern: re.Pattern[str], sql: str) -> bool:
    ranges = _string_ranges(sql)
    return any(not _is_inside_string(m.start(), ranges) for m in pattern.finditer(sql))


def _replace_outside_strings(
    pattern: re.Pattern[str], repl: str | Callable[..., str], sql: str
) -> str:
    """Apply *pattern* replacement only when the match start is outside a string literal."""
    ranges = _string_ranges(sql)
    matches = list(pattern.finditer(sql))
    for m in reversed(matches):
        if not _is_inside_string(m.start(), ranges):
            replacement = repl(m) if callable(repl) else m.expand(repl)
            sql = sql[: m.start()] + replacement + sql[m.end() :]
    return sql


# ---------------------------------------------------------------------------
# 1. SYSDATE → CURRENT_TIMESTAMP
# ---------------------------------------------------------------------------

_SYSDATE_RE = re.compile(r"\bSYSDATE\b", re.IGNORECASE)


class SYSDATERule(Rule):
    name = "sysdate_to_current_timestamp"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 10
    description = "SYSDATE -> CURRENT_TIMESTAMP"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_SYSDATE_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_SYSDATE_RE, "CURRENT_TIMESTAMP", sql)


# ---------------------------------------------------------------------------
# 2. SYSTIMESTAMP → clock_timestamp()
# ---------------------------------------------------------------------------

_SYSTIMESTAMP_RE = re.compile(r"\bSYSTIMESTAMP\b", re.IGNORECASE)


class SYSTIMESTAMPRule(Rule):
    name = "systimestamp_to_clock_timestamp"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 20
    description = "SYSTIMESTAMP -> clock_timestamp()"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_SYSTIMESTAMP_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_SYSTIMESTAMP_RE, "clock_timestamp()", sql)


# ---------------------------------------------------------------------------
# 3. ADD_MONTHS → interval arithmetic
# ---------------------------------------------------------------------------

_ADD_MONTHS_RE = re.compile(r"\bADD_MONTHS\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)


class ADDMONTHSRule(Rule):
    name = "add_months_to_interval"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 30
    description = "ADD_MONTHS(d, n) -> d + (n * interval '1 month')"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_ADD_MONTHS_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            d = m.group(1).strip()
            n = m.group(2).strip()
            return f"{d} + ({n} * interval '1 month')"

        return _replace_outside_strings(_ADD_MONTHS_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 4. LAST_DAY → DATE_TRUNC + INTERVAL
# ---------------------------------------------------------------------------

_LAST_DAY_RE = re.compile(r"\bLAST_DAY\s*" + _BALANCED_PARENS, re.IGNORECASE)


class LASTDAYRule(Rule):
    name = "last_day_to_date_trunc"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 40
    description = "LAST_DAY(d) -> (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::date"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_LAST_DAY_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            d = m.group(1).strip()
            return f"(DATE_TRUNC('month', {d}) + INTERVAL '1 month - 1 day')::date"

        return _replace_outside_strings(_LAST_DAY_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 5. TRUNC(date) → DATE_TRUNC
# ---------------------------------------------------------------------------

# TRUNC with format model: TRUNC(d, 'MM') / TRUNC(d, 'YYYY') etc.
_TRUNC_FMT_RE = re.compile(
    r"\bTRUNC\s*\(\s*(.+?)\s*,\s*'(MM|MONTH|YYYY|YEAR|YY|Q|DD|DY|DAY|HH|HH24|MI|IW|WW|W|CC)'\s*\)",
    re.IGNORECASE,
)
# TRUNC with single arg (date only): TRUNC(d)
_TRUNC_NOARG_RE = re.compile(r"\bTRUNC\s*\(\s*([^,)]+)\s*\)", re.IGNORECASE)

# Map Oracle format models to PostgreSQL DATE_TRUNC precision
_TRUNC_FMT_MAP: dict[str, str] = {
    "MM": "month",
    "MONTH": "month",
    "YYYY": "year",
    "YEAR": "year",
    "YY": "year",
    "Q": "quarter",
    "DD": "day",
    "DY": "day",
    "DAY": "day",
    "HH": "hour",
    "HH24": "hour",
    "MI": "minute",
    "IW": "week",
    "WW": "week",
    "W": "week",
    "CC": "century",
}


class TRUNCDateRule(Rule):
    name = "trunc_date_to_date_trunc"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 50
    description = "TRUNC(d) -> DATE_TRUNC('day', d); TRUNC(d, 'MM') -> DATE_TRUNC('month', d)"

    def matches(self, sql: str) -> bool:
        # Must be careful: TRUNC can also be numeric TRUNC(n, d).
        # We match if there is TRUNC( with a format string, or a bare TRUNC
        # that looks like a date context.  For safety, we match any TRUNC.
        pat = re.compile(r"\bTRUNC\s*\(", re.IGNORECASE)
        return _matches_outside_strings(pat, sql)

    def apply(self, sql: str) -> str:
        # First replace 2-arg form (with format model)
        def _repl_fmt(m: re.Match[str]) -> str:
            d = m.group(1).strip()
            fmt = m.group(2).upper()
            pg_prec = _TRUNC_FMT_MAP.get(fmt, "day")
            return f"DATE_TRUNC('{pg_prec}', {d})"

        result = _replace_outside_strings(_TRUNC_FMT_RE, _repl_fmt, sql)

        # Then replace single-arg TRUNC(d) — only if it looks like date context
        # (i.e., not numeric TRUNC(123.45, 2) which has already been handled above
        # if it had a format string).  We convert bare TRUNC(x) to DATE_TRUNC('day', x).
        def _repl_bare(m: re.Match[str]) -> str:
            d = m.group(1).strip()
            # Heuristic: if the arg looks like a plain number, skip.
            # Numbers: digits, dots, minus, or numeric expressions.
            if re.fullmatch(r"-?\d+(\.\d+)?", d):
                return m.group(0)
            return f"DATE_TRUNC('day', {d})"

        result = _replace_outside_strings(_TRUNC_NOARG_RE, _repl_bare, result)
        return result


# ---------------------------------------------------------------------------
# 6. Date arithmetic: date + integer → date + interval
# ---------------------------------------------------------------------------

# Pattern: <identifier_or_expr> + <integer> where context suggests date.
# We look for common date column names or SYSDATE/CURRENT_TIMESTAMP patterns.
_DATE_ADD_INT_RE = re.compile(
    r"(\b(?:CURRENT_TIMESTAMP|SYSDATE|[a-z_]\w*\.?(?:date|_dt|_date|created|modified|updated|hire_date|start_date|end_date|expiry_date|due_date|ship_date))\b)"
    r"\s*\+\s*(\d+)\b",
    re.IGNORECASE,
)


class DateArithmeticRule(Rule):
    name = "date_plus_integer_to_interval"
    category = RuleCategory.SYNTAX_DATETIME
    priority = 60
    description = "date + integer -> date + interval 'N days'"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_DATE_ADD_INT_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            date_expr = m.group(1)
            n = m.group(2)
            return f"{date_expr} + interval '{n} days'"

        return _replace_outside_strings(_DATE_ADD_INT_RE, _repl, sql)
