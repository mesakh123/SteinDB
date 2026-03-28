# tests/unit/verifier/test_ast_compare.py
"""Tests for AST comparison and Oracle remnant detection."""

from __future__ import annotations

from steindb.verifier.ast_compare import (
    check_structural_completeness,
    detect_oracle_remnants,
)


class TestDetectOracleRemnants:
    def test_clean_pg_sql(self) -> None:
        issues = detect_oracle_remnants("SELECT CURRENT_TIMESTAMP")
        assert issues == []

    def test_detects_nvl(self) -> None:
        issues = detect_oracle_remnants("SELECT NVL(x, 0) FROM t")
        assert any("NVL" in i for i in issues)

    def test_detects_nvl2(self) -> None:
        issues = detect_oracle_remnants("SELECT NVL2(x, 1, 0) FROM t")
        assert any("NVL2" in i for i in issues)

    def test_detects_sysdate(self) -> None:
        issues = detect_oracle_remnants("SELECT SYSDATE FROM t")
        assert any("SYSDATE" in i for i in issues)

    def test_detects_from_dual(self) -> None:
        issues = detect_oracle_remnants("SELECT 1 FROM DUAL")
        assert any("DUAL" in i for i in issues)

    def test_detects_connect_by(self) -> None:
        issues = detect_oracle_remnants("SELECT * CONNECT BY PRIOR id = mgr")
        assert any("CONNECT BY" in i for i in issues)

    def test_detects_varchar2(self) -> None:
        issues = detect_oracle_remnants("CREATE TABLE t (name VARCHAR2(100))")
        assert any("VARCHAR2" in i for i in issues)

    def test_detects_number(self) -> None:
        issues = detect_oracle_remnants("CREATE TABLE t (id NUMBER(10))")
        assert any("NUMBER" in i for i in issues)

    def test_detects_decode(self) -> None:
        issues = detect_oracle_remnants("SELECT DECODE(status, 1, 'A', 'B') FROM t")
        assert any("DECODE" in i for i in issues)

    def test_detects_rownum(self) -> None:
        issues = detect_oracle_remnants("SELECT * FROM t WHERE ROWNUM <= 10")
        assert any("ROWNUM" in i for i in issues)

    def test_detects_colon_new_old(self) -> None:
        issues = detect_oracle_remnants("IF :NEW.status = 'A' THEN")
        assert any(":NEW/:OLD" in i for i in issues)

    def test_detects_raise_application_error(self) -> None:
        issues = detect_oracle_remnants("RAISE_APPLICATION_ERROR(-20001, 'err')")
        assert any("RAISE_APPLICATION_ERROR" in i for i in issues)

    def test_detects_dbms_output(self) -> None:
        issues = detect_oracle_remnants("DBMS_OUTPUT.PUT_LINE('hello')")
        assert any("DBMS_OUTPUT" in i for i in issues)

    def test_detects_execute_immediate(self) -> None:
        issues = detect_oracle_remnants("EXECUTE IMMEDIATE 'DROP TABLE t'")
        assert any("EXECUTE IMMEDIATE" in i for i in issues)

    def test_detects_pragma(self) -> None:
        issues = detect_oracle_remnants("PRAGMA AUTONOMOUS_TRANSACTION;")
        assert any("PRAGMA" in i for i in issues)

    def test_detects_bulk_collect(self) -> None:
        issues = detect_oracle_remnants("SELECT id BULK COLLECT INTO v_ids FROM t")
        assert any("BULK COLLECT" in i for i in issues)

    def test_detects_forall(self) -> None:
        issues = detect_oracle_remnants("FORALL i IN 1..v_ids.COUNT")
        assert any("FORALL" in i for i in issues)

    def test_detects_dot_nextval(self) -> None:
        issues = detect_oracle_remnants("SELECT my_seq.NEXTVAL FROM DUAL")
        assert any("NEXTVAL" in i for i in issues)

    def test_detects_clob(self) -> None:
        issues = detect_oracle_remnants("CREATE TABLE t (data CLOB)")
        assert any("CLOB" in i for i in issues)

    def test_detects_blob(self) -> None:
        issues = detect_oracle_remnants("CREATE TABLE t (data BLOB)")
        assert any("BLOB" in i for i in issues)

    def test_multiple_remnants(self) -> None:
        sql = "SELECT NVL(SYSDATE, NULL) FROM DUAL"
        issues = detect_oracle_remnants(sql)
        assert len(issues) >= 3  # NVL, SYSDATE, DUAL

    def test_clean_coalesce(self) -> None:
        issues = detect_oracle_remnants("SELECT COALESCE(x, 0) FROM t")
        assert issues == []


class TestStructuralCompleteness:
    def test_select_preserved(self) -> None:
        result = check_structural_completeness(
            oracle="SELECT id, name FROM employees WHERE active = 1",
            postgresql="SELECT id, name FROM employees WHERE active = 1",
        )
        assert result.complete is True

    def test_missing_columns_detected(self) -> None:
        result = check_structural_completeness(
            oracle="SELECT id, name, salary FROM employees",
            postgresql="SELECT id, name FROM employees",
        )
        assert result.complete is False
        assert any("salary" in w.lower() for w in result.warnings)

    def test_no_select_clause(self) -> None:
        result = check_structural_completeness(
            oracle="CREATE TABLE t (id INT)",
            postgresql="CREATE TABLE t (id INTEGER)",
        )
        assert result.complete is True  # No SELECT to compare

    def test_star_select(self) -> None:
        result = check_structural_completeness(
            oracle="SELECT * FROM t",
            postgresql="SELECT * FROM t",
        )
        assert result.complete is True
