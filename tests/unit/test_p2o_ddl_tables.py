"""Tests for P2O DDL table rules -- CREATE TABLE conversions."""

from __future__ import annotations

from steindb.rules.p2o_ddl_tables import (
    P2OCreateTempTableRule,
    P2OCreateUnloggedTableRule,
    P2ODefaultCurrentTimestampRule,
    P2OGeneratedAlwaysAsIdentityRule,
    P2OIfNotExistsRule,
)


class TestP2OCreateTempTableRule:
    def setup_method(self) -> None:
        self.rule = P2OCreateTempTableRule()

    def test_matches_temp_table(self) -> None:
        sql = "CREATE TEMP TABLE tmp_results (id INTEGER)"
        assert self.rule.matches(sql)

    def test_matches_temporary_table(self) -> None:
        sql = "CREATE TEMPORARY TABLE tmp_results (id INTEGER)"
        assert self.rule.matches(sql)

    def test_no_match_regular_table(self) -> None:
        sql = "CREATE TABLE employees (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_temp_table(self) -> None:
        sql = "CREATE TEMP TABLE tmp_results (id INTEGER)"
        result = self.rule.apply(sql)
        assert "CREATE GLOBAL TEMPORARY TABLE tmp_results" in result
        assert "ON COMMIT DELETE ROWS" in result

    def test_apply_temporary_table(self) -> None:
        sql = "CREATE TEMPORARY TABLE tmp_results (id INTEGER)"
        result = self.rule.apply(sql)
        assert "CREATE GLOBAL TEMPORARY TABLE tmp_results" in result

    def test_apply_temp_table_with_on_commit_preserve(self) -> None:
        sql = "CREATE TEMP TABLE session_data (id INTEGER) ON COMMIT PRESERVE ROWS"
        result = self.rule.apply(sql)
        assert "CREATE GLOBAL TEMPORARY TABLE session_data" in result
        assert "ON COMMIT PRESERVE ROWS" in result
        # Should not add a second ON COMMIT
        assert result.count("ON COMMIT") == 1

    def test_apply_temp_table_with_on_commit_delete(self) -> None:
        sql = "CREATE TEMP TABLE tmp (id INTEGER) ON COMMIT DELETE ROWS"
        result = self.rule.apply(sql)
        assert "CREATE GLOBAL TEMPORARY TABLE" in result
        assert "ON COMMIT DELETE ROWS" in result
        assert result.count("ON COMMIT") == 1


class TestP2OCreateUnloggedTableRule:
    def setup_method(self) -> None:
        self.rule = P2OCreateUnloggedTableRule()

    def test_matches_unlogged(self) -> None:
        sql = "CREATE UNLOGGED TABLE fast_cache (key TEXT, val TEXT)"
        assert self.rule.matches(sql)

    def test_no_match_regular(self) -> None:
        sql = "CREATE TABLE employees (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_unlogged(self) -> None:
        sql = "CREATE UNLOGGED TABLE fast_cache (key TEXT, val TEXT)"
        result = self.rule.apply(sql)
        assert "CREATE TABLE fast_cache" in result
        assert "UNLOGGED" not in result.split("*/")[-1]
        assert "SteinDB: UNLOGGED removed" in result


class TestP2OIfNotExistsRule:
    def setup_method(self) -> None:
        self.rule = P2OIfNotExistsRule()

    def test_matches_if_not_exists(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS employees (id INTEGER)"
        assert self.rule.matches(sql)

    def test_no_match_regular(self) -> None:
        sql = "CREATE TABLE employees (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_if_not_exists(self) -> None:
        sql = "CREATE TABLE IF NOT EXISTS employees (id INTEGER)"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE employees (id INTEGER)"
        assert "IF NOT EXISTS" not in result

    def test_apply_index_if_not_exists(self) -> None:
        sql = "CREATE INDEX IF NOT EXISTS idx_emp ON employees (name)"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp ON employees (name)"


class TestP2ODefaultCurrentTimestampRule:
    def setup_method(self) -> None:
        self.rule = P2ODefaultCurrentTimestampRule()

    def test_matches_current_timestamp(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        assert self.rule.matches(sql)

    def test_matches_now(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP DEFAULT NOW())"
        assert self.rule.matches(sql)

    def test_no_match_sysdate(self) -> None:
        sql = "CREATE TABLE t (created_at DATE DEFAULT SYSDATE)"
        assert not self.rule.matches(sql)

    def test_apply_current_timestamp(self) -> None:
        sql = "CREATE TABLE t (id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        result = self.rule.apply(sql)
        assert "DEFAULT SYSDATE" in result
        assert "CURRENT_TIMESTAMP" not in result

    def test_apply_now(self) -> None:
        sql = "CREATE TABLE t (created_at TIMESTAMP DEFAULT NOW())"
        result = self.rule.apply(sql)
        assert "DEFAULT SYSDATE" in result
        assert "NOW()" not in result


class TestP2OGeneratedAlwaysAsIdentityRule:
    def setup_method(self) -> None:
        self.rule = P2OGeneratedAlwaysAsIdentityRule()

    def test_matches_generated_always(self) -> None:
        sql = "CREATE TABLE t (id INTEGER GENERATED ALWAYS AS IDENTITY)"
        assert self.rule.matches(sql)

    def test_matches_generated_by_default(self) -> None:
        sql = "CREATE TABLE t (id INTEGER GENERATED BY DEFAULT AS IDENTITY)"
        assert self.rule.matches(sql)

    def test_no_match_regular(self) -> None:
        sql = "CREATE TABLE t (id INTEGER PRIMARY KEY)"
        assert not self.rule.matches(sql)

    def test_apply_generated_always(self) -> None:
        sql = "CREATE TABLE t (id INTEGER GENERATED ALWAYS AS IDENTITY, name VARCHAR(100));"
        result = self.rule.apply(sql)
        assert "id NUMBER NOT NULL" in result
        assert "GENERATED ALWAYS AS IDENTITY" not in result
        assert "CREATE SEQUENCE t_id_seq" in result
        assert "CREATE OR REPLACE TRIGGER t_id_trg" in result
        assert "t_id_seq.NEXTVAL" in result
        assert ":NEW.id" in result

    def test_apply_generated_with_options(self) -> None:
        sql = "CREATE TABLE t (id INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 100 INCREMENT BY 5));"  # noqa: E501
        result = self.rule.apply(sql)
        assert "id NUMBER NOT NULL" in result
        assert "CREATE SEQUENCE t_id_seq" in result

    def test_apply_identity_without_create_table(self) -> None:
        """Line 163: GENERATED ALWAYS AS IDENTITY present but no CREATE TABLE prefix."""
        sql = "ALTER TABLE t ADD COLUMN id INTEGER GENERATED ALWAYS AS IDENTITY"
        result = self.rule.apply(sql)
        # No CREATE TABLE found, so should return SQL unchanged
        assert result == sql


class TestP2OIfNotExistsRuleEdgeCases:
    """Additional edge cases for P2OIfNotExistsRule."""

    def setup_method(self) -> None:
        self.rule = P2OIfNotExistsRule()

    def test_no_match_if_not_exists_without_create(self) -> None:
        """Line 91: SQL has IF NOT EXISTS but no CREATE keyword."""
        sql = "DROP TABLE IF NOT EXISTS employees"
        assert not self.rule.matches(sql)
