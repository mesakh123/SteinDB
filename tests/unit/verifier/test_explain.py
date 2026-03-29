# tests/unit/verifier/test_explain.py
"""Tests for EXPLAIN dry-run validation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from steindb.verifier.explain import (
    ExplainResult,
    analyze_explain_output,
    run_explain,
)


class TestRunExplain:
    @pytest.mark.asyncio
    async def test_successful_explain(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"QUERY PLAN": "Seq Scan on employees  (cost=0.00..1.01 rows=1 width=4)"}
        ]
        result = await run_explain("SELECT * FROM employees", mock_conn)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_failed_explain(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = Exception('relation "nonexistent" does not exist')
        result = await run_explain("SELECT * FROM nonexistent", mock_conn)
        assert result.valid is False
        assert "does not exist" in (result.error or "")

    @pytest.mark.asyncio
    async def test_none_connection_skips(self) -> None:
        result = await run_explain("SELECT 1", None)
        assert result.valid is True  # Skip when no connection
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_explain_result_has_plan(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"QUERY PLAN": "Index Scan using idx on t  (cost=0.00..1.00 rows=1 width=4)"}
        ]
        result = await run_explain("SELECT * FROM t", mock_conn)
        assert result.plan is not None
        assert "Index Scan" in result.plan


class TestAnalyzeExplainOutput:
    def test_detects_seq_scan_warning(self) -> None:
        plan = "Seq Scan on large_table  (cost=0.00..100000.00 rows=1000000 width=4)"
        issues = analyze_explain_output(plan)
        assert any(
            "seq" in i.lower() or "sequential" in i.lower() or "scan" in i.lower() for i in issues
        )

    def test_clean_plan_no_issues(self) -> None:
        plan = "Index Scan using idx_emp_id on employees  (cost=0.00..1.00 rows=1 width=4)"
        issues = analyze_explain_output(plan)
        assert issues == []

    def test_small_seq_scan_no_issue(self) -> None:
        plan = "Seq Scan on small_table  (cost=0.00..1.00 rows=100 width=4)"
        issues = analyze_explain_output(plan)
        assert issues == []

    def test_explain_result_dataclass(self) -> None:
        r = ExplainResult(valid=True, skipped=True)
        assert r.valid is True
        assert r.skipped is True
        assert r.issues == []
