# src/steindb/rules/p2o_ddl_alter.py
"""P2O DDL ALTER TABLE rules: PostgreSQL ALTER TABLE syntax -> Oracle.

PostgreSQL uses ADD COLUMN, ALTER COLUMN ... TYPE, ALTER COLUMN ... SET NOT NULL;
Oracle uses ADD (col type), MODIFY (col type), MODIFY (col NOT NULL).
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2OAlterAddColumnRule(Rule):
    """ALTER TABLE t ADD COLUMN col type -> ALTER TABLE t ADD (col type).

    PostgreSQL uses ADD COLUMN; Oracle wraps column definition in parentheses
    and omits the COLUMN keyword.
    """

    name = "p2o_alter_add_column"
    category = RuleCategory.P2O_DDL_ALTER
    priority = 10
    description = "Convert ADD COLUMN to ADD (...)"

    _PATTERN = re.compile(
        r"\bADD\s+COLUMN\s+(\w+)\s+((?:[^,;]*|\([^)]*\))*)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        return bool(re.search(r"\bADD\s+COLUMN\b", sql, re.IGNORECASE))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            col_def = m.group(2).strip()
            return f"ADD ({col_name} {col_def})"

        return self._PATTERN.sub(_replace, sql)


class P2OAlterColumnTypeRule(Rule):
    """ALTER TABLE t ALTER COLUMN col TYPE type -> ALTER TABLE t MODIFY (col type).

    PostgreSQL uses ALTER COLUMN ... TYPE; Oracle uses MODIFY (...).
    """

    name = "p2o_alter_column_type"
    category = RuleCategory.P2O_DDL_ALTER
    priority = 20
    description = "Convert ALTER COLUMN ... TYPE to MODIFY (...)"

    _PATTERN = re.compile(
        r"\bALTER\s+COLUMN\s+(\w+)\s+TYPE\s+(\w+(?:\s*\([^)]*\))?)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            col_type = m.group(2).strip()
            return f"MODIFY ({col_name} {col_type})"

        return self._PATTERN.sub(_replace, sql)


class P2OAlterColumnSetNotNullRule(Rule):
    """ALTER TABLE t ALTER COLUMN col SET NOT NULL -> ALTER TABLE t MODIFY (col NOT NULL)."""

    name = "p2o_alter_column_set_not_null"
    category = RuleCategory.P2O_DDL_ALTER
    priority = 30
    description = "Convert ALTER COLUMN ... SET NOT NULL to MODIFY (... NOT NULL)"

    _PATTERN = re.compile(
        r"\bALTER\s+COLUMN\s+(\w+)\s+SET\s+NOT\s+NULL\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "ALTER TABLE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace(m: re.Match[str]) -> str:
            col_name = m.group(1)
            return f"MODIFY ({col_name} NOT NULL)"

        return self._PATTERN.sub(_replace, sql)


class P2OAlterDropColumnRule(Rule):
    """ALTER TABLE t DROP COLUMN col -- same syntax, pass through."""

    name = "p2o_alter_drop_column"
    category = RuleCategory.P2O_DDL_ALTER
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
P2O_DDL_ALTER_RULES: list[type[Rule]] = [
    P2OAlterAddColumnRule,
    P2OAlterColumnTypeRule,
    P2OAlterColumnSetNotNullRule,
    P2OAlterDropColumnRule,
]
