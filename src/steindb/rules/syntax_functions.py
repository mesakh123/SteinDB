# src/steindb/rules/syntax_functions.py
"""Function mapping rules: Oracle built-in functions to PostgreSQL equivalents."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Regex to match a balanced parenthesised argument list.  Handles one level
# of nesting which is sufficient for the vast majority of real-world SQL.
_BALANCED_PARENS = r"\(([^()]*(?:\([^()]*\))*[^()]*)\)"


def _string_ranges(sql: str) -> list[tuple[int, int]]:
    """Return (start, end) ranges of single-quoted string literals in *sql*."""
    ranges: list[tuple[int, int]] = []
    for m in re.finditer(r"'(?:''|[^'])*'", sql):
        ranges.append((m.start(), m.end()))
    return ranges


def _is_inside_string(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """Return True if *pos* falls inside any of the given string-literal ranges."""
    return any(start < pos < end for start, end in ranges)


def _matches_outside_strings(pattern: re.Pattern[str], sql: str) -> bool:
    """Return True if *pattern* has at least one match whose start is outside a string literal."""
    ranges = _string_ranges(sql)
    return any(not _is_inside_string(m.start(), ranges) for m in pattern.finditer(sql))


def _replace_outside_strings(
    pattern: re.Pattern[str], repl: str | Callable[..., str], sql: str
) -> str:
    """Apply *pattern* replacement only when the match start is outside a string literal.

    Processes matches right-to-left so index positions remain valid.
    """
    ranges = _string_ranges(sql)
    matches = list(pattern.finditer(sql))
    # Process from right to left so earlier indices stay valid
    for m in reversed(matches):
        if not _is_inside_string(m.start(), ranges):
            replacement = repl(m) if callable(repl) else m.expand(repl)
            sql = sql[: m.start()] + replacement + sql[m.end() :]
    return sql


# ---------------------------------------------------------------------------
# 1. NVL → COALESCE  (but NOT NVL2)
# ---------------------------------------------------------------------------

_NVL_RE = re.compile(r"\bNVL\s*" + _BALANCED_PARENS, re.IGNORECASE)
# Negative lookahead version to exclude NVL2
_NVL_ONLY_RE = re.compile(r"\bNVL\b(?!2)\s*" + _BALANCED_PARENS, re.IGNORECASE)


class NVLRule(Rule):
    name = "nvl_to_coalesce"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 10
    description = "NVL(a, b) -> COALESCE(a, b)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_NVL_ONLY_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"COALESCE({m.group(1)})"

        return _replace_outside_strings(_NVL_ONLY_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 2. NVL2 → CASE WHEN ... IS NOT NULL THEN ... ELSE ... END
# ---------------------------------------------------------------------------

_NVL2_RE = re.compile(r"\bNVL2\s*" + _BALANCED_PARENS, re.IGNORECASE)


class NVL2Rule(Rule):
    name = "nvl2_to_case"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 20
    description = "NVL2(a, b, c) -> CASE WHEN a IS NOT NULL THEN b ELSE c END"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_NVL2_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            args = _split_args(m.group(1))
            if len(args) != 3:
                return m.group(0)  # leave unchanged
            a, b, c = (x.strip() for x in args)
            return f"CASE WHEN {a} IS NOT NULL THEN {b} ELSE {c} END"

        return _replace_outside_strings(_NVL2_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 3. DECODE → CASE
# ---------------------------------------------------------------------------

_DECODE_RE = re.compile(r"\bDECODE\s*" + _BALANCED_PARENS, re.IGNORECASE)


class DECODERule(Rule):
    name = "decode_to_case"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 30
    description = (
        "DECODE(expr, s1, r1, ..., default) -> CASE expr WHEN s1 THEN r1 ... ELSE default END"
    )

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_DECODE_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            args = _split_args(m.group(1))
            if len(args) < 3:
                return m.group(0)
            expr = args[0].strip()
            pairs = args[1:]
            # Check if any search value is NULL — needs searched CASE form
            for i in range(0, len(pairs) - 1, 2):
                if pairs[i].strip().upper() == "NULL":
                    return _decode_with_null(expr, pairs)
            parts: list[str] = [f"CASE {expr}"]
            i = 0
            while i + 1 < len(pairs):
                search_val = pairs[i].strip()
                result_val = pairs[i + 1].strip()
                parts.append(f"WHEN {search_val} THEN {result_val}")
                i += 2
            if i < len(pairs):
                parts.append(f"ELSE {pairs[i].strip()}")
            parts.append("END")
            return " ".join(parts)

        return _replace_outside_strings(_DECODE_RE, _repl, sql)


def _decode_with_null(expr: str, pairs: list[str]) -> str:
    """Handle DECODE where one of the search values is NULL."""
    parts: list[str] = ["CASE"]
    i = 0
    while i + 1 < len(pairs):
        search_val = pairs[i].strip()
        result_val = pairs[i + 1].strip()
        if search_val.upper() == "NULL":
            parts.append(f"WHEN {expr} IS NULL THEN {result_val}")
        else:
            parts.append(f"WHEN {expr} = {search_val} THEN {result_val}")
        i += 2
    if i < len(pairs):
        parts.append(f"ELSE {pairs[i].strip()}")
    parts.append("END")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 4. SUBSTR → SUBSTRING
# ---------------------------------------------------------------------------

_SUBSTR3_RE = re.compile(r"\bSUBSTR\s*\(\s*(.+?)\s*,\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)
_SUBSTR2_RE = re.compile(r"\bSUBSTR\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)
_SUBSTR_DETECT_RE = re.compile(r"\bSUBSTR\s*\(", re.IGNORECASE)


class SUBSTRRule(Rule):
    name = "substr_to_substring"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 40
    description = "SUBSTR(s, pos, len) -> SUBSTRING(s FROM pos FOR len)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_SUBSTR_DETECT_RE, sql)

    def apply(self, sql: str) -> str:
        # 3-arg first
        result = _replace_outside_strings(
            _SUBSTR3_RE,
            lambda m: f"SUBSTRING({m.group(1)} FROM {m.group(2)} FOR {m.group(3)})",
            sql,
        )
        result = _replace_outside_strings(
            _SUBSTR2_RE,
            lambda m: f"SUBSTRING({m.group(1)} FROM {m.group(2)})",
            result,
        )
        return result


# ---------------------------------------------------------------------------
# 5. INSTR → POSITION (2-arg form only)
# ---------------------------------------------------------------------------

_INSTR_RE = re.compile(r"\bINSTR\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)


class INSTRRule(Rule):
    name = "instr_to_position"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 50
    description = "INSTR(s, sub) -> POSITION(sub IN s)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_INSTR_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _INSTR_RE,
            lambda m: f"POSITION({m.group(2)} IN {m.group(1)})",
            sql,
        )


# ---------------------------------------------------------------------------
# 6. TO_NUMBER → CAST ... AS NUMERIC  (single-arg form only)
# ---------------------------------------------------------------------------

_TO_NUMBER1_RE = re.compile(r"\bTO_NUMBER\s*\(\s*([^,)]+)\s*\)", re.IGNORECASE)


class TONUMBERRule(Rule):
    name = "to_number_to_cast"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 60
    description = "TO_NUMBER(s) -> CAST(s AS NUMERIC); 2-arg form unchanged"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_TO_NUMBER1_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _TO_NUMBER1_RE,
            lambda m: f"CAST({m.group(1).strip()} AS NUMERIC)",
            sql,
        )


# ---------------------------------------------------------------------------
# 7. LISTAGG → STRING_AGG
# ---------------------------------------------------------------------------

_LISTAGG_RE = re.compile(
    r"\bLISTAGG\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)\s*WITHIN\s+GROUP\s*\(\s*ORDER\s+BY\s+(.+?)\s*\)",
    re.IGNORECASE,
)


class LISTAGGRule(Rule):
    name = "listagg_to_string_agg"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 70
    description = (
        "LISTAGG(col, sep) WITHIN GROUP (ORDER BY ...) -> STRING_AGG(col, sep ORDER BY ...)"
    )

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_LISTAGG_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _LISTAGG_RE,
            lambda m: (
                f"STRING_AGG({m.group(1).strip()}, {m.group(2).strip()}"
                f" ORDER BY {m.group(3).strip()})"
            ),
            sql,
        )


# ---------------------------------------------------------------------------
# 8. REGEXP_LIKE → ~
# ---------------------------------------------------------------------------

_REGEXP_LIKE_RE = re.compile(r"\bREGEXP_LIKE\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)


class REGEXPLIKERule(Rule):
    name = "regexp_like_to_tilde"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 80
    description = "REGEXP_LIKE(s, p) -> s ~ p"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_REGEXP_LIKE_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _REGEXP_LIKE_RE,
            lambda m: f"{m.group(1).strip()} ~ {m.group(2).strip()}",
            sql,
        )


# ---------------------------------------------------------------------------
# 9. REGEXP_SUBSTR → SUBSTRING ... FROM
# ---------------------------------------------------------------------------

_REGEXP_SUBSTR_RE = re.compile(r"\bREGEXP_SUBSTR\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", re.IGNORECASE)


class REGEXPSUBSTRRule(Rule):
    name = "regexp_substr_to_substring"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 90
    description = "REGEXP_SUBSTR(s, p) -> SUBSTRING(s FROM p)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_REGEXP_SUBSTR_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _REGEXP_SUBSTR_RE,
            lambda m: f"SUBSTRING({m.group(1).strip()} FROM {m.group(2).strip()})",
            sql,
        )


# ---------------------------------------------------------------------------
# 10. LENGTHB → OCTET_LENGTH
# ---------------------------------------------------------------------------

_LENGTHB_RE = re.compile(r"\bLENGTHB\s*" + _BALANCED_PARENS, re.IGNORECASE)


class LENGTHBRule(Rule):
    name = "lengthb_to_octet_length"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 100
    description = "LENGTHB(s) -> OCTET_LENGTH(s)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_LENGTHB_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"OCTET_LENGTH({m.group(1)})"

        return _replace_outside_strings(_LENGTHB_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 11. RAWTOHEX → ENCODE
# ---------------------------------------------------------------------------

_RAWTOHEX_RE = re.compile(r"\bRAWTOHEX\s*" + _BALANCED_PARENS, re.IGNORECASE)


class RAWTOHEXRule(Rule):
    name = "rawtohex_to_encode"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 110
    description = "RAWTOHEX(r) -> ENCODE(r, 'hex')"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_RAWTOHEX_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"ENCODE({m.group(1)}, 'hex')"

        return _replace_outside_strings(_RAWTOHEX_RE, _repl, sql)


# ---------------------------------------------------------------------------
# Utility: split comma-separated args respecting parentheses and quotes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 12. HEXTORAW → DECODE ... 'hex'
# ---------------------------------------------------------------------------

_HEXTORAW_RE = re.compile(r"\bHEXTORAW\s*" + _BALANCED_PARENS, re.IGNORECASE)


class HEXTORAWRule(Rule):
    name = "hextoraw_to_decode"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 115
    description = "HEXTORAW(x) -> DECODE(x, 'hex')"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_HEXTORAW_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"DECODE({m.group(1)}, 'hex')"

        return _replace_outside_strings(_HEXTORAW_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 13. WM_CONCAT → STRING_AGG
# ---------------------------------------------------------------------------

_WM_CONCAT_RE = re.compile(r"\bWM_CONCAT\s*" + _BALANCED_PARENS, re.IGNORECASE)


class WMConcatRule(Rule):
    name = "wm_concat_to_string_agg"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 120
    description = "WM_CONCAT(col) -> STRING_AGG(col, ',')"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_WM_CONCAT_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"STRING_AGG({m.group(1)}, ',')"

        return _replace_outside_strings(_WM_CONCAT_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 14. RATIO_TO_REPORT → expr / SUM(expr) OVER
# ---------------------------------------------------------------------------

_RATIO_RE = re.compile(
    r"\bRATIO_TO_REPORT\s*\(\s*(.+?)\s*\)\s*OVER\s*(\([^)]*\))",
    re.IGNORECASE,
)


class RatioToReportRule(Rule):
    name = "ratio_to_report_to_division"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 125
    description = "RATIO_TO_REPORT(x) OVER (...) -> x::numeric / SUM(x) OVER (...)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_RATIO_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            expr = m.group(1).strip()
            window = m.group(2)
            return f"{expr}::numeric / SUM({expr}) OVER {window}"

        return _replace_outside_strings(_RATIO_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 15. SYS_GUID() → gen_random_uuid()
# ---------------------------------------------------------------------------

_SYS_GUID_RE = re.compile(r"\bSYS_GUID\s*\(\s*\)", re.IGNORECASE)


class SYSGUIDRule(Rule):
    name = "sys_guid_to_gen_random_uuid"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 130
    description = "SYS_GUID() -> gen_random_uuid()"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_SYS_GUID_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_SYS_GUID_RE, "gen_random_uuid()", sql)


# ---------------------------------------------------------------------------
# Utility: split comma-separated args respecting parentheses and quotes
# ---------------------------------------------------------------------------


def _split_args(text: str) -> list[str]:
    """Split a comma-separated argument string, respecting nested parentheses and quotes."""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    in_quote = False
    for ch in text:
        if ch == "'" and not in_quote:
            in_quote = True
            current.append(ch)
        elif ch == "'" and in_quote:
            current.append(ch)
            in_quote = False
        elif in_quote:
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current))
    return args
