# src/steindb/verifier/parse.py
"""Stage 1: PostgreSQL syntax validation via pg_query.

Falls back to regex-based basic syntax checking when pg_query/pglast
is not available (e.g., on Windows).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

try:
    import pglast

    HAS_PGLAST = True
except ImportError:
    HAS_PGLAST = False


@dataclass(frozen=True)
class ParseResult:
    """Result of a SQL parse attempt."""

    valid: bool
    error: str | None = None
    statement_count: int = 0


# Basic SQL keywords that a valid PostgreSQL statement should start with
_VALID_STATEMENT_STARTS = re.compile(
    r"^\s*("
    r"SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|GRANT|REVOKE|"
    r"WITH|EXPLAIN|BEGIN|END|DO|COMMENT|TRUNCATE|SET|SHOW|"
    r"DECLARE|EXECUTE|PREPARE|DEALLOCATE|LISTEN|NOTIFY|VACUUM|"
    r"ANALYZE|REINDEX|CLUSTER|COPY|LOCK|RESET|DISCARD|SAVEPOINT|"
    r"RELEASE|ROLLBACK|COMMIT|ABORT|START|FETCH|MOVE|CLOSE|"
    r"CALL|RAISE|RETURN|PERFORM|IF|LOOP|WHILE|FOR|FOREACH|EXIT|CONTINUE"
    r")\b",
    re.IGNORECASE,
)

# Patterns indicating clearly broken SQL
_BROKEN_SQL_PATTERNS = [
    re.compile(r"\bSELEC\b(?!T)", re.IGNORECASE),  # misspelled SELECT
    re.compile(r"\bFORM\b\s", re.IGNORECASE),  # misspelled FROM
    re.compile(r"\bWHERR\b", re.IGNORECASE),  # misspelled WHERE
    re.compile(r"\bINSERT\s+INTO\s*$", re.IGNORECASE | re.MULTILINE),  # incomplete
]


def parse_sql(sql: str | None) -> ParseResult:
    """Validate PostgreSQL syntax.

    Uses pglast (pg_query Python bindings) if available.
    Falls back to basic regex-based heuristics otherwise.

    Returns ParseResult with valid=True if the SQL parses successfully.
    """
    if sql is None or not sql.strip():
        return ParseResult(valid=False, error="SQL is empty or None")

    if HAS_PGLAST:
        return _parse_with_pglast(sql)

    logger.warning("pglast not installed, using regex-based fallback validation")
    return _parse_with_regex_fallback(sql)


def _parse_with_pglast(sql: str) -> ParseResult:
    """Parse using pglast (pg_query bindings)."""
    try:
        stmts = pglast.parse_sql(sql)
        stmt_count = len(stmts) if stmts else 1
        return ParseResult(valid=True, statement_count=stmt_count)
    except Exception as e:
        return ParseResult(valid=False, error=str(e))


def _parse_with_regex_fallback(sql: str) -> ParseResult:
    """Basic regex-based SQL validation fallback.

    Not a real parser -- catches obvious issues but cannot validate
    full PostgreSQL syntax. Used when pglast is unavailable (Windows).
    """
    stripped = sql.strip()

    # Check for broken SQL patterns
    for pattern in _BROKEN_SQL_PATTERNS:
        if pattern.search(stripped):
            return ParseResult(
                valid=False,
                error=f"Likely invalid SQL: matched pattern {pattern.pattern}",
            )

    # Split into statements (basic semicolon split, ignoring $$ blocks)
    statements = _split_statements(stripped)
    if not statements:
        return ParseResult(valid=False, error="No SQL statements found")

    # Check each statement starts with a valid keyword
    for stmt in statements:
        stmt_stripped = stmt.strip()
        if not stmt_stripped:
            continue
        if not _VALID_STATEMENT_STARTS.search(stmt_stripped) and "$$" not in stripped:
            return ParseResult(
                valid=False,
                error=f"Statement does not start with a valid SQL keyword: {stmt_stripped[:50]}...",
            )

    return ParseResult(valid=True, statement_count=max(1, len(statements)))


def _split_statements(sql: str) -> list[str]:
    """Split SQL into statements, respecting $$ dollar-quoted strings."""
    # If there are $$ blocks, treat the whole thing as one statement
    if "$$" in sql:
        return [sql]

    parts = sql.split(";")
    return [p.strip() for p in parts if p.strip()]
