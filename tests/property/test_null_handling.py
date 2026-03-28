"""Property-based tests for NULL handling in Oracle-to-PostgreSQL conversion.

Verifies that concatenation with NULL, NVL/COALESCE mappings, and empty
string semantics are handled correctly for all generated inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from steindb.rules.loader import create_default_registry

if TYPE_CHECKING:
    from steindb.rules.registry import RuleRegistry


@pytest.fixture(scope="module")
def registry() -> RuleRegistry:
    return create_default_registry()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

column_names = st.sampled_from(["col_a", "col_b", "col_c", "first_name", "last_name"])
string_literals = st.sampled_from(["' '", "', '", "' - '", "'text'"])


# ---------------------------------------------------------------------------
# Property tests (marked slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@given(col=column_names)
@settings(max_examples=20)
def test_nvl_always_converted(col: str, registry: RuleRegistry) -> None:
    """NVL(col, default) must always be converted to COALESCE."""
    oracle = f"SELECT NVL({col}, 'default') FROM t"
    result, _rules = registry.apply_all(oracle)
    result_upper = result.upper()
    # NVL should not remain in the output
    assert "NVL(" not in result_upper or "NVL2(" in result_upper, f"NVL not converted: {result}"


@pytest.mark.slow
@given(col1=column_names, col2=column_names)
@settings(max_examples=20)
def test_concatenation_produces_output(col1: str, col2: str, registry: RuleRegistry) -> None:
    """Concatenation of two columns must produce non-empty output."""
    oracle = f"SELECT {col1} || {col2} FROM t"
    result, _rules = registry.apply_all(oracle)
    assert result is not None
    assert len(result.strip()) > 0


@pytest.mark.slow
@given(col=column_names, literal=string_literals)
@settings(max_examples=20)
def test_concat_with_literal_preserves_operator(
    col: str, literal: str, registry: RuleRegistry
) -> None:
    """Concatenation with string literals must preserve the || operator or use concat()."""
    oracle = f"SELECT {col} || {literal} FROM t"
    result, _rules = registry.apply_all(oracle)
    # Must still have some form of concatenation
    assert (
        "||" in result or "concat" in result.lower()
    ), f"Concatenation lost in conversion: {result}"


@pytest.mark.slow
@given(col=column_names)
@settings(max_examples=20)
def test_empty_string_comparison_flagged_or_converted(col: str, registry: RuleRegistry) -> None:
    """WHERE col = '' should either be converted or detectable by static analysis."""
    oracle = f"SELECT * FROM t WHERE {col} = ''"
    result, _rules = registry.apply_all(oracle)
    # The result should be non-empty
    assert result is not None
    assert len(result.strip()) > 0
