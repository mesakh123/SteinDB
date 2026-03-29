# src/steindb/rules/p2o_ddl_cleanup.py
"""P2O DDL Cleanup rules: strip PostgreSQL-specific clauses Oracle doesn't support.

These rules run FIRST in the P2O pipeline (Phase 0) to remove PostgreSQL-specific
clauses like USING INDEX, TABLESPACE pg_default, WITH (fillfactor=...),
INCLUDE columns on indexes, partial index WHERE clauses, and CONCURRENTLY.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class P2OUsingIndexRemovalRule(Rule):
    """Remove USING INDEX clause from constraint definitions.

    PostgreSQL allows USING INDEX on constraints; Oracle does not.
    """

    name = "p2o_using_index_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 10
    description = "Remove USING INDEX clause"

    _PATTERN = re.compile(
        r"\s*USING\s+INDEX\s+\w+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class P2OTablespacePgDefaultRemovalRule(Rule):
    """Remove TABLESPACE pg_default (Oracle doesn't use pg_default).

    Also removes other PostgreSQL tablespace references since they won't
    map to Oracle tablespaces.
    """

    name = "p2o_tablespace_pg_default_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 20
    description = "Remove TABLESPACE pg_default"

    _PATTERN = re.compile(
        r"\s*TABLESPACE\s+pg_default\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class P2OWithStorageParamsRemovalRule(Rule):
    """Remove WITH (fillfactor=70, ...) storage parameters.

    PostgreSQL storage parameters like fillfactor, autovacuum_*, toast_*
    have no Oracle equivalent.
    """

    name = "p2o_with_storage_params_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 30
    description = "Remove WITH (fillfactor=...) storage parameters"

    # Match WITH (...) containing storage parameters like fillfactor, autovacuum, etc.
    # Be careful not to match WITH in CTEs (WITH ... AS (...))
    _PATTERN = re.compile(
        r"\s*WITH\s*\(\s*(?:fillfactor|autovacuum_|toast_)\w*\s*=\s*(?:[^)]*)\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class P2OIncludeColumnsRemovalRule(Rule):
    """Remove INCLUDE (col, ...) from CREATE INDEX.

    PostgreSQL covering indexes (INCLUDE) are not supported in Oracle.
    """

    name = "p2o_include_columns_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 40
    description = "Remove INCLUDE (col) from indexes"

    _PATTERN = re.compile(
        r"\s*INCLUDE\s*\([^)]*\)",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "INDEX" not in upper and "CREATE" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class P2OPartialIndexWhereRemovalRule(Rule):
    """Remove WHERE clause from CREATE INDEX (partial indexes).

    Oracle does not support partial indexes. The WHERE clause is stripped.
    """

    name = "p2o_partial_index_where_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 50
    description = "Remove WHERE clause from partial indexes"

    # Match WHERE at the end of CREATE INDEX statements (after the column list)
    _PATTERN = re.compile(
        r"(CREATE\s+(?:UNIQUE\s+)?INDEX\s+\S+\s+ON\s+\S+\s*\([^)]*\))" r"\s+WHERE\s+.+",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "CREATE" not in upper or "INDEX" not in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        result = self._PATTERN.sub(
            r"\1 /* SteinDB: partial index WHERE clause removed (no Oracle equivalent) */",
            sql,
        )
        return result


class P2OConcurrentlyRemovalRule(Rule):
    """Remove CONCURRENTLY from CREATE INDEX CONCURRENTLY.

    Oracle does not have a CONCURRENTLY option for index creation.
    Oracle uses ONLINE instead, but that requires Enterprise Edition,
    so we simply strip CONCURRENTLY.
    """

    name = "p2o_concurrently_removal"
    category = RuleCategory.P2O_DDL_CLEANUP
    priority = 60
    description = "Remove CONCURRENTLY from CREATE INDEX"

    _PATTERN = re.compile(
        r"(\bCREATE\s+(?:UNIQUE\s+)?INDEX)\s+CONCURRENTLY\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub(r"\1", sql)


# All rules in this module, for easy registration
P2O_DDL_CLEANUP_RULES: list[type[Rule]] = [
    P2OUsingIndexRemovalRule,
    P2OTablespacePgDefaultRemovalRule,
    P2OWithStorageParamsRemovalRule,
    P2OIncludeColumnsRemovalRule,
    P2OPartialIndexWhereRemovalRule,
    P2OConcurrentlyRemovalRule,
]
