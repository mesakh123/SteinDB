# src/steindb/rules/ddl_tables.py
"""DDL Table rules: CREATE TABLE conversion, CTAS, COMMENT, RENAME.

These rules handle structural DDL transformations for table creation
and modification. Data type conversions are handled by datatype rules
that run earlier in the pipeline.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class CreateTableRule(Rule):
    """Handle Oracle-specific syntax within CREATE TABLE statements.

    - DEFAULT SYSDATE -> DEFAULT CURRENT_TIMESTAMP
    - GLOBAL TEMPORARY TABLE -> TEMP TABLE
    """

    name = "create_table"
    category = RuleCategory.DDL_TABLES
    priority = 10
    description = "Convert Oracle CREATE TABLE specifics"

    _SYSDATE_DEFAULT = re.compile(
        r"\bDEFAULT\s+SYSDATE\b",
        re.IGNORECASE,
    )
    _GLOBAL_TEMP = re.compile(
        r"\bCREATE\s+GLOBAL\s+TEMPORARY\s+TABLE\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._SYSDATE_DEFAULT.search(sql) or self._GLOBAL_TEMP.search(sql))

    def apply(self, sql: str) -> str:
        sql = self._SYSDATE_DEFAULT.sub("DEFAULT CURRENT_TIMESTAMP", sql)
        sql = self._GLOBAL_TEMP.sub("CREATE TEMP TABLE", sql)
        return sql


class CTASRule(Rule):
    """CREATE TABLE ... AS SELECT — mostly pass-through.

    Oracle-specific clauses (NOLOGGING, PARALLEL) are already stripped
    by DDL_CLEANUP. This rule exists for completeness and future needs.
    """

    name = "ctas"
    category = RuleCategory.DDL_TABLES
    priority = 20
    description = "Handle CREATE TABLE ... AS SELECT"

    _PATTERN = re.compile(
        r"\bCREATE\s+TABLE\s+\S+\s+.*?\bAS\s+SELECT\b",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # CTAS is mostly identical; Oracle-specific clauses already removed
        return sql


class CommentRule(Rule):
    """COMMENT ON TABLE/COLUMN — same syntax in PostgreSQL, pass through."""

    name = "comment_on"
    category = RuleCategory.DDL_TABLES
    priority = 30
    description = "Pass through COMMENT ON TABLE/COLUMN"

    _PATTERN = re.compile(
        r"\bCOMMENT\s+ON\s+(?:TABLE|COLUMN)\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        # Same syntax in PostgreSQL
        return sql


class RenameTableRule(Rule):
    """RENAME table_name TO new_name -> ALTER TABLE table_name RENAME TO new_name.

    Oracle's standalone RENAME statement does not exist in PostgreSQL.
    """

    name = "rename_table"
    category = RuleCategory.DDL_TABLES
    priority = 40
    description = "Convert RENAME to ALTER TABLE ... RENAME TO"

    _PATTERN = re.compile(
        r"\bRENAME\s+(\S+)\s+TO\s+(\S+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.strip().upper()
        # Only match standalone RENAME (not ALTER TABLE ... RENAME COLUMN)
        if upper.startswith("RENAME"):
            return bool(self._PATTERN.search(sql))
        return False

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"ALTER TABLE \1 RENAME TO \2", sql)


class EnableConstraintRule(Rule):
    """ALTER TABLE ... ENABLE CONSTRAINT -> VALIDATE CONSTRAINT."""

    name = "enable_constraint"
    category = RuleCategory.DDL_TABLES
    priority = 50
    description = "Convert ENABLE CONSTRAINT to VALIDATE CONSTRAINT"

    _PATTERN = re.compile(
        r"\bENABLE\s+CONSTRAINT\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("VALIDATE CONSTRAINT", sql)


class DisableConstraintRule(Rule):
    """ALTER TABLE ... DISABLE CONSTRAINT -> ALTER CONSTRAINT ... NOT VALID."""

    name = "disable_constraint"
    category = RuleCategory.DDL_TABLES
    priority = 60
    description = "Convert DISABLE CONSTRAINT to ALTER CONSTRAINT ... NOT VALID"

    _PATTERN = re.compile(
        r"\bDISABLE\s+CONSTRAINT\s+(\S+)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"ALTER CONSTRAINT \1 NOT VALID", sql)


# All rules in this module, for easy registration
DDL_TABLES_RULES: list[type[Rule]] = [
    CreateTableRule,
    CTASRule,
    CommentRule,
    RenameTableRule,
    EnableConstraintRule,
    DisableConstraintRule,
]
