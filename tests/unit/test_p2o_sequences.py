"""Tests for P2O sequence rules -- nextval/currval and CREATE SEQUENCE."""

from __future__ import annotations

from steindb.rules.p2o_sequences import (
    P2OCurrvalRule,
    P2ONextvalRule,
    P2OSequenceCache1Rule,
    P2OSequenceNoCycleRule,
    P2OSequenceNoMaxvalueRule,
    P2OSequenceNoMinvalueRule,
)


class TestP2ONextvalRule:
    def setup_method(self) -> None:
        self.rule = P2ONextvalRule()

    def test_matches_nextval(self) -> None:
        sql = "INSERT INTO t (id) VALUES (nextval('my_seq'))"
        assert self.rule.matches(sql)

    def test_no_match_oracle_nextval(self) -> None:
        sql = "INSERT INTO t (id) VALUES (my_seq.NEXTVAL)"
        assert not self.rule.matches(sql)

    def test_apply_nextval(self) -> None:
        sql = "INSERT INTO t (id) VALUES (nextval('my_seq'))"
        result = self.rule.apply(sql)
        assert "my_seq.NEXTVAL" in result
        assert "nextval" not in result

    def test_apply_nextval_schema_qualified(self) -> None:
        sql = "SELECT nextval('public.my_seq')"
        result = self.rule.apply(sql)
        assert "public.my_seq.NEXTVAL" in result

    def test_apply_nextval_in_default(self) -> None:
        sql = "CREATE TABLE t (id INTEGER DEFAULT nextval('t_id_seq'))"
        result = self.rule.apply(sql)
        assert "DEFAULT t_id_seq.NEXTVAL" in result


class TestP2OCurrvalRule:
    def setup_method(self) -> None:
        self.rule = P2OCurrvalRule()

    def test_matches_currval(self) -> None:
        sql = "SELECT currval('my_seq')"
        assert self.rule.matches(sql)

    def test_no_match_oracle_currval(self) -> None:
        sql = "SELECT my_seq.CURRVAL FROM DUAL"
        assert not self.rule.matches(sql)

    def test_apply_currval(self) -> None:
        sql = "SELECT currval('my_seq')"
        result = self.rule.apply(sql)
        assert "my_seq.CURRVAL" in result
        assert "currval" not in result


class TestP2OSequenceNoCycleRule:
    def setup_method(self) -> None:
        self.rule = P2OSequenceNoCycleRule()

    def test_matches_no_cycle(self) -> None:
        sql = "CREATE SEQUENCE my_seq START WITH 1 NO CYCLE"
        assert self.rule.matches(sql)

    def test_no_match_nocycle(self) -> None:
        sql = "CREATE SEQUENCE my_seq START WITH 1 NOCYCLE"
        assert not self.rule.matches(sql)

    def test_no_match_non_sequence(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_no_cycle(self) -> None:
        sql = "CREATE SEQUENCE my_seq START WITH 1 NO CYCLE"
        result = self.rule.apply(sql)
        assert "NOCYCLE" in result
        assert "NO CYCLE" not in result


class TestP2OSequenceCache1Rule:
    def setup_method(self) -> None:
        self.rule = P2OSequenceCache1Rule()

    def test_matches_cache_1(self) -> None:
        sql = "CREATE SEQUENCE my_seq CACHE 1"
        assert self.rule.matches(sql)

    def test_no_match_cache_20(self) -> None:
        sql = "CREATE SEQUENCE my_seq CACHE 20"
        assert not self.rule.matches(sql)

    def test_apply_cache_1(self) -> None:
        sql = "CREATE SEQUENCE my_seq START WITH 1 CACHE 1"
        result = self.rule.apply(sql)
        assert "NOCACHE" in result
        assert "CACHE 1" not in result


class TestP2OSequenceNoMinvalueRule:
    def setup_method(self) -> None:
        self.rule = P2OSequenceNoMinvalueRule()

    def test_matches_no_minvalue(self) -> None:
        sql = "CREATE SEQUENCE my_seq NO MINVALUE"
        assert self.rule.matches(sql)

    def test_apply_no_minvalue(self) -> None:
        sql = "CREATE SEQUENCE my_seq NO MINVALUE"
        result = self.rule.apply(sql)
        assert "NOMINVALUE" in result
        assert "NO MINVALUE" not in result


class TestP2OSequenceNoMaxvalueRule:
    def setup_method(self) -> None:
        self.rule = P2OSequenceNoMaxvalueRule()

    def test_matches_no_maxvalue(self) -> None:
        sql = "CREATE SEQUENCE my_seq NO MAXVALUE"
        assert self.rule.matches(sql)

    def test_apply_no_maxvalue(self) -> None:
        sql = "CREATE SEQUENCE my_seq NO MAXVALUE"
        result = self.rule.apply(sql)
        assert "NOMAXVALUE" in result
        assert "NO MAXVALUE" not in result
