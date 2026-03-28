# src/steindb/rules/ddl_cleanup.py
"""DDL Cleanup rules: strip Oracle-specific physical storage clauses.

These rules run FIRST in the pipeline (Phase 0) to remove Oracle-specific
clauses like TABLESPACE, STORAGE(...), PCTFREE, LOGGING, PARALLEL, etc.
before other DDL rules process the SQL.
"""

from __future__ import annotations

import re

from steindb.rules.base import Rule, RuleCategory


class TABLESPACERemovalRule(Rule):
    """Remove TABLESPACE clause from CREATE TABLE/INDEX/ALTER statements.

    Also converts ALTER TABLE ... MOVE TABLESPACE to a comment since
    there is no PostgreSQL equivalent.
    """

    name = "tablespace_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 10
    description = "Remove TABLESPACE clause"

    def matches(self, sql: str) -> bool:
        return bool(re.search(r"\bTABLESPACE\b", sql, re.IGNORECASE))

    def apply(self, sql: str) -> str:
        # Handle ALTER TABLE ... MOVE TABLESPACE (entire statement becomes comment)
        move_pattern = re.compile(
            r"ALTER\s+TABLE\s+\S+\s+MOVE\s+TABLESPACE\s+\S+",
            re.IGNORECASE,
        )
        if move_pattern.search(sql):
            sql = move_pattern.sub(
                "-- ALTER TABLE MOVE TABLESPACE removed (no PostgreSQL equivalent)",
                sql,
            )
            return sql

        # Remove TABLESPACE <identifier> from other statements
        sql = re.sub(
            r"\s*TABLESPACE\s+\S+",
            "",
            sql,
            flags=re.IGNORECASE,
        )
        return sql


class STORAGERemovalRule(Rule):
    """Remove STORAGE(...) clause entirely, handling nested parentheses."""

    name = "storage_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 20
    description = "Remove STORAGE(...) clause"

    def matches(self, sql: str) -> bool:
        return bool(re.search(r"\bSTORAGE\s*\(", sql, re.IGNORECASE))

    def apply(self, sql: str) -> str:
        # Match STORAGE followed by balanced parentheses
        result: list[str] = []
        i = 0
        upper = sql.upper()
        while i < len(sql):
            match = re.search(r"\bSTORAGE\s*\(", upper[i:], re.IGNORECASE)
            if match is None:
                result.append(sql[i:])
                break

            start = i + match.start()
            # Remove any leading whitespace before STORAGE
            # Find the start of whitespace before STORAGE
            ws_start = start
            while ws_start > 0 and sql[ws_start - 1] in (" ", "\t", "\n", "\r"):
                ws_start -= 1
            result.append(sql[i:ws_start])

            # Find matching closing paren
            paren_start = i + match.end() - 1  # position of '('
            depth = 1
            j = paren_start + 1
            while j < len(sql) and depth > 0:
                if sql[j] == "(":
                    depth += 1
                elif sql[j] == ")":
                    depth -= 1
                j += 1
            i = j
        return "".join(result)


class PCTRemovalRule(Rule):
    """Remove PCTFREE n, PCTUSED n, INITRANS n, MAXTRANS n."""

    name = "pct_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 30
    description = "Remove PCTFREE, PCTUSED, INITRANS, MAXTRANS"

    _PATTERN = re.compile(
        r"\s*\b(?:PCTFREE|PCTUSED|INITRANS|MAXTRANS)\s+\d+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class LOGGINGRemovalRule(Rule):
    """Remove LOGGING and NOLOGGING keywords."""

    name = "logging_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 40
    description = "Remove LOGGING / NOLOGGING"

    _PATTERN = re.compile(r"\s*\bNOLOGGING\b|\s*\bLOGGING\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class PARALLELRemovalRule(Rule):
    """Remove PARALLEL n and NOPARALLEL keywords."""

    name = "parallel_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 50
    description = "Remove PARALLEL / NOPARALLEL"

    _PATTERN = re.compile(
        r"\s*\bNOPARALLEL\b|\s*\bPARALLEL\s+\d+",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class COMPRESSRemovalRule(Rule):
    """Remove COMPRESS, NOCOMPRESS, COMPRESS FOR ... keywords."""

    name = "compress_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 60
    description = "Remove COMPRESS / NOCOMPRESS"

    _PATTERN = re.compile(
        r"\s*\bNOCOMPRESS\b|\s*\bCOMPRESS\s+FOR\s+\S+|\s*\bCOMPRESS\b",
        re.IGNORECASE,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class CACHERemovalRule(Rule):
    """Remove CACHE and NOCACHE keywords in table context (not sequence)."""

    name = "cache_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 70
    description = "Remove CACHE / NOCACHE in table context"

    _PATTERN = re.compile(r"\s*\bNOCACHE\b|\s*\bCACHE\b", re.IGNORECASE)

    def matches(self, sql: str) -> bool:
        # Only match in non-sequence context
        upper = sql.upper()
        if "CREATE SEQUENCE" in upper or "ALTER SEQUENCE" in upper:
            return False
        return bool(self._PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        return self._PATTERN.sub("", sql)


class OracleHintRemovalRule(Rule):
    """Remove Oracle optimizer hints like /*+ INDEX(...) */, /*+ FULL(...) */, /*+ PARALLEL(...) */.

    Oracle hints are silently ignored by PostgreSQL but indicate performance
    assumptions that won't translate. This rule strips them and optionally
    leaves a comment noting the removed hint.
    """

    name = "oracle_hint_removal"
    category = RuleCategory.DDL_CLEANUP
    priority = 5  # Run before other cleanup rules
    description = "Remove Oracle optimizer hints (/*+ ... */)"

    # Matches Oracle-style hints: /*+ ... */
    _HINT_PATTERN = re.compile(
        r"/\*\+\s*.*?\*/",
        re.IGNORECASE | re.DOTALL,
    )

    def matches(self, sql: str) -> bool:
        return bool(self._HINT_PATTERN.search(sql))

    def apply(self, sql: str) -> str:
        def _replace_hint(m: re.Match[str]) -> str:
            hint_text = m.group(0)
            return f"/* SteinDB: removed Oracle hint {hint_text} */"

        return self._HINT_PATTERN.sub(_replace_hint, sql)


# All rules in this module, for easy registration
DDL_CLEANUP_RULES: list[type[Rule]] = [
    OracleHintRemovalRule,
    TABLESPACERemovalRule,
    STORAGERemovalRule,
    PCTRemovalRule,
    LOGGINGRemovalRule,
    PARALLELRemovalRule,
    COMPRESSRemovalRule,
    CACHERemovalRule,
]
