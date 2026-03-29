"""Tests for P2O PL/pgSQL basic rules."""

from __future__ import annotations

from steindb.rules.p2o_plsql_basic import (
    DollarQuoteToISRule,
    ExecuteToExecuteImmediateRule,
    IntegerToNumberRule,
    NewOldToColonPrefixRule,
    RaiseExceptionToRaiseAppErrorRule,
    RaiseNoticeToDbmsOutputRule,
    RefcursorToSysRefcursorRule,
    ReturnsToReturnRule,
    SelectIntoStrictRule,
)


class TestReturnsToReturnRule:
    rule = ReturnsToReturnRule()

    def test_matches(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURNS VARCHAR2 AS $$"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("RETURN v_name;")

    def test_apply(self) -> None:
        sql = "CREATE FUNCTION get_name(p_id INTEGER) RETURNS VARCHAR2 AS $$"
        result = self.rule.apply(sql)
        assert "RETURN VARCHAR2" in result
        assert "RETURNS VARCHAR2" not in result

    def test_returns_table_forwards_to_llm(self) -> None:
        """RETURNS TABLE(...) has no PL/SQL equivalent; should forward to LLM."""
        sql = "CREATE FUNCTION get_employees(p_dept INTEGER) RETURNS TABLE(id INTEGER, name TEXT) AS $$"  # noqa: E501
        result = self.rule.apply(sql)
        assert "LLM_FORWARD" in result
        assert "RETURNS TABLE" in result

    def test_returns_setof_forwards_to_llm(self) -> None:
        """RETURNS SETOF has no PL/SQL equivalent; should forward to LLM."""
        sql = "CREATE FUNCTION get_users() RETURNS SETOF users AS $$"
        result = self.rule.apply(sql)
        assert "LLM_FORWARD" in result
        assert "RETURNS SETOF" in result


class TestDollarQuoteToISRule:
    rule = DollarQuoteToISRule()

    def test_matches(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS INT AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE FUNCTION f() RETURN INT IS BEGIN RETURN 1; END;")

    def test_apply(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS INT AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;"
        result = self.rule.apply(sql)
        assert "IS" in result
        assert "AS $$" not in result
        assert "LANGUAGE plpgsql" not in result

    def test_apply_removes_language_clause(self) -> None:
        sql = "CREATE PROCEDURE p() AS $$ BEGIN NULL; END; $$ LANGUAGE plpgsql;"
        result = self.rule.apply(sql)
        assert "$$ LANGUAGE" not in result
        assert "IS" in result


class TestRaiseNoticeToDbmsOutputRule:
    rule = RaiseNoticeToDbmsOutputRule()

    def test_matches(self) -> None:
        assert self.rule.matches("RAISE NOTICE '%', 'hello';")

    def test_no_match(self) -> None:
        assert not self.rule.matches("DBMS_OUTPUT.PUT_LINE('hello');")

    def test_apply_string(self) -> None:
        result = self.rule.apply("RAISE NOTICE '%', 'hello world';")
        assert "DBMS_OUTPUT.PUT_LINE('hello world')" in result

    def test_apply_variable(self) -> None:
        result = self.rule.apply("RAISE NOTICE '%', v_msg;")
        assert "DBMS_OUTPUT.PUT_LINE(v_msg)" in result


class TestRaiseExceptionToRaiseAppErrorRule:
    rule = RaiseExceptionToRaiseAppErrorRule()

    def test_matches_format_string(self) -> None:
        assert self.rule.matches("RAISE EXCEPTION '%', 'Bad input';")

    def test_matches_literal(self) -> None:
        assert self.rule.matches("RAISE EXCEPTION 'Invalid ID';")

    def test_no_match(self) -> None:
        assert not self.rule.matches("RAISE_APPLICATION_ERROR(-20001, 'msg');")

    def test_apply_format_string(self) -> None:
        result = self.rule.apply("RAISE EXCEPTION '%', v_msg;")
        assert "RAISE_APPLICATION_ERROR(-20001, v_msg)" in result

    def test_apply_literal(self) -> None:
        result = self.rule.apply("RAISE EXCEPTION 'Invalid ID';")
        assert "RAISE_APPLICATION_ERROR(-20001, 'Invalid ID')" in result


class TestNewOldToColonPrefixRule:
    rule = NewOldToColonPrefixRule()

    def test_matches_new(self) -> None:
        assert self.rule.matches("NEW.col := 1;")

    def test_matches_old(self) -> None:
        assert self.rule.matches("OLD.salary")

    def test_no_match_already_colon(self) -> None:
        assert not self.rule.matches(":NEW.col := 1;")

    def test_apply_new(self) -> None:
        result = self.rule.apply("NEW.employee_id := seq_val;")
        assert result == ":NEW.employee_id := seq_val;"

    def test_apply_old(self) -> None:
        result = self.rule.apply("IF OLD.salary != NEW.salary THEN")
        assert result == "IF :OLD.salary != :NEW.salary THEN"

    def test_apply_preserves_already_prefixed(self) -> None:
        result = self.rule.apply(":NEW.col := 1;")
        # Should not double-prefix
        assert result == ":NEW.col := 1;"


class TestExecuteToExecuteImmediateRule:
    rule = ExecuteToExecuteImmediateRule()

    def test_matches(self) -> None:
        assert self.rule.matches("EXECUTE 'DROP TABLE t';")

    def test_no_match_already_immediate(self) -> None:
        assert not self.rule.matches("EXECUTE IMMEDIATE 'DROP TABLE t';")

    def test_apply(self) -> None:
        result = self.rule.apply("EXECUTE 'DROP TABLE t';")
        assert result == "EXECUTE IMMEDIATE 'DROP TABLE t';"
        assert "EXECUTE IMMEDIATE" in result


class TestSelectIntoStrictRule:
    rule = SelectIntoStrictRule()

    def test_matches(self) -> None:
        sql = "SELECT name INTO STRICT v_name FROM employees WHERE id = 1;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "SELECT name INTO v_name FROM employees WHERE id = 1;"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "SELECT name INTO STRICT v_name FROM employees WHERE id = 1;"
        result = self.rule.apply(sql)
        assert "INTO v_name" in result
        assert "STRICT" not in result


class TestIntegerToNumberRule:
    rule = IntegerToNumberRule()

    def test_matches(self) -> None:
        assert self.rule.matches("v_count INTEGER;")

    def test_matches_with_init(self) -> None:
        assert self.rule.matches("v_count INTEGER := 0;")

    def test_apply(self) -> None:
        result = self.rule.apply("v_count INTEGER;")
        assert result == "v_count NUMBER(10);"

    def test_apply_with_init(self) -> None:
        result = self.rule.apply("v_idx INTEGER := 0;")
        assert result == "v_idx NUMBER(10) := 0;"


class TestRefcursorToSysRefcursorRule:
    rule = RefcursorToSysRefcursorRule()

    def test_matches(self) -> None:
        assert self.rule.matches("v_cursor REFCURSOR;")

    def test_no_match_already_sys(self) -> None:
        assert not self.rule.matches("v_cursor SYS_REFCURSOR;")

    def test_apply(self) -> None:
        result = self.rule.apply("v_cursor REFCURSOR;")
        assert result == "v_cursor SYS_REFCURSOR;"

    def test_apply_case_insensitive(self) -> None:
        result = self.rule.apply("c refcursor;")
        assert result == "c SYS_REFCURSOR;"
