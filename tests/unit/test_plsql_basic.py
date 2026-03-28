"""Tests for PL/SQL basic wrapper rules."""

from __future__ import annotations

from steindb.rules.plsql_basic import (
    DBMSOutputRule,
    ExecuteImmediateRule,
    IntoStrictRule,
    IStoASRule,
    LanguageWrapperRule,
    PLSIntegerRule,
    ReturnToReturnsRule,
    SysRefcursorRule,
)


class TestReturnToReturnsRule:
    rule = ReturnToReturnsRule()

    def test_matches(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURN VARCHAR2 IS"
        assert self.rule.matches(sql)

    def test_no_match_returns(self) -> None:
        # Should not match RETURN inside body (without preceding ')')
        assert not self.rule.matches("RETURN v_name;")

    def test_apply(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURN VARCHAR2 IS"
        result = self.rule.apply(sql)
        assert "RETURNS VARCHAR2" in result
        assert "RETURN VARCHAR2" not in result


class TestIStoASRule:
    rule = IStoASRule()

    def test_matches_is(self) -> None:
        sql = "CREATE FUNCTION f(x INT) RETURNS INT IS BEGIN RETURN x; END;"
        assert self.rule.matches(sql)

    def test_matches_as(self) -> None:
        sql = "CREATE OR REPLACE PROCEDURE p AS BEGIN NULL; END;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT 1 FROM dual;")

    def test_apply(self) -> None:
        sql = "CREATE OR REPLACE FUNCTION f(x INT) RETURNS INT IS"
        result = self.rule.apply(sql)
        assert result.endswith("AS $$")
        assert " IS" not in result.split("AS $$")[0].split("INT")[-1]


class TestLanguageWrapperRule:
    rule = LanguageWrapperRule()

    def test_matches(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS INT AS $$ BEGIN RETURN 1; END;"
        assert self.rule.matches(sql)

    def test_no_match_no_create(self) -> None:
        assert not self.rule.matches("BEGIN NULL; END;")

    def test_apply(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS INT AS $$ BEGIN RETURN 1; END;"
        result = self.rule.apply(sql)
        assert "$$ LANGUAGE plpgsql;" in result

    def test_apply_with_proc_name(self) -> None:
        sql = "CREATE PROCEDURE p() AS $$ BEGIN NULL; END p;"
        result = self.rule.apply(sql)
        assert "$$ LANGUAGE plpgsql;" in result
        assert "END p;" not in result


class TestDBMSOutputRule:
    rule = DBMSOutputRule()

    def test_matches(self) -> None:
        assert self.rule.matches("DBMS_OUTPUT.PUT_LINE('hello');")

    def test_no_match(self) -> None:
        assert not self.rule.matches("RAISE NOTICE 'hello';")

    def test_apply_string(self) -> None:
        result = self.rule.apply("DBMS_OUTPUT.PUT_LINE('hello world');")
        assert result == "RAISE NOTICE '%', 'hello world';"

    def test_apply_variable(self) -> None:
        result = self.rule.apply("DBMS_OUTPUT.PUT_LINE(v_msg);")
        assert result == "RAISE NOTICE '%', v_msg;"

    def test_apply_concatenation(self) -> None:
        result = self.rule.apply("DBMS_OUTPUT.PUT_LINE('Count: ' || v_cnt);")
        assert "RAISE NOTICE '%'" in result


class TestExecuteImmediateRule:
    rule = ExecuteImmediateRule()

    def test_matches(self) -> None:
        assert self.rule.matches("EXECUTE IMMEDIATE v_sql;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("EXECUTE v_sql;")

    def test_apply(self) -> None:
        result = self.rule.apply("EXECUTE IMMEDIATE 'DROP TABLE t';")
        assert result == "EXECUTE 'DROP TABLE t';"
        assert "IMMEDIATE" not in result


class TestPLSIntegerRule:
    rule = PLSIntegerRule()

    def test_matches_pls(self) -> None:
        assert self.rule.matches("v_count PLS_INTEGER;")

    def test_matches_binary(self) -> None:
        assert self.rule.matches("v_idx BINARY_INTEGER := 0;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("v_count INTEGER;")

    def test_apply_pls(self) -> None:
        result = self.rule.apply("v_count PLS_INTEGER;")
        assert result == "v_count INTEGER;"

    def test_apply_binary(self) -> None:
        result = self.rule.apply("v_idx BINARY_INTEGER := 0;")
        assert result == "v_idx INTEGER := 0;"

    def test_apply_multiple(self) -> None:
        sql = "a PLS_INTEGER; b BINARY_INTEGER;"
        result = self.rule.apply(sql)
        assert result == "a INTEGER; b INTEGER;"


class TestIntoStrictRule:
    """CRITICAL: SELECT INTO must become SELECT INTO STRICT."""

    rule = IntoStrictRule()

    def test_matches(self) -> None:
        assert self.rule.matches("SELECT name INTO v_name FROM employees WHERE id = 1;")

    def test_no_match_already_strict(self) -> None:
        assert not self.rule.matches("SELECT name INTO STRICT v_name FROM employees WHERE id = 1;")

    def test_no_match_no_select(self) -> None:
        assert not self.rule.matches("INSERT INTO t VALUES (1);")

    def test_apply(self) -> None:
        sql = "SELECT name INTO v_name FROM employees WHERE id = 1;"
        result = self.rule.apply(sql)
        assert "INTO STRICT v_name" in result

    def test_apply_multiple_vars(self) -> None:
        sql = "SELECT a, b INTO v_a FROM t WHERE id = 1;"
        result = self.rule.apply(sql)
        assert "INTO STRICT v_a" in result

    def test_preserves_already_strict(self) -> None:
        sql = "SELECT name INTO STRICT v_name FROM employees;"
        # Should not match, so apply won't be called, but test safety
        assert not self.rule.matches(sql)

    def test_no_match_fetch_into(self) -> None:
        """FETCH ... INTO must NOT get STRICT added."""
        sql = "FETCH cur INTO v_name;"
        assert not self.rule.matches(sql)

    def test_no_match_bulk_collect_into(self) -> None:
        """BULK COLLECT INTO must NOT get STRICT added."""
        sql = "SELECT name BULK COLLECT INTO v_names FROM employees;"
        assert not self.rule.matches(sql)

    def test_no_strict_for_count_aggregate(self) -> None:
        """SELECT COUNT(*) INTO should NOT get STRICT (always returns 1 row)."""
        sql = "SELECT COUNT(*) INTO v_cnt FROM employees WHERE dept_id = 10;"
        result = self.rule.apply(sql)
        assert "INTO STRICT" not in result
        assert "INTO v_cnt" in result

    def test_no_strict_for_sum_aggregate(self) -> None:
        """SELECT SUM(salary) INTO should NOT get STRICT."""
        sql = "SELECT SUM(salary) INTO v_total FROM employees;"
        result = self.rule.apply(sql)
        assert "INTO STRICT" not in result
        assert "INTO v_total" in result

    def test_no_strict_for_max_aggregate(self) -> None:
        """SELECT MAX(id) INTO should NOT get STRICT."""
        sql = "SELECT MAX(id) INTO v_max FROM employees;"
        result = self.rule.apply(sql)
        assert "INTO STRICT" not in result
        assert "INTO v_max" in result


class TestSysRefcursorRule:
    rule = SysRefcursorRule()

    def test_matches(self) -> None:
        assert self.rule.matches("v_cursor SYS_REFCURSOR;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("v_cursor REFCURSOR;")

    def test_apply(self) -> None:
        result = self.rule.apply("v_cursor SYS_REFCURSOR;")
        assert result == "v_cursor REFCURSOR;"

    def test_apply_case_insensitive(self) -> None:
        result = self.rule.apply("c sys_refcursor;")
        assert result == "c REFCURSOR;"
