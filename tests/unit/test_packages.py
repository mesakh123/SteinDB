"""Tests for package decomposition rules."""

from __future__ import annotations

from steindb.rules.packages import PackageToSchemaRule


class TestPackageToSchemaRule:
    rule = PackageToSchemaRule()

    def test_matches_package(self) -> None:
        sql = "CREATE OR REPLACE PACKAGE my_pkg AS\n  PROCEDURE do_stuff;\nEND my_pkg;"
        assert self.rule.matches(sql)

    def test_matches_package_body(self) -> None:
        sql = (
            "CREATE OR REPLACE PACKAGE BODY my_pkg AS\n"
            "  PROCEDURE do_stuff IS BEGIN NULL; END do_stuff;\n"
            "END my_pkg;"
        )
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_apply_simple_spec(self) -> None:
        sql = "CREATE OR REPLACE PACKAGE util_pkg AS\n  PROCEDURE cleanup;\nEND util_pkg;"
        result = self.rule.apply(sql)
        assert "CREATE SCHEMA IF NOT EXISTS util_pkg;" in result

    def test_apply_body_with_function(self) -> None:
        sql = (
            "CREATE OR REPLACE PACKAGE BODY calc_pkg AS\n"
            "  FUNCTION add_nums(a INTEGER, b INTEGER) RETURN INTEGER IS\n"
            "  BEGIN\n"
            "    RETURN a + b;\n"
            "  END add_nums;\n"
            "END calc_pkg;"
        )
        result = self.rule.apply(sql)
        assert "CREATE SCHEMA IF NOT EXISTS calc_pkg;" in result
        assert "calc_pkg.add_nums" in result
        assert "RETURNS INTEGER" in result
        assert "$$ LANGUAGE plpgsql;" in result

    def test_apply_body_with_procedure(self) -> None:
        sql = (
            "CREATE OR REPLACE PACKAGE BODY log_pkg AS\n"
            "  PROCEDURE log_msg(msg VARCHAR2) IS\n"
            "  BEGIN\n"
            "    INSERT INTO logs(message) VALUES(msg);\n"
            "  END log_msg;\n"
            "END log_pkg;"
        )
        result = self.rule.apply(sql)
        assert "CREATE SCHEMA IF NOT EXISTS log_pkg;" in result
        assert "log_pkg.log_msg" in result
        assert "PROCEDURE" in result

    def test_complex_package_forwarded(self) -> None:
        sql = (
            "CREATE OR REPLACE PACKAGE BODY state_pkg AS\n"
            "  TYPE rec_type IS RECORD (id INTEGER, name VARCHAR2(100));\n"
            "  PROCEDURE do_stuff IS BEGIN NULL; END do_stuff;\n"
            "END state_pkg;"
        )
        result = self.rule.apply(sql)
        assert "FORWARD TO LLM" in result

    def test_pragma_forwarded(self) -> None:
        sql = (
            "CREATE OR REPLACE PACKAGE BODY tx_pkg AS\n"
            "  PRAGMA SERIALLY_REUSABLE;\n"
            "  PROCEDURE do_stuff IS BEGIN NULL; END do_stuff;\n"
            "END tx_pkg;"
        )
        result = self.rule.apply(sql)
        assert "FORWARD TO LLM" in result
