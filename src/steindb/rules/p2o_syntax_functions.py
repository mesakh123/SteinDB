# src/steindb/rules/p2o_syntax_functions.py
"""P2O function mapping rules: PostgreSQL functions to Oracle equivalents."""

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


# ---------------------------------------------------------------------------
# 1. COALESCE(a, b) -> NVL(a, b)  (2-arg only; 3+ args keep COALESCE)
# ---------------------------------------------------------------------------

_COALESCE_RE = re.compile(r"\bCOALESCE\s*" + _BALANCED_PARENS, re.IGNORECASE)


class CoalesceToNVLRule(Rule):
    name = "coalesce_to_nvl"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 10
    description = "COALESCE(a, b) -> NVL(a, b) (2-arg only)"

    def matches(self, sql: str) -> bool:
        if not _matches_outside_strings(_COALESCE_RE, sql):
            return False
        # Check if any match has exactly 2 args
        ranges = _string_ranges(sql)
        for m in _COALESCE_RE.finditer(sql):
            if not _is_inside_string(m.start(), ranges):
                args = _split_args(m.group(1))
                if len(args) == 2:
                    return True
        return False

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            args = _split_args(m.group(1))
            if len(args) == 2:
                # WARNING: NVL always evaluates both arguments unlike COALESCE
                # which short-circuits. Side-effect-producing expressions may
                # behave differently. For safety, add inline comment.
                return (
                    f"NVL({m.group(1)})"
                    " /* NOTE: NVL evaluates both args; COALESCE short-circuits */"
                )
            return m.group(0)  # 3+ args: keep COALESCE

        return _replace_outside_strings(_COALESCE_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 2. SUBSTRING(s FROM p FOR l) -> SUBSTR(s, p, l)
#    SUBSTRING(s FROM p) -> SUBSTR(s, p)
# ---------------------------------------------------------------------------

_SUBSTRING_FROM_FOR_RE = re.compile(
    r"\bSUBSTRING\s*\(\s*(.+?)\s+FROM\s+(.+?)\s+FOR\s+(.+?)\s*\)",
    re.IGNORECASE,
)
_SUBSTRING_FROM_RE = re.compile(
    r"\bSUBSTRING\s*\(\s*(.+?)\s+FROM\s+(.+?)\s*\)",
    re.IGNORECASE,
)
_SUBSTRING_DETECT_RE = re.compile(r"\bSUBSTRING\s*\(", re.IGNORECASE)


class SubstringToSubstrRule(Rule):
    name = "substring_to_substr"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 20
    description = "SUBSTRING(s FROM p FOR l) -> SUBSTR(s, p, l)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_SUBSTRING_DETECT_RE, sql)

    def apply(self, sql: str) -> str:
        # 3-arg form first (FROM...FOR)
        result = _replace_outside_strings(
            _SUBSTRING_FROM_FOR_RE,
            lambda m: f"SUBSTR({m.group(1).strip()}, {m.group(2).strip()}, {m.group(3).strip()})",
            sql,
        )
        # 2-arg form (FROM only)
        result = _replace_outside_strings(
            _SUBSTRING_FROM_RE,
            lambda m: f"SUBSTR({m.group(1).strip()}, {m.group(2).strip()})",
            result,
        )
        return result


# ---------------------------------------------------------------------------
# 3. POSITION(sub IN s) -> INSTR(s, sub)
# ---------------------------------------------------------------------------

_POSITION_RE = re.compile(r"\bPOSITION\s*\(\s*(.+?)\s+IN\s+(.+?)\s*\)", re.IGNORECASE)


class PositionToInstrRule(Rule):
    name = "position_to_instr"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 30
    description = "POSITION(sub IN s) -> INSTR(s, sub)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_POSITION_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _POSITION_RE,
            lambda m: f"INSTR({m.group(2).strip()}, {m.group(1).strip()})",
            sql,
        )


# ---------------------------------------------------------------------------
# 4. STRING_AGG(col, sep ORDER BY x) -> LISTAGG(col, sep) WITHIN GROUP (ORDER BY x)
# ---------------------------------------------------------------------------

_STRING_AGG_RE = re.compile(
    r"\bSTRING_AGG\s*\(\s*(.+?)\s*,\s*(.+?)\s+ORDER\s+BY\s+(.+?)\s*\)",
    re.IGNORECASE,
)


class StringAggToListaggRule(Rule):
    name = "string_agg_to_listagg"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 40
    description = "STRING_AGG(col, sep ORDER BY x) -> LISTAGG(col, sep) WITHIN GROUP (ORDER BY x)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_STRING_AGG_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _STRING_AGG_RE,
            lambda m: (
                f"LISTAGG({m.group(1).strip()}, {m.group(2).strip()}) "
                f"WITHIN GROUP (ORDER BY {m.group(3).strip()})"
            ),
            sql,
        )


# ---------------------------------------------------------------------------
# 5. s ~ pattern -> REGEXP_LIKE(s, pattern)
# ---------------------------------------------------------------------------

# Match: identifier_or_expr ~ 'pattern' (not ~* which is case-insensitive)
_TILDE_RE = re.compile(
    r"(\b\w+(?:\.\w+)?)\s+~\s+('(?:''|[^'])*')",
    re.IGNORECASE,
)


class TildeToRegexpLikeRule(Rule):
    name = "tilde_to_regexp_like"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 50
    description = "s ~ pattern -> REGEXP_LIKE(s, pattern)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_TILDE_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _TILDE_RE,
            lambda m: f"REGEXP_LIKE({m.group(1)}, {m.group(2)})",
            sql,
        )


# ---------------------------------------------------------------------------
# 6. CAST(x AS NUMERIC) -> TO_NUMBER(x)  (simple cases)
# ---------------------------------------------------------------------------

_CAST_NUMERIC_RE = re.compile(
    r"\bCAST\s*\(\s*(.+?)\s+AS\s+NUMERIC\s*\)",
    re.IGNORECASE,
)


class CastNumericToToNumberRule(Rule):
    name = "cast_numeric_to_to_number"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 60
    description = "CAST(x AS NUMERIC) -> TO_NUMBER(x)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_CAST_NUMERIC_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _CAST_NUMERIC_RE,
            lambda m: f"TO_NUMBER({m.group(1).strip()})",
            sql,
        )


# ---------------------------------------------------------------------------
# 7. OCTET_LENGTH(s) -> LENGTHB(s)
# ---------------------------------------------------------------------------

_OCTET_LENGTH_RE = re.compile(r"\bOCTET_LENGTH\s*" + _BALANCED_PARENS, re.IGNORECASE)


class OctetLengthToLengthbRule(Rule):
    name = "octet_length_to_lengthb"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 70
    description = "OCTET_LENGTH(s) -> LENGTHB(s)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_OCTET_LENGTH_RE, sql)

    def apply(self, sql: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            return f"LENGTHB({m.group(1)})"

        return _replace_outside_strings(_OCTET_LENGTH_RE, _repl, sql)


# ---------------------------------------------------------------------------
# 8. ENCODE(r, 'hex') -> RAWTOHEX(r)
# ---------------------------------------------------------------------------

_ENCODE_HEX_RE = re.compile(
    r"\bENCODE\s*\(\s*(.+?)\s*,\s*'hex'\s*\)",
    re.IGNORECASE,
)


class EncodeHexToRawtohexRule(Rule):
    name = "encode_hex_to_rawtohex"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 80
    description = "ENCODE(r, 'hex') -> RAWTOHEX(r)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_ENCODE_HEX_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(
            _ENCODE_HEX_RE,
            lambda m: f"RAWTOHEX({m.group(1).strip()})",
            sql,
        )


# ---------------------------------------------------------------------------
# 9. gen_random_uuid() -> SYS_GUID()
# ---------------------------------------------------------------------------

_GEN_RANDOM_UUID_RE = re.compile(r"\bgen_random_uuid\s*\(\s*\)", re.IGNORECASE)


class GenRandomUuidToSysGuidRule(Rule):
    name = "gen_random_uuid_to_sys_guid"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 90
    description = "gen_random_uuid() -> SYS_GUID()"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_GEN_RANDOM_UUID_RE, sql)

    def apply(self, sql: str) -> str:
        return _replace_outside_strings(_GEN_RANDOM_UUID_RE, "SYS_GUID()", sql)


# ---------------------------------------------------------------------------
# 10. Boolean literals: true -> 1, false -> 0
# ---------------------------------------------------------------------------

_TRUE_RE = re.compile(r"\btrue\b", re.IGNORECASE)
_FALSE_RE = re.compile(r"\bfalse\b", re.IGNORECASE)


class BooleanLiteralRule(Rule):
    name = "boolean_literals_to_numeric"
    category = RuleCategory.P2O_SYNTAX_FUNCTIONS
    priority = 95
    description = "true -> 1, false -> 0 (Oracle has no BOOLEAN type in SQL)"

    def matches(self, sql: str) -> bool:
        return _matches_outside_strings(_TRUE_RE, sql) or _matches_outside_strings(_FALSE_RE, sql)

    def apply(self, sql: str) -> str:
        result = _replace_outside_strings(_TRUE_RE, "1", sql)
        return _replace_outside_strings(_FALSE_RE, "0", result)
