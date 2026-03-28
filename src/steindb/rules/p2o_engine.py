# src/steindb/rules/p2o_engine.py
"""P2O Rule Engine: deterministic PostgreSQL-to-Oracle conversion.

Built on the shared ``ConversionEngine`` base class defined in
``steindb.rules.engine``.
"""

from __future__ import annotations

import re

from steindb.contracts.models import MigrationDirection
from steindb.rules.engine import ConversionEngine
from steindb.rules.registry import P2O_CATEGORY_ORDER, RuleRegistry

# Patterns that MUST be forwarded to the LLM Transpiler.
# These are PostgreSQL constructs that cannot be converted deterministically.
P2O_LLM_FORWARD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bJSONB\b.*->>", re.IGNORECASE | re.DOTALL),
        "JSONB ->> operator requires LLM conversion",
    ),
    (
        re.compile(r"\bJSONB\b.*@>", re.IGNORECASE | re.DOTALL),
        "JSONB @> containment operator requires LLM conversion",
    ),
    (
        re.compile(r"\bARRAY\b\s*\[", re.IGNORECASE),
        "ARRAY literal requires LLM conversion (Oracle uses nested tables/VARRAYs)",
    ),
    (
        re.compile(r"\bUNNEST\b", re.IGNORECASE),
        "UNNEST requires LLM conversion (Oracle uses TABLE() with nested tables)",
    ),
    (
        re.compile(r"\bLATERAL\b", re.IGNORECASE),
        "LATERAL join requires LLM conversion (Oracle uses CROSS/OUTER APPLY in 12c+)",
    ),
    (
        re.compile(r"\bINHERITS\b", re.IGNORECASE),
        "Table inheritance has no Oracle equivalent; requires LLM conversion",
    ),
    (
        re.compile(r"\bLISTEN\b|\bNOTIFY\b", re.IGNORECASE),
        "LISTEN/NOTIFY requires LLM conversion (Oracle uses DBMS_AQ)",
    ),
    (
        re.compile(r"\bDISTINCT\s+ON\b", re.IGNORECASE),
        "DISTINCT ON requires LLM conversion (Oracle uses ROW_NUMBER() subquery)",
    ),
    (
        re.compile(r"CREATE\s+EXTENSION\b", re.IGNORECASE),
        "CREATE EXTENSION has no Oracle equivalent; requires per-extension LLM mapping",
    ),
    (
        re.compile(r"\bFILTER\s*\(\s*WHERE\b", re.IGNORECASE),
        "FILTER (WHERE ...) on aggregates requires LLM conversion (Oracle uses CASE WHEN)",
    ),
    (
        re.compile(r"\bTABLESAMPLE\b", re.IGNORECASE),
        "TABLESAMPLE requires LLM conversion (Oracle uses SAMPLE clause with different syntax)",
    ),
    (
        re.compile(r"\bRETURNING\b", re.IGNORECASE),
        "RETURNING clause requires LLM conversion (Oracle only supports in PL/SQL context)",
    ),
    # NOTE: Basic ON CONFLICT is handled by p2o_syntax_misc.OnConflictToMergeRule.
    # Only complex ON CONFLICT with multiple columns/expressions forwards to LLM.
    # NOTE: PL/pgSQL functions are handled by p2o_plsql_basic and p2o_triggers rules.
    # Do NOT forward all PL/pgSQL to LLM — only forward complex patterns below.
    (
        re.compile(r"\bFOREIGN\s+DATA\s+WRAPPER\b", re.IGNORECASE),
        "Foreign data wrappers require LLM conversion (Oracle uses database links)",
    ),
    (
        re.compile(r"\bCREATE\s+POLICY\b", re.IGNORECASE),
        "Row-level security policies require LLM conversion (Oracle uses VPD)",
    ),
]


class P2ORuleEngine(ConversionEngine):
    """Entry point for deterministic PostgreSQL-to-Oracle conversion."""

    def __init__(self, registry: RuleRegistry) -> None:
        super().__init__(
            registry=registry,
            category_order=P2O_CATEGORY_ORDER,
            forward_patterns=P2O_LLM_FORWARD_PATTERNS,
            direction=MigrationDirection.PG_TO_ORACLE,
        )
