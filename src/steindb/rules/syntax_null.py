# src/steindb/rules/syntax_null.py
"""NULL/Empty string semantic rules for Oracle-to-PostgreSQL conversion.

Oracle treats '' as NULL and || is null-safe.  PostgreSQL does not.
These rules add safety wrappers.
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
# 1. ConcatNullSafeRule: || with column refs → concat()
#    Oracle: 'hello' || NULL = 'hello'
#    PostgreSQL: 'hello' || NULL = NULL
# ---------------------------------------------------------------------------

# Match SELECT ... col1 || col2 ... (column-like operands around ||)
# We detect || used with column references (not purely literal || literal)
_CONCAT_OP_RE = re.compile(r"\|\|")
_COLUMN_CONCAT_RE = re.compile(
    r"((?:[\w.]+|'(?:''|[^'])*')\s*(?:\|\|\s*(?:[\w.]+|'(?:''|[^'])*')\s*)+)",
)


class ConcatNullSafeRule(Rule):
    name = "concat_null_safe"
    category = RuleCategory.SYNTAX_NULL
    priority = 10
    description = "Wrap || concatenation with column refs in concat() for null safety"

    def matches(self, sql: str) -> bool:
        if not _outside_strings_has(_CONCAT_OP_RE, sql):
            return False
        # Must have at least one non-literal operand (column reference)
        # around a || operator
        return _has_column_concat(sql)

    def apply(self, sql: str) -> str:
        return _convert_concat_to_function(sql)


def _has_column_concat(sql: str) -> bool:
    """Check if || is used with at least one column reference (not purely literals)."""
    parts = re.split(r"('(?:''|[^'])*')", sql)
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            # Look for pattern: something || something where at least one is a column
            concat_segments = re.split(r"\|\|", part)
            if len(concat_segments) < 2:
                continue
            has_column = False
            for seg in concat_segments:
                seg = seg.strip()
                if (
                    seg
                    and not re.fullmatch(r"'(?:''|[^'])*'", seg)
                    and re.search(r"[a-zA-Z_]\w*", seg)
                ):
                    has_column = True
                    break
            if has_column:
                return True
    return False


def _convert_concat_to_function(sql: str) -> str:
    """Convert col1 || ' ' || col2 into concat(col1, ' ', col2).

    Only converts when column references are involved.
    Works within SELECT expressions but avoids modifying string literals.
    """
    # We need to work on the full SQL but respect string boundaries.
    # Simpler approach: find all || chains in the full SQL, checking each operand.

    # Use a regex that matches a chain of expressions connected by ||
    chain_re = re.compile(r"((?:[\w.]+|'(?:''|[^'])*')\s*(?:\|\|\s*(?:[\w.]+|'(?:''|[^'])*')\s*)+)")

    def _repl_chain(m: re.Match[str]) -> str:
        chain = m.group(0)
        operands = re.split(r"\s*\|\|\s*", chain)
        # Check if there is at least one column reference
        has_col = any(
            not re.fullmatch(r"'(?:''|[^'])*'", op.strip()) and re.search(r"[a-zA-Z_]", op.strip())
            for op in operands
        )
        if not has_col:
            return chain  # all literals, leave as-is
        args = ", ".join(op.strip() for op in operands)
        return f"concat({args})"

    return chain_re.sub(_repl_chain, sql)


# ---------------------------------------------------------------------------
# 2. EmptyStringComparisonRule: WHERE col = '' → WHERE (col = '' OR col IS NULL)
# ---------------------------------------------------------------------------

_EMPTY_STR_RE = re.compile(r"(\b[\w.]+)\s*=\s*''", re.IGNORECASE)


class EmptyStringComparisonRule(Rule):
    name = "empty_string_comparison"
    category = RuleCategory.SYNTAX_NULL
    priority = 20
    description = "WHERE col = '' -> WHERE (col = '' OR col IS NULL)"

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_EMPTY_STR_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            col = m.group(1)
            return f"({col} = '' OR {col} IS NULL)"

        return _replace_outside_strings(_EMPTY_STR_RE, _repl, sql)
