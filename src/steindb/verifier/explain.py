# src/steindb/verifier/explain.py
"""Stage 2: EXPLAIN dry-run against PostgreSQL catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ExplainResult:
    """Result of an EXPLAIN dry-run."""

    valid: bool
    error: str | None = None
    plan: str | None = None
    skipped: bool = False
    issues: list[str] = field(default_factory=list)


async def run_explain(
    sql: str,
    connection: Any,
    timeout_seconds: float = 30.0,
) -> ExplainResult:
    """Run EXPLAIN on the SQL without executing it.

    If connection is None, skip the check (returns valid=True, skipped=True).
    """
    if connection is None:
        return ExplainResult(valid=True, skipped=True)

    try:
        # EXPLAIN only plans the query, does not execute
        explain_sql = f"EXPLAIN {sql}"
        rows = await connection.fetch(explain_sql)
        plan = "\n".join(str(row.get("QUERY PLAN", row)) for row in rows)
        issues = analyze_explain_output(plan)
        return ExplainResult(valid=True, plan=plan, issues=issues)
    except Exception as e:
        return ExplainResult(valid=False, error=str(e))


def analyze_explain_output(plan: str) -> list[str]:
    """Analyze EXPLAIN output for potential issues."""
    issues: list[str] = []

    # Detect sequential scans on large tables
    seq_scan_match = re.search(r"Seq Scan.*rows=(\d+)", plan)
    if seq_scan_match:
        rows = int(seq_scan_match.group(1))
        if rows > 10000:
            issues.append(
                f"Sequential scan on table with ~{rows} estimated rows. Consider adding an index."
            )

    return issues
