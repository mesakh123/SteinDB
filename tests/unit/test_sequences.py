"""Tests for sequence conversion rules — NEXTVAL, CURRVAL, NOCACHE, cleanup."""

from __future__ import annotations

from steindb.rules.sequences import (
    CreateSequenceCleanupRule,
    CURRVALRule,
    NEXTVALRule,
    NOCACHERemovalRule,
)


class TestNEXTVALRule:
    def setup_method(self) -> None:
        self.rule = NEXTVALRule()

    def test_matches(self) -> None:
        sql = "SELECT emp_seq.NEXTVAL FROM DUAL"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "SELECT nextval('emp_seq')"
        assert not self.rule.matches(sql)

    def test_apply_select(self) -> None:
        sql = "SELECT emp_seq.NEXTVAL FROM DUAL"
        result = self.rule.apply(sql)
        assert result == "SELECT nextval('emp_seq') FROM DUAL"

    def test_apply_insert(self) -> None:
        sql = "INSERT INTO employees (id, name) VALUES (emp_seq.NEXTVAL, 'John')"
        result = self.rule.apply(sql)
        assert result == "INSERT INTO employees (id, name) VALUES (nextval('emp_seq'), 'John')"

    def test_apply_case_insensitive(self) -> None:
        sql = "SELECT emp_seq.nextval FROM DUAL"
        result = self.rule.apply(sql)
        assert result == "SELECT nextval('emp_seq') FROM DUAL"


class TestCURRVALRule:
    def setup_method(self) -> None:
        self.rule = CURRVALRule()

    def test_matches(self) -> None:
        sql = "SELECT emp_seq.CURRVAL FROM DUAL"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "SELECT currval('emp_seq')"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "SELECT emp_seq.CURRVAL FROM DUAL"
        result = self.rule.apply(sql)
        assert result == "SELECT currval('emp_seq') FROM DUAL"


class TestNOCACHERemovalRule:
    def setup_method(self) -> None:
        self.rule = NOCACHERemovalRule()

    def test_matches(self) -> None:
        sql = "CREATE SEQUENCE audit_seq NOCACHE"
        assert self.rule.matches(sql)

    def test_no_match_cache(self) -> None:
        sql = "CREATE SEQUENCE order_seq CACHE 20"
        assert not self.rule.matches(sql)

    def test_no_match_no_sequence(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "CREATE SEQUENCE audit_seq NOCACHE"
        result = self.rule.apply(sql)
        assert result == "CREATE SEQUENCE audit_seq"


class TestCreateSequenceCleanupRule:
    def setup_method(self) -> None:
        self.rule = CreateSequenceCleanupRule()

    def test_matches_noorder(self) -> None:
        sql = "CREATE SEQUENCE s NOORDER"
        assert self.rule.matches(sql)

    def test_matches_nominvalue(self) -> None:
        sql = "CREATE SEQUENCE s NOMINVALUE"
        assert self.rule.matches(sql)

    def test_matches_nomaxvalue(self) -> None:
        sql = "CREATE SEQUENCE s NOMAXVALUE"
        assert self.rule.matches(sql)

    def test_matches_nocycle(self) -> None:
        sql = "CREATE SEQUENCE s NOCYCLE"
        assert self.rule.matches(sql)

    def test_no_match_plain_sequence(self) -> None:
        sql = "CREATE SEQUENCE emp_seq START WITH 1 INCREMENT BY 1"
        assert not self.rule.matches(sql)

    def test_no_match_non_sequence(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_noorder(self) -> None:
        sql = "CREATE SEQUENCE s START WITH 1 NOORDER"
        result = self.rule.apply(sql)
        assert result == "CREATE SEQUENCE s START WITH 1"

    def test_apply_multiple(self) -> None:
        sql = "CREATE SEQUENCE s NOMINVALUE NOMAXVALUE NOCYCLE NOORDER"
        result = self.rule.apply(sql)
        assert result.strip() == "CREATE SEQUENCE s"
