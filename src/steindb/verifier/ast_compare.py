# src/steindb/verifier/ast_compare.py
"""Stage 3: AST comparison and Oracle remnant detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Oracle constructs that should NEVER appear in PostgreSQL output
ORACLE_REMNANT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("NVL", re.compile(r"\bNVL\s*\(", re.I)),
    ("NVL2", re.compile(r"\bNVL2\s*\(", re.I)),
    ("DECODE", re.compile(r"\bDECODE\s*\(", re.I)),
    ("SYSDATE", re.compile(r"\bSYSDATE\b", re.I)),
    ("SYSTIMESTAMP", re.compile(r"\bSYSTIMESTAMP\b", re.I)),
    ("DUAL", re.compile(r"\bFROM\s+DUAL\b", re.I)),
    ("CONNECT BY", re.compile(r"\bCONNECT\s+BY\b", re.I)),
    ("START WITH", re.compile(r"\bSTART\s+WITH\b", re.I)),
    ("ROWNUM", re.compile(r"\bROWNUM\b", re.I)),
    ("VARCHAR2", re.compile(r"\bVARCHAR2\b", re.I)),
    ("NUMBER", re.compile(r"\bNUMBER\s*\(", re.I)),
    ("CLOB", re.compile(r"\bCLOB\b", re.I)),
    ("BLOB", re.compile(r"\bBLOB\b", re.I)),
    (":NEW/:OLD", re.compile(r":(NEW|OLD)\.", re.I)),
    ("RAISE_APPLICATION_ERROR", re.compile(r"\bRAISE_APPLICATION_ERROR\b", re.I)),
    ("DBMS_OUTPUT", re.compile(r"\bDBMS_OUTPUT\b", re.I)),
    ("EXECUTE IMMEDIATE", re.compile(r"\bEXECUTE\s+IMMEDIATE\b", re.I)),
    ("PRAGMA", re.compile(r"\bPRAGMA\b", re.I)),
    ("BULK COLLECT", re.compile(r"\bBULK\s+COLLECT\b", re.I)),
    ("FORALL", re.compile(r"\bFORALL\b", re.I)),
    (".NEXTVAL", re.compile(r"\.\s*NEXTVAL\b", re.I)),
]


# Patterns that generate warnings (not errors) for PostgreSQL-specific concerns
POSTGRES_WARNING_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "ctid_usage",
        re.compile(r"\bctid\b", re.I),
        "WARNING: ctid is volatile in PostgreSQL — it changes after UPDATE or VACUUM FULL. "
        "Do not use as a stable row identifier (unlike Oracle ROWID).",
    ),
    (
        "timestamp_zero_precision",
        re.compile(r"\bTIMESTAMP\b(?!\s*\()", re.I),
        "WARNING: Oracle DATE includes time (to seconds). If migrated to TIMESTAMP "
        "(not TIMESTAMP(0)), sub-second precision may differ from Oracle behavior.",
    ),
    (
        "varchar2_byte_semantics",
        re.compile(r"\bVARCHAR2\s*\(\s*\d+\s*(?:BYTE)?\s*\)", re.I),
        "WARNING: Oracle VARCHAR2 may use BYTE semantics (depending on NLS settings). "
        "PostgreSQL VARCHAR is always CHARACTER-based. Multi-byte UTF-8 data may truncate.",
    ),
]


def detect_oracle_remnants(postgresql: str) -> list[str]:
    """Detect leftover Oracle syntax in PostgreSQL output."""
    issues: list[str] = []
    for name, pattern in ORACLE_REMNANT_PATTERNS:
        if pattern.search(postgresql):
            issues.append(f"Oracle remnant detected: {name}")
    return issues


def detect_postgres_warnings(sql: str) -> list[str]:
    """Detect PostgreSQL-specific patterns that warrant non-blocking warnings.

    These are not errors but advisory notices about potential issues
    in the converted PostgreSQL output.
    """
    warnings: list[str] = []
    for _name, pattern, message in POSTGRES_WARNING_PATTERNS:
        if pattern.search(sql):
            warnings.append(message)
    return warnings


def detect_connection_pooler_warning(max_connections: int) -> list[str]:
    """Warn if application uses more than 100 connections without a pooler.

    Oracle handles >1000 direct connections efficiently. PostgreSQL forks
    a heavyweight OS process per connection and degrades above ~100-500.
    """
    warnings: list[str] = []
    if max_connections > 100:
        warnings.append(
            f"WARNING: Application uses {max_connections} connections. "
            "PostgreSQL requires a connection pooler (PgBouncer/Odyssey) "
            "for >100 connections — Oracle's threaded model does not apply."
        )
    return warnings


@dataclass
class ASTCompareResult:
    """Result of a structural comparison between Oracle and PostgreSQL SQL."""

    complete: bool
    warnings: list[str] = field(default_factory=list)


def check_structural_completeness(
    oracle: str,
    postgresql: str,
) -> ASTCompareResult:
    """Basic structural comparison between Oracle and PostgreSQL SQL.

    Checks that key identifiers (table names, column names) from the
    Oracle source appear in the PostgreSQL output.
    """
    warnings: list[str] = []

    # Extract identifiers from SELECT list
    oracle_cols = _extract_select_columns(oracle)
    pg_cols = _extract_select_columns(postgresql)

    if oracle_cols and pg_cols:
        missing = oracle_cols - pg_cols
        if missing:
            warnings.append(f"Columns from Oracle SELECT not found in PostgreSQL: {missing}")
            return ASTCompareResult(complete=False, warnings=warnings)

    return ASTCompareResult(complete=True, warnings=warnings)


def _extract_select_columns(sql: str) -> set[str]:
    """Extract column names from a SELECT clause (basic heuristic)."""
    match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.I | re.S)
    if not match:
        return set()

    cols_str = match.group(1)
    # Split by comma, extract identifiers
    cols: set[str] = set()
    for part in cols_str.split(","):
        # Get the last word (alias or column name)
        tokens = part.strip().split()
        if tokens:
            name = tokens[-1].strip().lower()
            # Skip * and expressions
            if name != "*" and name.isidentifier():
                cols.add(name)
    return cols
