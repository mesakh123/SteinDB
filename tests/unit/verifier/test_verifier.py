# tests/unit/verifier/test_verifier.py
"""Tests for the Verifier pipeline."""

from __future__ import annotations

import pytest
from steindb.contracts.models import VerifyResult, VerifyStatus
from steindb.verifier.verifier import Verifier


class TestVerifier:
    def test_create(self) -> None:
        v = Verifier()
        assert v is not None

    @pytest.mark.asyncio
    async def test_verify_valid_sql(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="get_total",
            object_type="FUNCTION",
            oracle_sql="SELECT NVL(salary, 0) FROM employees",
            postgresql="SELECT COALESCE(salary, 0) FROM employees",
            llm_confidence=0.95,
            complexity=2.0,
        )
        assert isinstance(result, VerifyResult)
        assert result.parse_valid is True
        assert result.status in {VerifyStatus.GREEN, VerifyStatus.YELLOW}

    @pytest.mark.asyncio
    async def test_verify_invalid_sql(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="bad_query",
            object_type="VIEW",
            oracle_sql="SELECT * FROM t",
            postgresql="SELEC * FORM t",  # intentional typo
            llm_confidence=0.5,
            complexity=1.0,
        )
        assert result.status == VerifyStatus.RED
        assert result.parse_valid is False

    @pytest.mark.asyncio
    async def test_verify_detects_oracle_remnants(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="query",
            object_type="VIEW",
            oracle_sql="SELECT NVL(x, 0) FROM DUAL",
            postgresql="SELECT NVL(x, 0) FROM DUAL",  # Not converted!
            llm_confidence=0.8,
            complexity=1.0,
        )
        # Should flag oracle remnants even if pg_query happens to parse it
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_rules_converted_gets_high_confidence(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="table_t",
            object_type="TABLE",
            oracle_sql="CREATE TABLE t (id NUMBER(9))",
            postgresql="CREATE TABLE t (id INTEGER)",
            llm_confidence=1.0,  # Rule engine gives 1.0
            complexity=1.0,
        )
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_verify_returns_verify_result(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="test",
            object_type="TABLE",
            oracle_sql="CREATE TABLE t (id INT)",
            postgresql="CREATE TABLE t (id INTEGER)",
            llm_confidence=0.9,
        )
        assert isinstance(result, VerifyResult)
        assert result.object_name == "test"
        assert result.object_type == "TABLE"

    @pytest.mark.asyncio
    async def test_verify_structural_incompleteness(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="query",
            object_type="VIEW",
            oracle_sql="SELECT id, name, salary FROM employees",
            postgresql="SELECT id, name FROM employees",
            llm_confidence=0.8,
            complexity=2.0,
        )
        # Should detect missing salary column
        assert any("salary" in str(i.message).lower() for i in result.issues)

    @pytest.mark.asyncio
    async def test_verify_empty_sql_is_red(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="empty",
            object_type="VIEW",
            oracle_sql="SELECT 1",
            postgresql="",
            llm_confidence=0.5,
        )
        assert result.status == VerifyStatus.RED
        assert result.parse_valid is False

    @pytest.mark.asyncio
    async def test_verify_explain_skipped_without_connection(self) -> None:
        v = Verifier()
        result = await v.verify(
            object_name="test",
            object_type="TABLE",
            oracle_sql="SELECT 1",
            postgresql="SELECT 1",
            llm_confidence=0.9,
        )
        # EXPLAIN should be skipped (no connection), but valid=True
        assert result.explain_valid is True
