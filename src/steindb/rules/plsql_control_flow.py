# src/steindb/rules/plsql_control_flow.py
"""PL/SQL control flow rules: exception handling, cursors, exit when."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory

# Oracle exception name -> PostgreSQL equivalent
_EXCEPTION_MAP: dict[str, str] = {
    "NO_DATA_FOUND": "NO_DATA_FOUND",
    "TOO_MANY_ROWS": "TOO_MANY_ROWS",
    "DUP_VAL_ON_INDEX": "UNIQUE_VIOLATION",
    "VALUE_ERROR": "DATA_EXCEPTION",
    "INVALID_NUMBER": "INVALID_TEXT_REPRESENTATION",
    "ZERO_DIVIDE": "DIVISION_BY_ZERO",
    "CURSOR_ALREADY_OPEN": "DUPLICATE_CURSOR",
    "INVALID_CURSOR": "INVALID_CURSOR_STATE",
    "LOGIN_DENIED": "INVALID_PASSWORD",
    "PROGRAM_ERROR": "INTERNAL_ERROR",
    "STORAGE_ERROR": "OUT_OF_MEMORY",
    "TIMEOUT_ON_RESOURCE": "LOCK_NOT_AVAILABLE",
    "ACCESS_INTO_NULL": "NULL_VALUE_NOT_ALLOWED",
    "CASE_NOT_FOUND": "CASE_NOT_FOUND",
    "ROWTYPE_MISMATCH": "DATATYPE_MISMATCH",
    "SELF_IS_NULL": "NULL_VALUE_NOT_ALLOWED",
    "SUBSCRIPT_BEYOND_COUNT": "ARRAY_SUBSCRIPT_ERROR",
    "SUBSCRIPT_OUTSIDE_LIMIT": "ARRAY_SUBSCRIPT_ERROR",
}


class ExceptionHandlingRule(Rule):
    """Convert Oracle exception names to PostgreSQL equivalents.

    WHEN DUP_VAL_ON_INDEX -> WHEN UNIQUE_VIOLATION
    WHEN NO_DATA_FOUND -> WHEN NO_DATA_FOUND (same)
    """

    name = "exception_handling"
    category = RuleCategory.PLSQL_CONTROL_FLOW
    priority = 10
    description = "Map Oracle exception names to PostgreSQL equivalents"

    _WHEN_PATTERN = re.compile(
        r"\bWHEN\s+(" + "|".join(re.escape(k) for k in _EXCEPTION_MAP) + r")\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._WHEN_PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            oracle_name = m.group(1).upper()
            pg_name = _EXCEPTION_MAP.get(oracle_name, oracle_name)
            return f"WHEN {pg_name}"

        return self._WHEN_PATTERN.sub(_replace, sql)


class CursorForLoopRule(Rule):
    """Cursor FOR loop pass-through with minor cleanup.

    Oracle: FOR rec IN cursor LOOP ... END LOOP;
    PG: FOR rec IN cursor LOOP ... END LOOP; (mostly identical)

    The main adjustment is ensuring cursor declaration syntax is compatible.
    """

    name = "cursor_for_loop"
    category = RuleCategory.PLSQL_CONTROL_FLOW
    priority = 20
    description = "Cursor FOR loop compatibility pass-through"

    _PATTERN = re.compile(
        r"\bFOR\s+\w+\s+IN\s+\w+\s+LOOP\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # Mostly pass-through -- PG supports the same syntax
        return sql


class ExitWhenRule(Rule):
    """EXIT WHEN pass-through (same syntax in PG)."""

    name = "exit_when"
    category = RuleCategory.PLSQL_CONTROL_FLOW
    priority = 30
    description = "EXIT WHEN pass-through (compatible syntax)"

    _PATTERN = re.compile(r"\bEXIT\s+WHEN\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # Same syntax in PostgreSQL
        return sql
