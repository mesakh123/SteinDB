# tests/golden/test_golden_llm.py
"""Parametrized golden test runner for LLM Transpiler output.

These tests verify the LLM produces correct output for constructs
that the Rule Engine cannot handle. They require an LLM endpoint
(BYOK) and are slower than rule golden tests.

In CI: run with --timeout=900 (15 minutes)
Locally: skip with -m "not llm_golden" unless you have a model running
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from steindb.testing.loader import load_golden_tests

if TYPE_CHECKING:
    from steindb.contracts.models import GoldenTestCase

GOLDEN_LLM_DIR = Path(__file__).parent / "llm"


def _collect_llm_tests() -> list[GoldenTestCase]:
    return load_golden_tests(GOLDEN_LLM_DIR)


ALL_LLM_TESTS = _collect_llm_tests()


@pytest.mark.golden
@pytest.mark.llm_golden
@pytest.mark.timeout(900)  # 15 minutes gate
@pytest.mark.parametrize(
    "test_case",
    ALL_LLM_TESTS,
    ids=[t.name for t in ALL_LLM_TESTS],
)
def test_llm_golden(test_case: GoldenTestCase) -> None:
    """Golden test: verify LLM Transpiler output matches expected PostgreSQL.

    Skipped until BYOK endpoint is configured. Set STEINDB_BYOK_API_KEY
    and STEINDB_BYOK_MODEL environment variables to enable.
    """
    pytest.skip("LLM golden tests require BYOK endpoint -- set STEINDB_BYOK_API_KEY to enable")
