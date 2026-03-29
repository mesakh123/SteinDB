# src/steindb/rules/materialized_views.py
"""Materialized view rules: Oracle MVIEW options -> PostgreSQL equivalents."""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class MViewRefreshRule(Rule):
    """Handle REFRESH COMPLETE/FAST/FORCE -> strip (PG uses REFRESH MATERIALIZED VIEW).

    Oracle:  CREATE MATERIALIZED VIEW ... REFRESH FAST ON COMMIT ...
    PG:      CREATE MATERIALIZED VIEW ... (refresh is a separate command)
    """

    name = "mview_refresh"
    category = RuleCategory.MATERIALIZED_VIEWS
    priority = 10
    description = "Remove Oracle-specific REFRESH clause from MVIEW definition"

    _PATTERN = re.compile(
        r"\s*REFRESH\s+(?:COMPLETE|FAST|FORCE)" r"(?:\s+ON\s+(?:COMMIT|DEMAND))?\s*",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(
            re.search(r"\bMATERIALIZED\s+VIEW\b", sql, re.IGNORECASE) and self._PATTERN.search(sql)
        )

    def apply(self, sql: str) -> str:
        result = self._PATTERN.sub(" ", sql)
        # Add a comment about refresh strategy
        if re.search(r"\bON\s+COMMIT\b", sql, re.IGNORECASE):
            result = (
                "-- NOTE: Oracle ON COMMIT refresh has no direct PG equivalent.\n"
                "-- Use pg_cron or application-level REFRESH MATERIALIZED VIEW.\n" + result
            )
        return result


class MViewBuildDeferredRule(Rule):
    """BUILD DEFERRED -> WITH NO DATA."""

    name = "mview_build_deferred"
    category = RuleCategory.MATERIALIZED_VIEWS
    priority = 20
    description = "Convert BUILD DEFERRED to WITH NO DATA"

    _PATTERN = re.compile(r"\bBUILD\s+DEFERRED\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("WITH NO DATA", sql)


class MViewCleanupRule(Rule):
    """Remove Oracle-specific MVIEW options not supported in PostgreSQL.

    Removes: BUILD IMMEDIATE, ENABLE QUERY REWRITE, USING INDEX, TABLESPACE,
    STORAGE clauses, etc.
    """

    name = "mview_cleanup"
    category = RuleCategory.MATERIALIZED_VIEWS
    priority = 30
    description = "Strip Oracle-specific MVIEW options"

    _CLEANUP_PATTERNS = [
        re.compile(r"\bBUILD\s+IMMEDIATE\b", re.IGNORECASE),
        re.compile(r"\bENABLE\s+QUERY\s+REWRITE\b", re.IGNORECASE),
        re.compile(r"\bDISABLE\s+QUERY\s+REWRITE\b", re.IGNORECASE),
        re.compile(r"\bUSING\s+INDEX\b", re.IGNORECASE),
        re.compile(r"\bUSING\s+NO\s+INDEX\b", re.IGNORECASE),
        re.compile(r"\bNEVER\s+REFRESH\b", re.IGNORECASE),
    ]

    def matches(self, sql: str) -> bool:
        if not re.search(r"\bMATERIALIZED\s+VIEW\b", sql, re.IGNORECASE):
            return False
        return any(p.search(sql) for p in self._CLEANUP_PATTERNS)

    def apply(self, sql: str) -> str:
        result = sql
        for p in self._CLEANUP_PATTERNS:
            result = p.sub("", result)
        # Clean up multiple spaces
        result = re.sub(r"  +", " ", result)
        return result
