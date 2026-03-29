"""JSON report renderer — generates structured JSON migration report."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from steindb.contracts import ScannedObject, ScanResult

_LOW_THRESHOLD = 3.0
_MED_THRESHOLD = 7.0


def _classify(score: float) -> str:
    if score <= _LOW_THRESHOLD:
        return "low"
    elif score <= _MED_THRESHOLD:
        return "medium"
    return "high"


class JSONReportRenderer:
    """Generate a structured JSON report string."""

    def render(
        self,
        scan_result: ScanResult,
        complexity_scores: dict[str, float],
        dependency_graph: dict[str, list[str]],
    ) -> str:
        """Generate a JSON report string."""
        generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        objects = scan_result.objects

        # --- by_type counts ---
        by_type: dict[str, int] = {}
        for obj in objects:
            by_type[obj.object_type.value] = by_type.get(obj.object_type.value, 0) + 1

        # --- complexity stats ---
        scores = list(complexity_scores.values())
        avg_complexity = round(sum(scores) / len(scores), 2) if scores else 0.0

        low_count = sum(1 for s in scores if _classify(s) == "low")
        med_count = sum(1 for s in scores if _classify(s) == "medium")
        high_count = sum(1 for s in scores if _classify(s) == "high")

        rule_convertible = low_count + med_count
        llm_required = high_count

        # --- per-object details ---
        object_list: list[dict[str, object]] = []
        for obj in objects:
            score = complexity_scores.get(obj.name, 0.0)
            object_list.append(
                {
                    "name": obj.name,
                    "schema": obj.schema,
                    "object_type": obj.object_type.value,
                    "line_count": obj.line_count,
                    "complexity_score": round(score, 2),
                    "complexity_class": _classify(score),
                    "dependencies": obj.dependencies,
                }
            )

        # --- complexity factors ---
        complexity_factors = self._collect_complexity_factors(objects)

        report = {
            "version": "0.1.0",
            "generated_at": generated_at,
            "job_id": scan_result.job_id,
            "customer_id": scan_result.customer_id,
            "summary": {
                "total_objects": scan_result.total_objects,
                "by_type": by_type,
                "avg_complexity": avg_complexity,
                "complexity_breakdown": {
                    "low": low_count,
                    "medium": med_count,
                    "high": high_count,
                },
                "rule_convertible": rule_convertible,
                "llm_required": llm_required,
            },
            "objects": object_list,
            "dependencies": dependency_graph,
            "complexity_factors": complexity_factors,
        }

        return json.dumps(report, indent=2, ensure_ascii=False)

    def _collect_complexity_factors(self, objects: list[ScannedObject]) -> dict[str, int]:
        """Detect Oracle-specific constructs across all objects."""
        import re

        patterns: dict[str, re.Pattern[str]] = {
            "DBMS_LOB": re.compile(r"\bDBMS_LOB\b", re.IGNORECASE),
            "DBMS_SQL": re.compile(r"\bDBMS_SQL\b", re.IGNORECASE),
            "UTL_FILE": re.compile(r"\bUTL_FILE\b", re.IGNORECASE),
            "DBMS_SCHEDULER": re.compile(r"\bDBMS_SCHEDULER\b", re.IGNORECASE),
            "DBMS_OUTPUT": re.compile(r"\bDBMS_OUTPUT\b", re.IGNORECASE),
            "AUTONOMOUS_TRANSACTION": re.compile(r"\bAUTONOMOUS_TRANSACTION\b", re.IGNORECASE),
            "BULK COLLECT": re.compile(r"\bBULK\s+COLLECT\b", re.IGNORECASE),
            "CONNECT BY": re.compile(r"\bCONNECT\s+BY\b", re.IGNORECASE),
            "DECODE": re.compile(r"\bDECODE\s*\(", re.IGNORECASE),
            "NVL": re.compile(r"\bNVL\s*\(", re.IGNORECASE),
            "SYSDATE": re.compile(r"\bSYSDATE\b", re.IGNORECASE),
            "ROWNUM": re.compile(r"\bROWNUM\b", re.IGNORECASE),
            "VARCHAR2": re.compile(r"\bVARCHAR2\b", re.IGNORECASE),
            "NUMBER": re.compile(r"\bNUMBER\b", re.IGNORECASE),
        }

        counts: dict[str, int] = {}
        for obj in objects:
            for name, pat in patterns.items():
                if pat.search(obj.source_sql):
                    counts[name] = counts.get(name, 0) + 1
        return counts
