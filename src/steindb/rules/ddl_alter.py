# src/steindb/rules/ddl_alter.py
"""DDL ALTER TABLE rules: convert Oracle ALTER TABLE syntax to PostgreSQL.

Oracle uses ADD (col type) with parentheses and MODIFY; PostgreSQL
uses ADD COLUMN and ALTER COLUMN.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class AlterAddColumnRule(Rule):
    """ALTER TABLE t ADD (col type) -> ALTER TABLE t ADD COLUMN col type.

    Oracle wraps the column definition in parentheses; PostgreSQL uses
    ADD COLUMN without parens.
    """

    name = "alter_add_column"
    category = RuleCategory.DDL_ALTER
    priority = 10
    description = "Convert ALTER TABLE ADD (...) to ADD COLUMN"

    _PATTERN = re.compile(
        r"\bADD\s*\(\s*(\w+)\s+((?:[^()]*|\([^()]*\))*?)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        # Match ADD (...) but not ADD CONSTRAINT
        if re.search(r"\bADD\s*\(", sql, re.IGNORECASE):
            # Exclude ADD CONSTRAINT patterns
            # Exclude ADD CONSTRAINT patterns
            return not re.search(r"\bADD\s+CONSTRAINT\b", sql, re.IGNORECASE)
        return False

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            col_def = m.group(2).strip()
            return f"ADD COLUMN {col_name} {col_def}"

        return self._PATTERN.sub(_replace, sql)


class AlterModifyColumnRule(Rule):
    """ALTER TABLE t MODIFY (col type) -> ALTER TABLE t ALTER COLUMN col TYPE type.

    Handles type changes only (not NOT NULL which is a separate rule).
    """

    name = "alter_modify_column"
    category = RuleCategory.DDL_ALTER
    priority = 20
    description = "Convert ALTER TABLE MODIFY to ALTER COLUMN ... TYPE"

    _PATTERN = re.compile(
        r"\bMODIFY\s*\(\s*(\w+)\s+((?:[^()]*|\([^()]*\))*?)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        if not re.search(r"\bMODIFY\s*\(", sql, re.IGNORECASE):
            return False
        # Check if this is a NOT NULL modification (handled by separate rule)
        m = self._PATTERN.search(sql)
        if m:
            col_def = m.group(2).strip().upper()
            if col_def == "NOT NULL" or col_def.endswith(" NOT NULL"):
                # If it's ONLY NOT NULL (no type change), let the NOT NULL rule handle it
                # If it has type + NOT NULL, we handle the type part
                return col_def != "NOT NULL"
        return bool(m)

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            col_def = m.group(2).strip()
            # If col_def contains NOT NULL, handle that too
            upper_def = col_def.upper()
            if upper_def.endswith("NOT NULL"):
                type_part = col_def[: col_def.upper().rfind("NOT NULL")].strip()
                return (
                    f"ALTER COLUMN {col_name} TYPE {type_part},"
                    f" ALTER COLUMN {col_name} SET NOT NULL"
                )
            return f"ALTER COLUMN {col_name} TYPE {col_def}"

        return self._PATTERN.sub(_replace, sql)


class AlterModifyNotNullRule(Rule):
    """ALTER TABLE t MODIFY (col NOT NULL) -> ALTER TABLE t ALTER COLUMN col SET NOT NULL.

    Handles the case where MODIFY only sets NOT NULL without changing type.
    """

    name = "alter_modify_not_null"
    category = RuleCategory.DDL_ALTER
    priority = 30
    description = "Convert ALTER TABLE MODIFY NOT NULL"

    _PATTERN = re.compile(
        r"\bMODIFY\s*\(\s*(\w+)\s+(?:\S+\s+)?NOT\s+NULL\s*\)",
        re.IGNORECASE,
    )
    _SIMPLE_PATTERN = re.compile(
        r"\bMODIFY\s*\(\s*(\w+)\s+NOT\s+NULL\s*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        # Only match MODIFY (col NOT NULL) without type change
        return bool(self._SIMPLE_PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            return f"ALTER COLUMN {col_name} SET NOT NULL"

        return self._SIMPLE_PATTERN.sub(_replace, sql)


class AlterDropColumnRule(Rule):
    """ALTER TABLE t DROP COLUMN col — same syntax, pass through."""

    name = "alter_drop_column"
    category = RuleCategory.DDL_ALTER
    priority = 40
    description = "Pass through ALTER TABLE DROP COLUMN"

    _PATTERN = re.compile(
        r"\bALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return sql


# All rules in this module, for easy registration
DDL_ALTER_RULES: list[type[Rule]] = [
    AlterAddColumnRule,
    AlterModifyColumnRule,
    AlterModifyNotNullRule,
    AlterDropColumnRule,
]
