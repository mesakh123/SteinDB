# tests/unit/test_blocker_fixes.py
"""Regression tests for two BLOCKER bugs fixed on feature/autoresearch-enhancement.

BUG 1: CONNECT BY hierarchical queries passed through unconverted with confidence=1.0.
BUG 2: ROWNUM was not converted to LIMIT due to missing keyword in SYNTAX_MISC speed gate.
"""

from __future__ import annotations

import pytest
from steindb.contracts.models import ConvertedObject, ForwardedObject, ScannedObject
from steindb.rules.engine import O2PRuleEngine
from steindb.rules.loader import create_direction_registry


@pytest.fixture()
def engine() -> O2PRuleEngine:
    registry = create_direction_registry("o2p")
    return O2PRuleEngine(registry)


def _make_obj(sql: str) -> ScannedObject:
    return ScannedObject(
        name="test",
        object_type="TABLE",
        source_sql=sql,
        schema="PUBLIC",
        line_count=sql.count("\n") + 1,
    )


# -----------------------------------------------------------------------
# BUG 1: CONNECT BY must be forwarded to LLM
# -----------------------------------------------------------------------


class TestConnectByForwarded:
    """CONNECT BY hierarchical queries should be forwarded to LLM."""

    def test_connect_by_prior(self, engine: O2PRuleEngine) -> None:
        sql = (
            "SELECT employee_id, manager_id, LEVEL\n"
            "FROM employees\n"
            "START WITH manager_id IS NULL\n"
            "CONNECT BY PRIOR employee_id = manager_id"
        )
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ForwardedObject), (
            f"CONNECT BY should be forwarded to LLM, got ConvertedObject: "
            f"{getattr(result, 'target_sql', '')}"
        )
        assert "CONNECT BY" in result.forward_reason

    def test_connect_by_nocycle(self, engine: O2PRuleEngine) -> None:
        sql = (
            "SELECT employee_id, LEVEL\n"
            "FROM employees\n"
            "START WITH manager_id IS NULL\n"
            "CONNECT BY NOCYCLE PRIOR employee_id = manager_id"
        )
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ForwardedObject)

    def test_start_with_alone(self, engine: O2PRuleEngine) -> None:
        sql = (
            "SELECT * FROM employees\n"
            "START WITH department_id = 10\n"
            "CONNECT BY PRIOR employee_id = manager_id"
        )
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ForwardedObject)

    def test_sys_connect_by_path(self, engine: O2PRuleEngine) -> None:
        sql = (
            "SELECT SYS_CONNECT_BY_PATH(name, '/') AS path\n"
            "FROM categories\n"
            "START WITH parent_id IS NULL\n"
            "CONNECT BY PRIOR id = parent_id"
        )
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ForwardedObject)


# -----------------------------------------------------------------------
# BUG 2: ROWNUM must be converted to LIMIT (or forwarded for complex cases)
# -----------------------------------------------------------------------


class TestRownumConverted:
    """Simple ROWNUM patterns must convert to LIMIT."""

    def test_where_rownum_le(self, engine: O2PRuleEngine) -> None:
        sql = "SELECT * FROM employees WHERE ROWNUM <= 10"
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ConvertedObject)
        assert "ROWNUM" not in result.target_sql.upper()
        assert "LIMIT 10" in result.target_sql.upper()

    def test_where_rownum_lt(self, engine: O2PRuleEngine) -> None:
        sql = "SELECT * FROM employees WHERE ROWNUM < 11"
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ConvertedObject)
        assert "ROWNUM" not in result.target_sql.upper()
        assert "LIMIT 10" in result.target_sql.upper()

    def test_where_rownum_eq_1(self, engine: O2PRuleEngine) -> None:
        sql = "SELECT * FROM employees WHERE ROWNUM = 1"
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ConvertedObject)
        assert "ROWNUM" not in result.target_sql.upper()
        assert "LIMIT 1" in result.target_sql.upper()

    def test_and_rownum_le(self, engine: O2PRuleEngine) -> None:
        sql = "SELECT * FROM employees WHERE status = 'ACTIVE' AND ROWNUM <= 5"
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ConvertedObject)
        assert "ROWNUM" not in result.target_sql.upper()
        assert "LIMIT 5" in result.target_sql.upper()
        # The WHERE clause for status should remain
        assert "STATUS" in result.target_sql.upper()

    def test_rownum_in_rules_applied(self, engine: O2PRuleEngine) -> None:
        """Verify that the rownum_to_limit rule is actually listed in rules_applied."""
        sql = "SELECT * FROM employees WHERE ROWNUM <= 10"
        result = engine.convert(_make_obj(sql))
        assert isinstance(result, ConvertedObject)
        assert "rownum_to_limit" in result.rules_applied

    def test_simple_rownum_converted_or_forwarded(self, engine: O2PRuleEngine) -> None:
        """Simple ROWNUM <= N should either convert to LIMIT or forward to LLM."""
        sql = "SELECT * FROM employees WHERE ROWNUM <= 10"
        result = engine.convert(_make_obj(sql))
        if isinstance(result, ConvertedObject):
            assert "ROWNUM" not in result.target_sql.upper()
            assert "LIMIT" in result.target_sql.upper()
        else:
            assert isinstance(result, ForwardedObject)
