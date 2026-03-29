# src/steindb/rules/engine.py
"""Rule Engine orchestrator: classifies, converts, or forwards objects.

Provides a unified ``ConversionEngine`` base class used by both
``O2PRuleEngine`` (Oracle-to-PostgreSQL) and ``P2ORuleEngine``
(PostgreSQL-to-Oracle).  The legacy ``RuleEngine`` alias is kept for
backward compatibility.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from steindb.contracts.models import (
    ConvertedObject,
    ForwardedObject,
    MigrationDirection,
    RuleOutput,
    ScannedObject,
)
from steindb.rules.registry import CATEGORY_ORDER, RuleCategory, RuleRegistry

# ---------------------------------------------------------------------------
# Oracle-to-PostgreSQL forward patterns
# ---------------------------------------------------------------------------
_O2P_FORWARD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bDBMS_LOB\b", re.IGNORECASE),
        "DBMS_LOB package requires LLM conversion",
    ),
    (
        re.compile(r"\bDBMS_SQL\b", re.IGNORECASE),
        "DBMS_SQL package requires LLM conversion",
    ),
    (
        re.compile(r"\bUTL_FILE\b", re.IGNORECASE),
        "UTL_FILE package requires LLM conversion",
    ),
    (
        re.compile(r"\bDBMS_SCHEDULER\b", re.IGNORECASE),
        "DBMS_SCHEDULER package requires LLM conversion",
    ),
    (
        re.compile(r"\bDBMS_PIPE\b", re.IGNORECASE),
        "DBMS_PIPE package requires LLM conversion",
    ),
    (
        re.compile(r"\bDBMS_AQ\b", re.IGNORECASE),
        "DBMS_AQ package requires LLM conversion",
    ),
    (
        re.compile(r"\bAUTONOMOUS_TRANSACTION\b", re.IGNORECASE),
        "AUTONOMOUS_TRANSACTION pragma has no direct PostgreSQL equivalent",
    ),
    (
        re.compile(r"\bPIPE\s+ROW\b", re.IGNORECASE),
        "PIPE ROW pipelined functions have no direct PostgreSQL equivalent",
    ),
    (
        re.compile(r"\bMODEL\s+(?:DIMENSION|MEASURES|RULES)\b", re.IGNORECASE),
        "MODEL clause is Oracle-specific analytic construct",
    ),
    (
        re.compile(
            r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TYPE\b.*?\bAS\s+OBJECT\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "Custom object types with methods require LLM conversion",
    ),
    (
        re.compile(r"\bBULK\s+COLLECT\b.*?\bFORALL\b", re.IGNORECASE | re.DOTALL),
        "Complex BULK COLLECT with FORALL requires LLM conversion",
    ),
    (
        re.compile(r"\bDBMS_OUTPUT\b", re.IGNORECASE),
        "DBMS_OUTPUT usage requires LLM conversion",
    ),
    (
        re.compile(r"\bGLOBAL\s+TEMPORARY\s+TABLE\b", re.IGNORECASE),
        "Global temporary tables require LLM conversion"
        " (PostgreSQL temp tables have different lifecycle)",
    ),
    (
        re.compile(r"\bINDEX\s+ORGANIZED\s+TABLE\b", re.IGNORECASE),
        "Index organized tables have no direct PostgreSQL equivalent (consider CLUSTER)",
    ),
    (
        re.compile(r"\bORA-04091\b", re.IGNORECASE),
        "Mutating table trigger pattern requires LLM conversion",
    ),
    (
        re.compile(
            r"\bplpgsql\.variable_conflict\b",
            re.IGNORECASE,
        ),
        "plpgsql.variable_conflict indicates variable/column name masking that requires LLM review",
    ),
]

# Keep the old module-level name for anything importing ``_LLM_FORWARD_PATTERNS``.
_LLM_FORWARD_PATTERNS = _O2P_FORWARD_PATTERNS


# ---------------------------------------------------------------------------
# Unified base class
# ---------------------------------------------------------------------------
class ConversionEngine:
    """Base class for deterministic rule-based conversion.

    Sub-classes only need to supply:
    - ``forward_patterns``: regex patterns that trigger LLM forwarding
    - ``category_order``: rule category execution order
    - ``direction``: the migration direction enum value
    """

    def __init__(
        self,
        registry: RuleRegistry,
        category_order: Sequence[RuleCategory],
        forward_patterns: Sequence[tuple[re.Pattern[str], str]],
        direction: MigrationDirection,
    ) -> None:
        self._registry = registry
        self._category_order = list(category_order)
        self._forward_patterns = list(forward_patterns)
        self._direction = direction

    def should_forward_to_llm(self, obj: ScannedObject) -> tuple[bool, str]:
        """Check if this object should be forwarded to the LLM Transpiler."""
        sql = obj.source_sql
        for pattern, reason in self._forward_patterns:
            if pattern.search(sql):
                return True, reason
        return False, ""

    def convert(self, obj: ScannedObject) -> ConvertedObject | ForwardedObject:
        """Convert a single object using deterministic rules."""
        should_forward, reason = self.should_forward_to_llm(obj)
        if should_forward:
            return ForwardedObject(
                name=obj.name,
                schema=obj.schema,
                object_type=obj.object_type,
                source_sql=obj.source_sql,
                forward_reason=reason,
            )

        target_sql, rules_applied = self._registry.apply_all(
            obj.source_sql, category_order=self._category_order
        )

        return ConvertedObject(
            name=obj.name,
            schema=obj.schema,
            object_type=obj.object_type,
            source_sql=obj.source_sql,
            target_sql=target_sql,
            confidence=1.0,
            method="rules",
            rules_applied=rules_applied,
        )

    def convert_batch(
        self, job_id: str, customer_id: str, objects: list[ScannedObject]
    ) -> RuleOutput:
        """Convert a batch of objects, splitting into converted and forwarded."""
        converted: list[ConvertedObject] = []
        forwarded: list[ForwardedObject] = []

        for obj in objects:
            result = self.convert(obj)
            if isinstance(result, ConvertedObject):
                converted.append(result)
            else:
                forwarded.append(result)

        return RuleOutput(
            job_id=job_id,
            customer_id=customer_id,
            converted=converted,
            forwarded=forwarded,
            rules_converted_count=len(converted),
            forwarded_to_llm_count=len(forwarded),
            direction=self._direction,
        )


# ---------------------------------------------------------------------------
# Concrete engines
# ---------------------------------------------------------------------------
class O2PRuleEngine(ConversionEngine):
    """Oracle-to-PostgreSQL deterministic rule engine."""

    def __init__(self, registry: RuleRegistry) -> None:
        super().__init__(
            registry=registry,
            category_order=CATEGORY_ORDER,
            forward_patterns=_O2P_FORWARD_PATTERNS,
            direction=MigrationDirection.ORACLE_TO_PG,
        )


# Backward-compatible alias — existing code imports ``RuleEngine``.
RuleEngine = O2PRuleEngine
