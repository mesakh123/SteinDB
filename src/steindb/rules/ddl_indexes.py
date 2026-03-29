# src/steindb/rules/ddl_indexes.py
"""DDL Index rules: clean Oracle-specific index options and handle BITMAP indexes.

Most Oracle-specific clauses (TABLESPACE, STORAGE, PARALLEL) are already
stripped by DDL_CLEANUP. This module handles index-specific patterns.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class CreateIndexCleanupRule(Rule):
    """Remove any remaining Oracle-specific index options.

    Most cleanup is done by DDL_CLEANUP rules (TABLESPACE, STORAGE, etc.).
    This rule catches any stragglers specific to index creation, such as
    COMPUTE STATISTICS, ONLINE, REVERSE, COMPRESS <n> on indexes.
    """

    name = "create_index_cleanup"
    category = RuleCategory.DDL_INDEXES
    priority = 10
    description = "Remove Oracle-specific index options"

    _COMPUTE_STATS = re.compile(r"\s*\bCOMPUTE\s+STATISTICS\b", re.IGNORECASE)
    _ONLINE = re.compile(r"\s*\bONLINE\b", re.IGNORECASE)
    _REVERSE = re.compile(r"\s*\bREVERSE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        upper = sql.upper()
        if "CREATE" not in upper or "INDEX" not in upper:
            return False
        return bool(
            self._COMPUTE_STATS.search(sql) or self._ONLINE.search(sql) or self._REVERSE.search(sql)
        )

    def apply(self, sql: str) -> str:
        sql = self._COMPUTE_STATS.sub("", sql)
        sql = self._ONLINE.sub("", sql)
        sql = self._REVERSE.sub("", sql)
        return sql


class BitmapIndexRule(Rule):
    """CREATE BITMAP INDEX -> convert to standard btree index with warning.

    PostgreSQL has no BITMAP index type. We convert to a standard btree
    index and add a comment warning for manual review.
    """

    name = "bitmap_index"
    category = RuleCategory.DDL_INDEXES
    priority = 20
    description = "Convert BITMAP INDEX to standard INDEX with warning"

    _PATTERN = re.compile(
        r"\bCREATE\s+BITMAP\s+INDEX\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        result = self._PATTERN.sub("CREATE INDEX", sql)
        return (
            "-- WARNING: BITMAP INDEX converted to standard btree index; "
            "review for GIN/GiST alternatives\n" + result
        )


# All rules in this module, for easy registration
DDL_INDEXES_RULES: list[type[Rule]] = [
    CreateIndexCleanupRule,
    BitmapIndexRule,
]
