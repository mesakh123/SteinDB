"""Tests for major bug fixes: bare VARCHAR2 conversion and double space before AS $$."""

from __future__ import annotations

from steindb.contracts.models import ScannedObject
from steindb.rules.engine import O2PRuleEngine
from steindb.rules.loader import create_direction_registry


def _make_engine() -> O2PRuleEngine:
    registry = create_direction_registry("o2p")
    return O2PRuleEngine(registry)


def _convert(sql: str, object_type: str = "PROCEDURE") -> str:
    engine = _make_engine()
    obj = ScannedObject(
        name="test",
        object_type=object_type,
        source_sql=sql,
        schema="PUBLIC",
        line_count=sql.count("\n") + 1,
    )
    result = engine.convert(obj)
    return result.target_sql


class TestBareVarchar2Conversion:
    """BUG 3: Bare VARCHAR2 in PL/SQL parameters not converted."""

    def test_bare_varchar2_converted(self) -> None:
        """VARCHAR2 without size should convert to VARCHAR."""
        sql = (
            "CREATE OR REPLACE PROCEDURE test_proc"
            "(p_name IN VARCHAR2, p_desc IN VARCHAR2) IS BEGIN NULL; END;"
        )
        result = _convert(sql)
        assert "VARCHAR2" not in result, f"Bare VARCHAR2 not converted: {result}"
        assert "VARCHAR" in result

    def test_bare_nvarchar2_converted(self) -> None:
        """NVARCHAR2 without size should convert to VARCHAR."""
        sql = "CREATE OR REPLACE PROCEDURE test_proc" "(p_name IN NVARCHAR2) IS BEGIN NULL; END;"
        result = _convert(sql)
        assert "NVARCHAR2" not in result, f"Bare NVARCHAR2 not converted: {result}"
        assert "VARCHAR" in result

    def test_sized_varchar2_still_works(self) -> None:
        """VARCHAR2(100) should still convert to VARCHAR(100)."""
        sql = (
            "CREATE OR REPLACE PROCEDURE test_proc" "(p_name IN VARCHAR2(100)) IS BEGIN NULL; END;"
        )
        result = _convert(sql)
        assert "VARCHAR2" not in result
        assert "VARCHAR(100)" in result

    def test_mixed_bare_and_sized_varchar2(self) -> None:
        """Both bare and sized VARCHAR2 should be converted."""
        sql = (
            "CREATE OR REPLACE PROCEDURE test_proc"
            "(p_name IN VARCHAR2, p_desc IN VARCHAR2(200)) IS BEGIN NULL; END;"
        )
        result = _convert(sql)
        assert "VARCHAR2" not in result, f"VARCHAR2 remains: {result}"
        assert "VARCHAR(200)" in result


class TestDoubleSpaceBeforeAsDollar:
    """BUG 5: Double space before AS $$ in function/procedure declarations."""

    def test_no_double_space_before_as_dollar(self) -> None:
        """No double space before AS $$."""
        sql = """CREATE OR REPLACE FUNCTION get_name(p_id IN NUMBER) RETURN VARCHAR2 IS
  v_name VARCHAR2(100);
BEGIN
  SELECT name INTO v_name FROM t WHERE id = p_id;
  RETURN v_name;
END;"""
        result = _convert(sql, "FUNCTION")
        assert "  AS $$" not in result, f"Double space found: {result}"
        assert " AS $$" in result

    def test_no_double_space_procedure(self) -> None:
        """No double space for procedures either."""
        sql = """CREATE OR REPLACE PROCEDURE do_stuff(p_id IN NUMBER) IS
BEGIN
  NULL;
END;"""
        result = _convert(sql)
        assert "  AS $$" not in result, f"Double space found: {result}"
        assert " AS $$" in result
