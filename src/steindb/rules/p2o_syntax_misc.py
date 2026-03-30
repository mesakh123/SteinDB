# src/steindb/rules/p2o_syntax_misc.py
"""P2O miscellaneous SQL syntax rules.

LIMIT, EXCEPT, CURRENT_USER, FROM DUAL, generate_series, ON CONFLICT.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# 1. LIMIT n -> FETCH FIRST n ROWS ONLY  (Oracle 12c+)
# ---------------------------------------------------------------------------

_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


class LimitToFetchFirstRule(Rule):
    name = "limit_to_fetch_first"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 10
    description = "LIMIT n -> FETCH FIRST n ROWS ONLY"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_LIMIT_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _LIMIT_RE,
            lambda m: f"FETCH FIRST {m.group(1)} ROWS ONLY",
            sql,
        )


# ---------------------------------------------------------------------------
# 2. EXCEPT -> MINUS
# ---------------------------------------------------------------------------

# Avoid matching EXCEPTION; also strip optional ALL (Oracle has no MINUS ALL)
_EXCEPT_ONLY_RE = re.compile(r"\bEXCEPT\b(?!ION)(\s+ALL\b)?", re.IGNORECASE)


class ExceptToMinusRule(Rule):
    name = "except_to_minus"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 20
    description = "EXCEPT [ALL] -> MINUS (Oracle has no MINUS ALL)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_EXCEPT_ONLY_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_EXCEPT_ONLY_RE, "MINUS", sql)


# ---------------------------------------------------------------------------
# 3. CURRENT_USER -> USER
# ---------------------------------------------------------------------------

_CURRENT_USER_RE = re.compile(r"\bCURRENT_USER\b", re.IGNORECASE)


class CurrentUserToUserRule(Rule):
    name = "current_user_to_user"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 30
    description = "CURRENT_USER -> USER"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_CURRENT_USER_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_CURRENT_USER_RE, "USER", sql)


# ---------------------------------------------------------------------------
# 4. SELECT expr (no FROM) -> SELECT expr FROM DUAL
# ---------------------------------------------------------------------------

# Match SELECT ... that does NOT have a FROM clause.
# Simple heuristic: a SELECT statement ending with ; or end-of-string that
# has no FROM keyword.  We only handle single-line simple cases.
_SELECT_NO_FROM_RE = re.compile(
    r"\b(SELECT\s+.+?)(?=\s*;|\s*$)",
    re.IGNORECASE,
)


class SelectFromDualRule(Rule):
    name = "select_from_dual"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 40
    description = "SELECT expr (no FROM) -> SELECT expr FROM DUAL"

    def matches(self, sql: str) -> bool:
        # Must have SELECT but no FROM
        upper = sql.upper().strip()
        if not upper.startswith("SELECT"):
            return False
        # Check there's no FROM clause at all
        return not re.search(r"\bFROM\b", sql, re.IGNORECASE)

    def apply(self, sql: str) -> str:
        # Append FROM DUAL before trailing semicolon or at end
        stripped = sql.rstrip()
        if stripped.endswith(";"):
            return stripped[:-1] + " FROM DUAL;"
        return stripped + " FROM DUAL"


# ---------------------------------------------------------------------------
# 5. generate_series(1, n) -> SELECT LEVEL FROM DUAL CONNECT BY LEVEL <= n
# ---------------------------------------------------------------------------

_GENERATE_SERIES_RE = re.compile(
    r"\bgenerate_series\s*\(\s*(\d+)\s*,\s*(\w+)\s*\)",
    re.IGNORECASE,
)


class GenerateSeriesToConnectByRule(Rule):
    name = "generate_series_to_connect_by"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 50
    description = "generate_series(1, n) -> SELECT LEVEL FROM DUAL CONNECT BY LEVEL <= n"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_GENERATE_SERIES_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            start = m.group(1)
            end = m.group(2)
            if start == "1":
                return f"SELECT LEVEL FROM DUAL CONNECT BY LEVEL <= {end}"
            return (
                f"SELECT LEVEL + {int(start) - 1} FROM DUAL"
                f" CONNECT BY LEVEL <= {end} - {int(start) - 1}"
            )

        return _replace_outside_strings(_GENERATE_SERIES_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 6. INSERT ... ON CONFLICT DO UPDATE -> MERGE INTO (basic pattern)
# ---------------------------------------------------------------------------

_ON_CONFLICT_RE = re.compile(
    r"INSERT\s+INTO\s+(\S+)\s*\((.+?)\)\s*"
    r"VALUES\s*\((.+?)\)\s*"
    r"ON\s+CONFLICT\s*\((\w+)\)\s*DO\s+UPDATE\s+SET\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)


class OnConflictToMergeRule(Rule):
    """Convert basic INSERT ... ON CONFLICT DO UPDATE to MERGE INTO.

    Handles the common pattern:
        INSERT INTO target (cols) VALUES (vals) ON CONFLICT (key) DO UPDATE SET ...

    Complex cases with WHERE clauses or DO NOTHING are forwarded to the LLM.
    """

    name = "on_conflict_to_merge"
    category = RuleCategory.P2O_SYNTAX_MISC
    priority = 60
    description = "INSERT ... ON CONFLICT DO UPDATE -> MERGE INTO"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_ON_CONFLICT_RE, sql)

    def apply(self, sql: str) -> str:
        m = _ON_CONFLICT_RE.search(sql)
        if not m:
            return sql

        target = m.group(1)
        cols = m.group(2).strip()
        vals = m.group(3).strip()
        conflict_col = m.group(4).strip()
        update_set = m.group(5).strip().rstrip(";")

        # Replace EXCLUDED.col references with src.col in the update set
        update_set_oracle = re.sub(
            r"\bEXCLUDED\.(\w+)",
            r"src.\1",
            update_set,
            flags=re.IGNORECASE,
        )

        # Build column list for the source
        col_list = [c.strip() for c in cols.split(",")]
        val_list = [v.strip() for v in vals.split(",")]

        # Build the USING (SELECT ... FROM DUAL) clause
        select_parts = [f"{v} AS {c}" for c, v in zip(col_list, val_list, strict=False)]
        using_select = ", ".join(select_parts)

        result = (
            f"MERGE INTO {target} tgt\n"
            f"USING (SELECT {using_select} FROM DUAL) src\n"
            f"ON (tgt.{conflict_col} = src.{conflict_col})\n"
            f"WHEN MATCHED THEN UPDATE SET {update_set_oracle}\n"
            f"WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({vals})"
        )
        return result
