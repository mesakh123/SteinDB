# src/steindb/rules/syntax_joins.py
"""Oracle (+) outer join syntax to ANSI JOIN conversion."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _string_ranges(sql: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"'(?:''|[^'])*'", sql)]


def _is_inside_string(pos: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < pos < end for start, end in ranges)


def _outside_strings_has(pattern: re.Pattern[str], sql: str) -> bool:
    """Return True if pattern matches outside string literals."""
    ranges = _string_ranges(sql)
    return any(not _is_inside_string(m.start(), ranges) for m in pattern.finditer(sql))


# Detect (+) anywhere outside strings
_PLUS_JOIN_RE = re.compile(r"\(\+\)")

# ---------------------------------------------------------------------------
# Oracle (+) outer join rule
# ---------------------------------------------------------------------------

# Pattern to detect old-style comma joins in FROM clause
_FROM_TABLES_RE = re.compile(
    r"\bFROM\s+((?:[a-z_]\w*(?:\.\w+)?\s+[a-z_]\w*\s*,\s*)*[a-z_]\w*(?:\.\w+)?\s+[a-z_]\w*)",
    re.IGNORECASE,
)

# Pattern to parse individual WHERE conditions with (+)
# Matches: <expr>(+) = <expr>  or  <expr> = <expr>(+)
_COND_PLUS_RE = re.compile(
    r"(\b[\w.]+)\s*(\(\+\))?\s*=\s*(\b[\w.]+)\s*(\(\+\))?",
    re.IGNORECASE,
)


class OracleOuterJoinRule(Rule):
    name = "oracle_plus_to_ansi_join"
    category = RuleCategory.SYNTAX_JOINS
    priority = 10
    description = "WHERE a.id = b.id(+) -> LEFT JOIN b ON a.id = b.id"
    confidence = 0.95  # Complex cases may not be perfect

    def matches(self, sql: str) -> bool:
        return _outside_strings_has(_PLUS_JOIN_RE, sql)

    def apply(self, sql: str) -> str:
        return _convert_plus_joins(sql)


def _convert_plus_joins(sql: str) -> str:
    """Convert Oracle (+) joins to ANSI JOIN syntax.

    Strategy:
    1. Parse the FROM clause to identify tables and aliases.
    2. Parse the WHERE clause to find conditions with (+).
    3. Determine join type (LEFT, RIGHT, FULL) based on (+) placement.
    4. Rebuild the query with explicit JOIN ... ON syntax.
    """
    # Split into segments: everything before FROM, FROM clause, WHERE clause, rest
    from_match = re.search(r"\bFROM\b\s+", sql, re.IGNORECASE)
    if from_match is None:
        return sql

    # Find WHERE clause
    where_match = re.search(r"\bWHERE\b\s+", sql, re.IGNORECASE)
    if where_match is None:
        return sql

    prefix = sql[: from_match.start()]
    from_keyword = sql[from_match.start() : from_match.end()]

    # Find end boundaries: GROUP BY, ORDER BY, HAVING, UNION, LIMIT, or end of string
    tail_match = re.search(
        r"\b(GROUP\s+BY|ORDER\s+BY|HAVING|UNION|INTERSECT|EXCEPT|MINUS|LIMIT|FETCH)\b",
        sql[where_match.end() :],
        re.IGNORECASE,
    )
    if tail_match:
        where_end = where_match.end() + tail_match.start()
        tail = sql[where_end:]
    else:
        where_end = len(sql)
        tail = ""

    from_text = sql[from_match.end() : where_match.start()].strip()
    where_text = sql[where_match.end() : where_end].strip()

    # Parse tables from FROM clause: "table1 alias1, table2 alias2, ..."
    tables = _parse_from_tables(from_text)
    if not tables:
        return sql

    # Parse WHERE conditions
    conditions = _parse_where_conditions(where_text)

    # Separate (+) conditions from normal conditions
    plus_conditions: list[_JoinCondition] = []
    normal_conditions: list[str] = []

    for cond in conditions:
        if "(+)" in cond:
            parsed = _parse_plus_condition(cond)
            if parsed:
                plus_conditions.append(parsed)
            else:
                normal_conditions.append(cond.replace("(+)", ""))
        else:
            normal_conditions.append(cond)

    if not plus_conditions:
        return sql

    # Build join graph: determine which tables join to which
    # The table whose column has (+) is the "optional" table (outer side)
    first_table = tables[0]
    joined_tables: dict[str, _JoinInfo] = {}

    for pc in plus_conditions:
        # (+) on right side: LEFT JOIN the right table
        # (+) on left side: RIGHT JOIN the left table
        # (+) on both sides: FULL OUTER JOIN
        left_alias = _extract_alias(pc.left_col)
        right_alias = _extract_alias(pc.right_col)

        if pc.plus_on_left and pc.plus_on_right:
            join_type = "FULL OUTER JOIN"
            optional_alias = right_alias
        elif pc.plus_on_right:
            join_type = "LEFT JOIN"
            optional_alias = right_alias
        else:  # plus_on_left
            join_type = "RIGHT JOIN"
            optional_alias = left_alias

        clean_cond = f"{pc.left_col} = {pc.right_col}"
        if optional_alias and optional_alias in joined_tables:
            joined_tables[optional_alias].conditions.append(clean_cond)
        elif optional_alias:
            joined_tables[optional_alias] = _JoinInfo(
                join_type=join_type,
                conditions=[clean_cond],
            )

    # Also handle conditions where (+) column's alias matches a joined table
    # (e.g., d.active(+) = 'Y' should become part of the JOIN ON clause)
    remaining_normal: list[str] = []
    for cond in normal_conditions:
        assigned = False
        for alias, info in joined_tables.items():
            # Check if any column reference in the condition belongs to this alias
            if re.search(rf"\b{re.escape(alias)}\.\w+", cond) and alias != first_table[1]:
                info.conditions.append(cond)
                assigned = True
                break
        if not assigned:
            remaining_normal.append(cond)

    # Build the new FROM clause with JOINs
    # First table stays as-is
    from_parts: list[str] = [f"{first_table[0]} {first_table[1]}"]

    # Track which tables have been joined
    joined_aliases: set[str] = {first_table[1]}

    # Tables in original order, minus the first
    for tbl_name, tbl_alias in tables[1:]:
        if tbl_alias in joined_tables:
            info = joined_tables[tbl_alias]
            on_clause = " AND ".join(info.conditions)
            from_parts.append(f"{info.join_type} {tbl_name} {tbl_alias} ON {on_clause}")
        else:
            # No (+) for this table — check if it has normal join conditions
            # with already-joined tables
            inner_conds: list[str] = []
            still_remaining: list[str] = []
            for cond in remaining_normal:
                if re.search(rf"\b{re.escape(tbl_alias)}\.\w+", cond) and any(
                    re.search(rf"\b{re.escape(a)}\.\w+", cond) for a in joined_aliases
                ):
                    inner_conds.append(cond)
                else:
                    still_remaining.append(cond)
            remaining_normal = still_remaining

            if inner_conds:
                on_clause = " AND ".join(inner_conds)
                from_parts.append(f"INNER JOIN {tbl_name} {tbl_alias} ON {on_clause}")
            else:
                from_parts.append(f", {tbl_name} {tbl_alias}")

        joined_aliases.add(tbl_alias)

    new_from = "\n".join(from_parts)

    # Build new WHERE clause with remaining conditions
    new_where = f"\nWHERE {' AND '.join(remaining_normal)}" if remaining_normal else ""

    result = (
        f"{prefix}{'FROM' if from_keyword.strip().upper() == 'FROM' else from_keyword.rstrip()}"
    )
    result = f"{prefix}FROM {new_from}{new_where}{tail}"
    return result


class _JoinCondition:
    """Parsed (+) condition."""

    def __init__(
        self,
        left_col: str,
        right_col: str,
        plus_on_left: bool,
        plus_on_right: bool,
    ) -> None:
        self.left_col = left_col
        self.right_col = right_col
        self.plus_on_left = plus_on_left
        self.plus_on_right = plus_on_right


class _JoinInfo:
    """Accumulated join information for one table."""

    def __init__(self, join_type: str, conditions: list[str]) -> None:
        self.join_type = join_type
        self.conditions = conditions


def _parse_from_tables(from_text: str) -> list[tuple[str, str]]:
    """Parse 'table1 alias1, table2 alias2' into [(table, alias), ...]."""
    tables: list[tuple[str, str]] = []
    for part in from_text.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if len(tokens) >= 2:
            tables.append((tokens[0], tokens[1]))
        elif len(tokens) == 1:
            tables.append((tokens[0], tokens[0]))
    return tables


def _parse_where_conditions(where_text: str) -> list[str]:
    """Split WHERE clause into individual conditions on AND boundaries.

    Respects parenthesised groups.
    """
    # Simple split on AND that is not inside parentheses
    conditions: list[str] = []
    depth = 0
    current: list[str] = []
    tokens = re.split(r"(\bAND\b)", where_text, flags=re.IGNORECASE)

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.upper().strip() == "AND" and depth == 0:
            conditions.append("".join(current).strip())
            current = []
        else:
            depth += token.count("(") - token.count(")")
            current.append(token)
        i += 1
    if current:
        conditions.append("".join(current).strip())

    return [c for c in conditions if c]


def _parse_plus_condition(cond: str) -> _JoinCondition | None:
    """Parse a condition like 'a.id = b.id(+)' into a _JoinCondition."""
    # Match: expr(+) = expr  or  expr = expr(+)  or  expr(+) = expr(+)
    m = re.match(
        r"\s*([\w.]+)\s*(\(\+\))?\s*=\s*([\w.']+)\s*(\(\+\))?\s*$",
        cond.strip(),
    )
    if not m:
        return None
    left_col = m.group(1)
    plus_left = m.group(2) is not None
    right_col = m.group(3)
    plus_right = m.group(4) is not None
    if not plus_left and not plus_right:
        return None
    return _JoinCondition(left_col, right_col, plus_left, plus_right)


def _extract_alias(col_ref: str) -> str | None:
    """Extract the alias from 'alias.column'."""
    if "." in col_ref:
        return col_ref.split(".")[0]
    return None
