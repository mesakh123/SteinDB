# src/steindb/verifier/verifier.py
"""Verifier pipeline: 4-stage validation of converted PostgreSQL."""

from __future__ import annotations

from typing import Any

import structlog

from steindb.contracts.models import Issue, VerifyResult, VerifyStatus
from steindb.verifier.ast_compare import (
    check_structural_completeness,
    detect_oracle_remnants,
)
from steindb.verifier.confidence import classify_status, compute_confidence
from steindb.verifier.explain import run_explain
from steindb.verifier.parse import parse_sql
from steindb.verifier.static_analysis import Severity, run_static_analysis

logger = structlog.get_logger(__name__)


class Verifier:
    """5-stage verification pipeline.

    Stage 1: pg_query syntax check
    Stage 2: EXPLAIN dry-run (optional, requires PG connection)
    Stage 3: AST comparison + Oracle remnant detection
    Stage 3c: Static analysis for silent conversion errors
    Stage 4: Confidence scoring + status classification
    """

    def __init__(self, pg_connection: Any = None) -> None:
        self._pg_connection = pg_connection

    async def verify(
        self,
        object_name: str,
        object_type: str,
        oracle_sql: str,
        postgresql: str,
        llm_confidence: float = 0.5,
        complexity: float = 1.0,
    ) -> VerifyResult:
        """Run all verification stages on a converted SQL object."""
        issues: list[Issue] = []

        # Stage 1: pg_query syntax check
        parse_result = parse_sql(postgresql)
        if not parse_result.valid:
            return VerifyResult(
                object_name=object_name,
                object_type=object_type,
                status=VerifyStatus.RED,
                confidence=0.0,
                parse_valid=False,
                explain_valid=False,
                issues=[
                    Issue(
                        code="PARSE_FAIL",
                        message=f"Syntax error: {parse_result.error}",
                        severity="error",
                    )
                ],
            )

        # Stage 2: EXPLAIN dry-run
        explain_result = await run_explain(postgresql, self._pg_connection)
        explain_valid = explain_result.valid
        if not explain_result.valid and not explain_result.skipped:
            issues.append(
                Issue(
                    code="EXPLAIN_FAIL",
                    message=f"EXPLAIN failed: {explain_result.error}",
                    severity="error",
                )
            )
        for issue_msg in explain_result.issues:
            issues.append(Issue(code="EXPLAIN_WARNING", message=issue_msg, severity="warning"))

        # Stage 3: Oracle remnant detection
        remnants = detect_oracle_remnants(postgresql)
        for remnant_msg in remnants:
            issues.append(Issue(code="ORACLE_REMNANT", message=remnant_msg, severity="error"))

        # Stage 3b: Structural completeness
        structural = check_structural_completeness(oracle_sql, postgresql)
        if not structural.complete:
            for warning in structural.warnings:
                issues.append(
                    Issue(
                        code="STRUCTURAL_INCOMPLETE",
                        message=warning,
                        severity="warning",
                    )
                )

        # Stage 3c: Static analysis for silent conversion errors
        sa_report = run_static_analysis(oracle_sql, postgresql)
        for sa_issue in sa_report.issues:
            severity_map = {
                Severity.CRITICAL: "error",
                Severity.HIGH: "warning",
                Severity.MEDIUM: "info",
            }
            issues.append(
                Issue(
                    code=sa_issue.code,
                    message=f"[{sa_issue.name}] {sa_issue.message}",
                    severity=severity_map.get(sa_issue.severity, "warning"),
                )
            )

        # Stage 4: Confidence scoring
        confidence = compute_confidence(
            parse_valid=True,
            explain_valid=explain_valid,
            llm_confidence=llm_confidence,
            complexity=complexity,
            issue_count=len(issues),
        )
        status = classify_status(confidence, issue_count=len(issues))

        return VerifyResult(
            object_name=object_name,
            object_type=object_type,
            status=status,
            confidence=confidence,
            parse_valid=True,
            explain_valid=explain_valid,
            issues=issues,
            llm_confidence=llm_confidence,
            complexity_score=complexity,
        )
