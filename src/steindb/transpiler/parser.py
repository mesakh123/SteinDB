# src/steindb/transpiler/parser.py
"""Structured output parser for LLM responses.

Three parsing strategies in order:
1. Direct JSON parse
2. Extract JSON from code block (```json ... ```)
3. Extract raw SQL from code block (```sql ... ```) at confidence=0.5
"""

from __future__ import annotations

import json
import re
from typing import Any

from steindb.contracts.models import TranspileResult


def extract_json(raw: str) -> dict[str, Any] | None:
    """Extract a JSON object from text using multiple strategies."""
    # Strategy 1: Direct parse
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Strategy 2: JSON code block
    match = re.search(r"```json\s*\n([\s\S]*?)\n\s*```", raw)
    if match:
        try:
            return json.loads(match.group(1))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Strategy 3: Bare JSON object in text
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group(0))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    return None


def _extract_sql_from_code_block(raw: str) -> str | None:
    """Extract SQL from a code block."""
    match = re.search(r"```(?:sql|pgsql|postgresql)?\s*\n([\s\S]*?)\n\s*```", raw)
    if match:
        return match.group(1).strip()
    return None


def parse_llm_output(raw: str) -> TranspileResult:
    """Parse LLM output into a TranspileResult.

    Tries structured JSON first, then falls back to extracting raw SQL.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM response is empty")

    # Try structured JSON
    data = extract_json(raw)
    if data and "postgresql" in data:
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
        return TranspileResult(
            postgresql=str(data["postgresql"]),
            confidence=confidence,
            changes=data.get("changes", []),
            warnings=data.get("warnings", []),
            test_hints=data.get("test_hints", []),
        )

    # Fallback: extract SQL from code block
    sql = _extract_sql_from_code_block(raw)
    if sql:
        return TranspileResult(
            postgresql=sql,
            confidence=0.5,
            changes=["Extracted from unstructured output"],
            warnings=["Output was not in expected JSON format -- review carefully"],
            test_hints=[],
        )

    # Last resort: treat entire response as SQL
    cleaned = raw.strip()
    if cleaned:
        return TranspileResult(
            postgresql=cleaned,
            confidence=0.5,
            changes=["Raw output used as SQL"],
            warnings=["Could not parse structured output -- review carefully"],
            test_hints=[],
        )

    raise ValueError("Could not extract PostgreSQL from LLM response")
