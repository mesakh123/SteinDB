"""Verifier module for PostgreSQL output validation.

Provides 4-stage verification:
1. pg_query syntax check (with regex fallback)
2. EXPLAIN dry-run (optional)
3. AST comparison + Oracle remnant detection
4. Confidence scoring + status classification
"""

from __future__ import annotations

from steindb.verifier.ast_compare import (
    ASTCompareResult,
    check_structural_completeness,
    detect_oracle_remnants,
)
from steindb.verifier.confidence import classify_status, compute_confidence
from steindb.verifier.explain import ExplainResult, analyze_explain_output, run_explain
from steindb.verifier.parse import ParseResult, parse_sql
from steindb.verifier.static_analysis import (
    StaticAnalysisReport,
    StaticAnalysisRule,
    run_static_analysis,
)
from steindb.verifier.verifier import Verifier

__all__ = [
    "ASTCompareResult",
    "ExplainResult",
    "ParseResult",
    "StaticAnalysisReport",
    "StaticAnalysisRule",
    "Verifier",
    "analyze_explain_output",
    "check_structural_completeness",
    "classify_status",
    "compute_confidence",
    "detect_oracle_remnants",
    "parse_sql",
    "run_explain",
    "run_static_analysis",
]
