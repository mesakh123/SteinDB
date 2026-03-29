# src/steindb/rules/syntax_misc.py
"""Miscellaneous SQL syntax rules.

DUAL removal, ROWNUM, MINUS, subselect aliases, USER, MERGE, case folding.
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
    """Apply *pattern* replacement only when the match start is outside a string literal."""
    ranges = _string_ranges(sql)
    matches = list(pattern.finditer(sql))
    for m in reversed(matches):
        if not _is_inside_string(m.start(), ranges):
            replacement = repl(m) if callable(repl) else m.expand(repl)
            sql = sql[: m.start()] + replacement + sql[m.end() :]
    return sql


def _outside_strings_has(pattern: re.Pattern[str], sql: str) -> bool:
    return _matches_outside_strings(pattern, sql)


# ---------------------------------------------------------------------------
# 1. DUALRemovalRule: FROM DUAL / FROM SYS.DUAL
# ---------------------------------------------------------------------------

_DUAL_RE = re.compile(r"\s+FROM\s+(?:SYS\.)?DUAL\b", re.IGNORECASE)


class DUALRemovalRule(Rule):
    name = "dual_removal"
    category = RuleCategory.SYNTAX_MISC
    priority = 10
    description = "Remove FROM DUAL (or FROM SYS.DUAL)"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_DUAL_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_DUAL_RE, "", sql)


# ---------------------------------------------------------------------------
# 2. ROWNUMRule: WHERE ROWNUM <= n → LIMIT n
# ---------------------------------------------------------------------------

# Simple ROWNUM in WHERE clause: WHERE ROWNUM <= N or WHERE ROWNUM < N
_ROWNUM_LE_RE = re.compile(r"\bWHERE\s+ROWNUM\s*<=\s*(\d+)\b", re.IGNORECASE)
_ROWNUM_LT_RE = re.compile(r"\bWHERE\s+ROWNUM\s*<\s*(\d+)\b", re.IGNORECASE)
_ROWNUM_EQ_RE = re.compile(r"\bWHERE\s+ROWNUM\s*=\s*1\b", re.IGNORECASE)
# ROWNUM after AND: AND ROWNUM <= N
_ROWNUM_AND_LE_RE = re.compile(r"\bAND\s+ROWNUM\s*<=\s*(\d+)\b", re.IGNORECASE)
_ROWNUM_AND_LT_RE = re.compile(r"\bAND\s+ROWNUM\s*<\s*(\d+)\b", re.IGNORECASE)
# General ROWNUM detector
_ROWNUM_RE = re.compile(r"\bROWNUM\b", re.IGNORECASE)


class ROWNUMRule(Rule):
    name = "rownum_to_limit"
    category = RuleCategory.SYNTAX_MISC
    priority = 20
    description = "WHERE ROWNUM <= n -> LIMIT n (simple cases)"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_ROWNUM_RE, sql)

    def apply(self, sql: str) -> str:
        result = sql

        # WHERE ROWNUM = 1 → LIMIT 1 (remove WHERE clause)
        if _outside_strings_has(_ROWNUM_EQ_RE, result):
            result = _replace_outside_strings(_ROWNUM_EQ_RE, "LIMIT 1", result)
            return result

        # WHERE ROWNUM <= N → LIMIT N (remove WHERE, append LIMIT)
        m = _ROWNUM_LE_RE.search(result)
        if m and _outside_strings_has(_ROWNUM_LE_RE, result):
            n = m.group(1)
            result = _replace_outside_strings(_ROWNUM_LE_RE, f"LIMIT {n}", result)
            return result

        # WHERE ROWNUM < N → LIMIT N-1
        m = _ROWNUM_LT_RE.search(result)
        if m and _outside_strings_has(_ROWNUM_LT_RE, result):
            n = int(m.group(1)) - 1
            result = _replace_outside_strings(_ROWNUM_LT_RE, f"LIMIT {n}", result)
            return result

        # AND ROWNUM <= N → strip AND, add LIMIT
        m = _ROWNUM_AND_LE_RE.search(result)
        if m and _outside_strings_has(_ROWNUM_AND_LE_RE, result):
            n = m.group(1)
            result = _replace_outside_strings(_ROWNUM_AND_LE_RE, "", result)
            result = result.rstrip() + f" LIMIT {n}"
            return result

        # AND ROWNUM < N → strip AND, add LIMIT N-1
        m = _ROWNUM_AND_LT_RE.search(result)
        if m and _outside_strings_has(_ROWNUM_AND_LT_RE, result):
            n = int(m.group(1)) - 1
            result = _replace_outside_strings(_ROWNUM_AND_LT_RE, "", result)
            result = result.rstrip() + f" LIMIT {n}"
            return result

        return result


# ---------------------------------------------------------------------------
# 3. MINUSRule: MINUS → EXCEPT
# ---------------------------------------------------------------------------

_MINUS_RE = re.compile(r"\bMINUS\b", re.IGNORECASE)


class MINUSRule(Rule):
    name = "minus_to_except"
    category = RuleCategory.SYNTAX_MISC
    priority = 30
    description = "MINUS -> EXCEPT"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_MINUS_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_MINUS_RE, "EXCEPT", sql)


# ---------------------------------------------------------------------------
# 4. SubselectAliasRule: anonymous subselects in FROM get an alias
# ---------------------------------------------------------------------------

# Match: FROM ( ... )  without an alias (no AS alias or bare alias after)
_SUBSELECT_NO_ALIAS_RE = re.compile(
    r"(\bFROM\s*\()((?:[^()]*(?:\([^()]*\))*)*\))" r"(?!\s+(?:AS\s+)?[a-z_]\w*)",
    re.IGNORECASE,
)

# Counter for generating unique aliases
_alias_counter = 0


class SubselectAliasRule(Rule):
    name = "subselect_alias"
    category = RuleCategory.SYNTAX_MISC
    priority = 40
    description = "Add alias to anonymous subselects in FROM clause"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_SUBSELECT_NO_ALIAS_RE, sql)

    def apply(self, sql: str) -> str:
        global _alias_counter  # noqa: PLW0603

        def _repl(m: re.Match[str]) -> str:
            global _alias_counter  # noqa: PLW0603
            _alias_counter += 1
            return f"{m.group(1)}{m.group(2)} AS subq{_alias_counter}"

        return _replace_outside_strings(_SUBSELECT_NO_ALIAS_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 5. USERPseudocolumnRule: USER → CURRENT_USER
# ---------------------------------------------------------------------------

# Match bare USER keyword used as a pseudocolumn (not part of a larger word,
# not preceded by CURRENT_ or CREATE/ALTER/DROP)
_USER_RE = re.compile(
    r"(?<![_A-Za-z])(?<!CURRENT_)(?<!CREATE\s)(?<!ALTER\s)(?<!DROP\s)\bUSER\b(?![\w.])",
    re.IGNORECASE,
)


class USERPseudocolumnRule(Rule):
    name = "user_to_current_user"
    category = RuleCategory.SYNTAX_MISC
    priority = 50
    description = "USER -> CURRENT_USER"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_USER_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_USER_RE, "CURRENT_USER", sql)


# ---------------------------------------------------------------------------
# 6. CaseFoldingWarningRule: warn about uppercase identifiers
# ---------------------------------------------------------------------------

# Detect quoted uppercase identifiers like "MY_TABLE" or "EMPLOYEE_ID"
_UPPERCASE_IDENT_RE = re.compile(r'"([A-Z][A-Z0-9_]*)"')


class CaseFoldingWarningRule(Rule):
    """Add a WARNING comment when uppercase quoted identifiers are detected.

    Oracle defaults to uppercase unquoted identifiers while PostgreSQL
    defaults to lowercase.  Quoted uppercase identifiers in PostgreSQL
    require exact-case quoting in every query, ORM mapping, and script.
    """

    name = "case_folding_warning"
    category = RuleCategory.SYNTAX_MISC
    priority = 60
    description = "Add WARNING comment for uppercase identifiers"

    def matches(self, sql: str) -> bool:
        return bool(_UPPERCASE_IDENT_RE.search(sql))

    def apply(self, sql: str) -> str:
        identifiers = _UPPERCASE_IDENT_RE.findall(sql)
        unique_ids = sorted(set(identifiers))
        warning = (
            "/* WARNING: Uppercase identifiers detected: "
            + ", ".join(f'"{ident}"' for ident in unique_ids)
            + ". Consider converting to lowercase to avoid quoting issues in PostgreSQL. */"
        )
        return warning + "\n" + sql


# ---------------------------------------------------------------------------
# 7. MERGEIntoRule: MERGE INTO -> INSERT ... ON CONFLICT (basic pattern)
# ---------------------------------------------------------------------------

# Basic MERGE pattern:
#   MERGE INTO <target> USING <source> ON (<condition>)
#   WHEN MATCHED THEN UPDATE SET <assignments>
#   WHEN NOT MATCHED THEN INSERT (<cols>) VALUES (<vals>)
_MERGE_RE = re.compile(
    r"\bMERGE\s+INTO\s+(\S+)(?:\s+\S+)?\s+"
    r"USING\s+(\S+)(?:\s+\S+)?\s+"
    r"ON\s*\((.+?)\)\s+"
    r"WHEN\s+MATCHED\s+THEN\s+UPDATE\s+SET\s+(.+?)\s+"
    r"WHEN\s+NOT\s+MATCHED\s+THEN\s+INSERT\s*\((.+?)\)\s+VALUES\s*\((.+?)\)",
    re.IGNORECASE | re.DOTALL,
)


class MERGEIntoRule(Rule):
    """Convert basic MERGE INTO to INSERT ... ON CONFLICT DO UPDATE.

    Handles the common pattern:
        MERGE INTO target USING source ON (condition)
        WHEN MATCHED THEN UPDATE SET ...
        WHEN NOT MATCHED THEN INSERT (...) VALUES (...)

    Complex MERGE statements with DELETE clauses or multiple WHEN conditions
    are forwarded to the LLM Transpiler.
    """

    name = "merge_into_to_insert_on_conflict"
    category = RuleCategory.SYNTAX_MISC
    priority = 70
    description = "MERGE INTO -> INSERT ... ON CONFLICT (basic pattern)"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_MERGE_RE, sql)

    def apply(self, sql: str) -> str:
        m = _MERGE_RE.search(sql)
        if not m:
            return sql

        target = m.group(1)
        _source = m.group(2)
        condition = m.group(3).strip()
        update_set = m.group(4).strip()
        insert_cols = m.group(5).strip()
        insert_vals = m.group(6).strip()

        # Extract the conflict column from the ON condition
        # Typical: target.col = source.col -> col
        conflict_col_match = re.search(r"(\w+)\s*=\s*\w+\.\w+", condition)
        if conflict_col_match:
            conflict_col = conflict_col_match.group(1)
            # Strip table prefix if present
            if "." in conflict_col:
                conflict_col = conflict_col.split(".")[-1]
        else:
            conflict_col = condition

        result = (
            f"INSERT INTO {target} ({insert_cols})\n"
            f"VALUES ({insert_vals})\n"
            f"ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}"
        )

        # Preserve anything after the MERGE statement
        end_pos = m.end()
        remainder = sql[end_pos:]
        return result + remainder
