"""Property-based tests for rule engine idempotency.

Verifies that applying the rule engine twice produces the same result as
applying it once. This is a critical property: rules must be stable.
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
# Strategies: various Oracle SQL fragments
# ---------------------------------------------------------------------------

simple_ddl = st.sampled_from(
    [
        "CREATE TABLE t (id NUMBER(10), name VARCHAR2(100))",
        "CREATE TABLE t (id NUMBER(5,0), val NUMBER(18,2))",
        "CREATE TABLE t (created DATE, updated TIMESTAMP)",
        "CREATE TABLE t (data CLOB, bin BLOB)",
        "CREATE TABLE t (id NUMBER(10) NOT NULL, name NVARCHAR2(200))",
    ]
)

simple_dml = st.sampled_from(
    [
        "SELECT NVL(col, 'default') FROM t",
        "SELECT SYSDATE FROM DUAL",
        "SELECT * FROM t WHERE ROWNUM <= 10",
        "SELECT DECODE(status, 1, 'A', 2, 'B', 'C') FROM t",
        "SELECT col1 || col2 FROM t",
    ]
)

simple_plsql = st.sampled_from(
    [
        "SELECT col INTO v_result FROM t WHERE id = 1;",
        "NVL(salary, 0)",
    ]
)

all_oracle_sql = st.one_of(simple_ddl, simple_dml, simple_plsql)


# ---------------------------------------------------------------------------
# Property tests (marked slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@given(sql=all_oracle_sql)
@settings(max_examples=50)
def test_rule_engine_is_idempotent(sql: str, registry: RuleRegistry) -> None:
    """Applying the rule engine twice must produce the same result."""
    first_pass, rules_first = registry.apply_all(sql)
    second_pass, rules_second = registry.apply_all(first_pass)
    assert first_pass == second_pass, (
        f"Rule engine is NOT idempotent.\n"
        f"Input:  {sql}\n"
        f"Pass 1: {first_pass}\n"
        f"Pass 2: {second_pass}\n"
        f"Rules applied (pass 1): {rules_first}\n"
        f"Rules applied (pass 2): {rules_second}"
    )


@pytest.mark.slow
@given(sql=simple_ddl)
@settings(max_examples=30)
def test_ddl_idempotency(sql: str, registry: RuleRegistry) -> None:
    """DDL conversion must be idempotent."""
    first_pass, _ = registry.apply_all(sql)
    second_pass, _ = registry.apply_all(first_pass)
    assert first_pass == second_pass


@pytest.mark.slow
@given(sql=simple_dml)
@settings(max_examples=30)
def test_dml_idempotency(sql: str, registry: RuleRegistry) -> None:
    """DML conversion must be idempotent."""
    first_pass, _ = registry.apply_all(sql)
    second_pass, _ = registry.apply_all(first_pass)
    assert first_pass == second_pass
