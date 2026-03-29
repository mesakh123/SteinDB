"""Tests for synonym resolution rules."""

from __future__ import annotations

from steindb.rules.synonyms import (
    DropSynonymRule,
    PrivateSynonymRule,
    PublicSynonymRule,
)


class TestPublicSynonymRule:
    rule = PublicSynonymRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE PUBLIC SYNONYM emp FOR hr.employees;")

    def test_no_match_private(self) -> None:
        assert not self.rule.matches("CREATE SYNONYM emp FOR hr.employees;")

    def test_apply(self) -> None:
        sql = "CREATE PUBLIC SYNONYM emp FOR hr.employees;"
        result = self.rule.apply(sql)
        assert result == "CREATE OR REPLACE VIEW emp AS SELECT * FROM hr.employees;"

    def test_apply_or_replace(self) -> None:
        sql = "CREATE OR REPLACE PUBLIC SYNONYM emp FOR employees;"
        result = self.rule.apply(sql)
        assert "CREATE OR REPLACE VIEW emp AS SELECT * FROM employees;" in result

    def test_apply_simple_target(self) -> None:
        sql = "CREATE PUBLIC SYNONYM dept FOR departments;"
        result = self.rule.apply(sql)
        assert "SELECT * FROM departments;" in result


class TestPrivateSynonymRule:
    rule = PrivateSynonymRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE SYNONYM emp FOR hr.employees;")

    def test_no_match_public(self) -> None:
        assert not self.rule.matches("CREATE PUBLIC SYNONYM emp FOR hr.employees;")

    def test_no_match_other(self) -> None:
        assert not self.rule.matches("CREATE TABLE emp (id INT);")

    def test_apply(self) -> None:
        sql = "CREATE SYNONYM emp FOR hr.employees;"
        result = self.rule.apply(sql)
        assert result == "CREATE OR REPLACE VIEW emp AS SELECT * FROM hr.employees;"

    def test_apply_simple(self) -> None:
        sql = "CREATE SYNONYM dept FOR departments;"
        result = self.rule.apply(sql)
        assert "SELECT * FROM departments;" in result


class TestDropSynonymRule:
    rule = DropSynonymRule()

    def test_matches(self) -> None:
        assert self.rule.matches("DROP SYNONYM emp;")

    def test_matches_public(self) -> None:
        assert self.rule.matches("DROP PUBLIC SYNONYM emp;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("DROP TABLE emp;")

    def test_apply(self) -> None:
        result = self.rule.apply("DROP SYNONYM emp;")
        assert result == "DROP VIEW IF EXISTS emp;"

    def test_apply_public(self) -> None:
        result = self.rule.apply("DROP PUBLIC SYNONYM emp;")
        assert result == "DROP VIEW IF EXISTS emp;"
