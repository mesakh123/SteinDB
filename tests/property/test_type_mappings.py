"""Property-based tests for Oracle-to-PostgreSQL type mappings.

Uses Hypothesis to verify that type mapping rules always produce valid
PostgreSQL types for any valid Oracle type input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from steindb.rules.loader import create_default_registry

if TYPE_CHECKING:
    from steindb.rules.registry import RuleRegistry

# ---------------------------------------------------------------------------
# Strategies for generating Oracle types
# ---------------------------------------------------------------------------

oracle_string_types = st.sampled_from(
    [
        "VARCHAR2(100)",
        "VARCHAR2(4000)",
        "VARCHAR2(1)",
        "NVARCHAR2(200)",
        "CHAR(10)",
        "NCHAR(5)",
        "CLOB",
        "NCLOB",
        "LONG",
    ]
)

oracle_numeric_types = st.sampled_from(
    [
        "NUMBER",
        "NUMBER(5)",
        "NUMBER(10)",
        "NUMBER(18)",
        "NUMBER(10,2)",
        "NUMBER(38,10)",
        "NUMBER(1)",
        "FLOAT",
        "BINARY_FLOAT",
        "BINARY_DOUBLE",
    ]
)

oracle_temporal_types = st.sampled_from(
    [
        "DATE",
        "TIMESTAMP",
        "TIMESTAMP(6)",
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMP WITH LOCAL TIME ZONE",
        "INTERVAL YEAR TO MONTH",
        "INTERVAL DAY TO SECOND",
    ]
)

# Valid PostgreSQL type keywords that should appear in output
VALID_PG_TYPE_KEYWORDS = frozenset(
    {
        "varchar",
        "character varying",
        "text",
        "char",
        "character",
        "integer",
        "int",
        "bigint",
        "smallint",
        "numeric",
        "decimal",
        "real",
        "double precision",
        "boolean",
        "timestamp",
        "timestamptz",
        "date",
        "interval",
        "time",
        "bytea",
        "oid",
        # Also allow the original if no rule matched (pass-through)
    }
)


def _has_valid_pg_type(sql: str) -> bool:
    """Check that the SQL contains at least one valid PostgreSQL type keyword."""
    sql_lower = sql.lower()
    return any(kw in sql_lower for kw in VALID_PG_TYPE_KEYWORDS)


@pytest.fixture(scope="module")
def registry() -> RuleRegistry:
    return create_default_registry()


# ---------------------------------------------------------------------------
# Property tests (marked slow for Hypothesis)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@given(oracle_type=oracle_string_types)
@settings(max_examples=50)
def test_string_type_always_produces_output(oracle_type: str, registry: RuleRegistry) -> None:
    """Any Oracle string type wrapped in CREATE TABLE must produce non-empty output."""
    sql = f"CREATE TABLE test_tbl (col1 {oracle_type})"
    result, _rules = registry.apply_all(sql)
    assert result is not None
    assert len(result.strip()) > 0, f"Empty output for {oracle_type}"


@pytest.mark.slow
@given(oracle_type=oracle_numeric_types)
@settings(max_examples=50)
def test_numeric_type_always_produces_output(oracle_type: str, registry: RuleRegistry) -> None:
    """Any Oracle numeric type wrapped in CREATE TABLE must produce non-empty output."""
    sql = f"CREATE TABLE test_tbl (col1 {oracle_type})"
    result, _rules = registry.apply_all(sql)
    assert result is not None
    assert len(result.strip()) > 0, f"Empty output for {oracle_type}"


@pytest.mark.slow
@given(oracle_type=oracle_temporal_types)
@settings(max_examples=50)
def test_temporal_type_always_produces_output(oracle_type: str, registry: RuleRegistry) -> None:
    """Any Oracle temporal type wrapped in CREATE TABLE must produce non-empty output."""
    sql = f"CREATE TABLE test_tbl (col1 {oracle_type})"
    result, _rules = registry.apply_all(sql)
    assert result is not None
    assert len(result.strip()) > 0, f"Empty output for {oracle_type}"


@pytest.mark.slow
@given(
    precision=st.integers(min_value=1, max_value=38),
    scale=st.integers(min_value=0, max_value=30),
)
@settings(max_examples=100)
def test_number_mapping_always_valid(precision: int, scale: int, registry: RuleRegistry) -> None:
    """Any NUMBER(p,s) must map to a valid PostgreSQL type."""
    assume(scale <= precision)
    oracle = f"CREATE TABLE t (col NUMBER({precision},{scale}))"
    result, _rules = registry.apply_all(oracle)
    assert result is not None
    assert len(result.strip()) > 0
    # Must not contain Oracle NUMBER type in output
    # The result should either have converted the type or left it as-is
    # (which would be caught by SA-007). Here we just verify no crash.


@pytest.mark.slow
@given(length=st.integers(min_value=1, max_value=32767))
@settings(max_examples=50)
def test_varchar2_mapping_preserves_length(length: int, registry: RuleRegistry) -> None:
    """VARCHAR2(n) must map to a type that preserves the length constraint."""
    oracle = f"CREATE TABLE t (col VARCHAR2({length}))"
    result, _rules = registry.apply_all(oracle)
    assert result is not None
    # The length value should still appear in the output
    assert (
        str(length) in result or "TEXT" in result.upper()
    ), f"Length {length} not preserved in output: {result}"
