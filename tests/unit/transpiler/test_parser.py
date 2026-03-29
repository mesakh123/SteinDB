# tests/unit/transpiler/test_parser.py
"""Tests for the structured output parser."""

from __future__ import annotations

import json

import pytest
from steindb.transpiler.parser import extract_json, parse_llm_output


class TestExtractJson:
    def test_clean_json(self) -> None:
        raw = '{"postgresql": "SELECT 1", "confidence": 0.9, "changes": [], "warnings": [], "test_hints": []}'  # noqa: E501
        result = extract_json(raw)
        assert result is not None
        assert result["confidence"] == 0.9

    def test_json_in_code_block(self) -> None:
        raw = 'Here is the result:\n```json\n{"postgresql": "SELECT 1", "confidence": 0.9, "changes": [], "warnings": [], "test_hints": []}\n```'  # noqa: E501
        result = extract_json(raw)
        assert result is not None
        assert result["postgresql"] == "SELECT 1"

    def test_json_embedded_in_text(self) -> None:
        raw = 'The conversion is: {"postgresql": "SELECT 1", "confidence": 0.8, "changes": ["removed DUAL"], "warnings": [], "test_hints": []} Hope this helps!'  # noqa: E501
        result = extract_json(raw)
        assert result is not None

    def test_no_json(self) -> None:
        assert extract_json("Just plain text with no JSON.") is None

    def test_nested_json(self) -> None:
        data = {
            "postgresql": "SELECT 1",
            "confidence": 0.9,
            "changes": ["a", "b"],
            "warnings": [],
            "test_hints": [],
        }
        raw = json.dumps(data)
        result = extract_json(raw)
        assert result is not None
        assert result["changes"] == ["a", "b"]


class TestParseLlmOutput:
    def test_valid_json(self) -> None:
        raw = json.dumps(
            {
                "postgresql": "SELECT CURRENT_TIMESTAMP",
                "confidence": 0.95,
                "changes": ["SYSDATE -> CURRENT_TIMESTAMP"],
                "warnings": [],
                "test_hints": ["Test with timezone"],
            }
        )
        result = parse_llm_output(raw)
        assert result.confidence == 0.95
        assert "CURRENT_TIMESTAMP" in result.postgresql

    def test_fallback_to_raw_sql(self) -> None:
        raw = "SELECT CURRENT_TIMESTAMP;"
        result = parse_llm_output(raw)
        assert result.confidence == 0.5  # Lower confidence for unstructured
        assert "CURRENT_TIMESTAMP" in result.postgresql

    def test_code_block_fallback(self) -> None:
        raw = "Here is the PostgreSQL:\n```sql\nSELECT CURRENT_TIMESTAMP;\n```"
        result = parse_llm_output(raw)
        assert "CURRENT_TIMESTAMP" in result.postgresql

    def test_empty_response_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_llm_output("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_llm_output("   \n  ")

    def test_confidence_clamped(self) -> None:
        raw = json.dumps(
            {
                "postgresql": "SELECT 1",
                "confidence": 1.5,  # Out of range
                "changes": [],
                "warnings": [],
                "test_hints": [],
            }
        )
        result = parse_llm_output(raw)
        assert result.confidence <= 1.0

    def test_negative_confidence_clamped(self) -> None:
        raw = json.dumps(
            {
                "postgresql": "SELECT 1",
                "confidence": -0.5,
                "changes": [],
                "warnings": [],
                "test_hints": [],
            }
        )
        result = parse_llm_output(raw)
        assert result.confidence >= 0.0

    def test_missing_confidence_defaults(self) -> None:
        raw = json.dumps(
            {
                "postgresql": "SELECT 1",
                "changes": [],
                "warnings": [],
                "test_hints": [],
            }
        )
        result = parse_llm_output(raw)
        assert result.confidence == 0.5

    def test_code_block_pgsql(self) -> None:
        raw = "Result:\n```pgsql\nSELECT 42;\n```"
        result = parse_llm_output(raw)
        assert "42" in result.postgresql

    def test_code_block_postgresql(self) -> None:
        raw = "Result:\n```postgresql\nSELECT 42;\n```"
        result = parse_llm_output(raw)
        assert "42" in result.postgresql
