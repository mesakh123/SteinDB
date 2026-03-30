"""Speed optimizations for the rule engine.

- RegexCache: pre-compile and reuse regex patterns
- Category keyword gates for short-circuit evaluation
"""

from __future__ import annotations

import re

from steindb.rules.base import RuleCategory


class RegexCache:
    """Thread-safe regex pattern cache. Compile once, reuse everywhere."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], re.Pattern[str]] = {}

    def get(self, pattern: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
        key = (pattern, flags)
        if key not in self._cache:
            self._cache[key] = re.compile(pattern, flags)
        return self._cache[key]

    def clear(self) -> None:
        self._cache.clear()


regex_cache = RegexCache()


# ---------------------------------------------------------------------------
# Category keyword gates for short-circuit evaluation.
#
# If SQL (uppercased) does not contain ANY of the keywords for a category,
# we can skip that category entirely.  This avoids running matches() on
# every rule in categories that are clearly irrelevant.
#
# Categories NOT listed here are never skipped (safe default).
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[RuleCategory, frozenset[str]] = {
    RuleCategory.DDL_CLEANUP: frozenset(
        {
            "STORAGE",
            "TABLESPACE",
            "PCTFREE",
            "INITRANS",
            "LOGGING",
            "NOLOGGING",
            "PARALLEL",
        }
    ),
    RuleCategory.DATATYPES_BASIC: frozenset(
        {
            "VARCHAR2",
            "NVARCHAR2",
            "NCHAR",
            "CLOB",
            "NCLOB",
            "BLOB",
            "RAW",
            "LONG",
            "BFILE",
        }
    ),
    RuleCategory.DATATYPES_NUMERIC: frozenset(
        {
            "NUMBER",
            "BINARY_FLOAT",
            "BINARY_DOUBLE",
            "PLS_INTEGER",
            "BINARY_INTEGER",
        }
    ),
    RuleCategory.DATATYPES_TEMPORAL: frozenset(
        {
            "DATE",
            "TIMESTAMP",
            "INTERVAL",
        }
    ),
    RuleCategory.SYNTAX_FUNCTIONS: frozenset(
        {
            "NVL",
            "NVL2",
            "DECODE",
            "SUBSTR",
            "INSTR",
            "ROWNUM",
            "LISTAGG",
            "DBMS_OUTPUT",
            "LENGTHB",
            "RAWTOHEX",
            "HEXTORAW",
            "REGEXP_LIKE",
            "REGEXP_SUBSTR",
            "TO_NUMBER",
            "WM_CONCAT",
            "RATIO_TO_REPORT",
        }
    ),
    RuleCategory.SYNTAX_DATETIME: frozenset(
        {
            "TO_DATE",
            "TO_CHAR",
            "ADD_MONTHS",
            "MONTHS_BETWEEN",
            "TRUNC",
            "SYSDATE",
            "SYSTIMESTAMP",
        }
    ),
    RuleCategory.SYNTAX_JOINS: frozenset({"(+)"}),
    RuleCategory.SYNTAX_NULL: frozenset({"NVL", "COALESCE", "NULLIF"}),
    RuleCategory.SYNTAX_MISC: frozenset(
        {
            "DUAL",
            "MINUS",
            "ROWID",
            "ROWNUM",
            "MERGE",
            "CONNECT BY",
        }
    ),
    RuleCategory.SEQUENCES: frozenset({"SEQUENCE", "NEXTVAL", "CURRVAL"}),
    RuleCategory.TRIGGERS: frozenset({"TRIGGER", "RAISE_APPLICATION_ERROR"}),
    RuleCategory.PLSQL_BASIC: frozenset(
        {
            "PROCEDURE",
            "FUNCTION",
            "BEGIN",
            "DECLARE",
            "EXCEPTION",
            "DBMS_OUTPUT",
            "EXECUTE IMMEDIATE",
            "PLS_INTEGER",
            "SYS_REFCURSOR",
        }
    ),
    RuleCategory.PLSQL_CONTROL_FLOW: frozenset(
        {
            "LOOP",
            "WHILE",
            "FOR",
            "CURSOR",
            "FETCH",
        }
    ),
    RuleCategory.PACKAGES: frozenset({"PACKAGE"}),
    RuleCategory.SYNONYMS: frozenset({"SYNONYM"}),
    RuleCategory.MATERIALIZED_VIEWS: frozenset({"MATERIALIZED"}),
    RuleCategory.GRANTS: frozenset({"GRANT", "REVOKE"}),
    RuleCategory.PARTITIONING: frozenset({"PARTITION"}),
}


def should_skip_category(category: RuleCategory, sql_upper: str) -> bool:
    """Return True if the category can be safely skipped for the given SQL.

    The SQL must already be uppercased by the caller. Categories not in
    CATEGORY_KEYWORDS are never skipped (returns False).
    """
    keywords = CATEGORY_KEYWORDS.get(category)
    if keywords is None:
        return False
    return not any(kw in sql_upper for kw in keywords)
