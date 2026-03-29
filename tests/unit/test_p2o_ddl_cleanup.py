"""Tests for P2O DDL cleanup rules -- strip PostgreSQL-specific clauses."""

from __future__ import annotations

from steindb.rules.p2o_ddl_cleanup import (
    P2OConcurrentlyRemovalRule,
    P2OIncludeColumnsRemovalRule,
    P2OPartialIndexWhereRemovalRule,
    P2OTablespacePgDefaultRemovalRule,
    P2OUsingIndexRemovalRule,
    P2OWithStorageParamsRemovalRule,
)


class TestP2OUsingIndexRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OUsingIndexRemovalRule()

    def test_matches_using_index(self) -> None:
        sql = "ALTER TABLE t ADD CONSTRAINT pk_t PRIMARY KEY (id) USING INDEX idx_pk"
        assert self.rule.matches(sql)

    def test_no_match_regular(self) -> None:
        sql = "ALTER TABLE t ADD CONSTRAINT pk_t PRIMARY KEY (id)"
        assert not self.rule.matches(sql)

    def test_apply_using_index(self) -> None:
        sql = "ALTER TABLE t ADD CONSTRAINT pk_t PRIMARY KEY (id) USING INDEX idx_pk"
        result = self.rule.apply(sql)
        assert "USING INDEX" not in result
        assert "PRIMARY KEY (id)" in result


class TestP2OTablespacePgDefaultRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OTablespacePgDefaultRemovalRule()

    def test_matches_tablespace_pg_default(self) -> None:
        sql = "CREATE TABLE t (id INTEGER) TABLESPACE pg_default"
        assert self.rule.matches(sql)

    def test_no_match_no_tablespace(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_tablespace_pg_default(self) -> None:
        sql = "CREATE TABLE t (id INTEGER) TABLESPACE pg_default"
        result = self.rule.apply(sql)
        assert "TABLESPACE" not in result
        assert "pg_default" not in result
        assert "CREATE TABLE t (id INTEGER)" in result


class TestP2OWithStorageParamsRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OWithStorageParamsRemovalRule()

    def test_matches_fillfactor(self) -> None:
        sql = "CREATE TABLE t (id INTEGER) WITH (fillfactor=70)"
        assert self.rule.matches(sql)

    def test_matches_autovacuum(self) -> None:
        sql = "CREATE TABLE t (id INTEGER) WITH (autovacuum_enabled=false)"
        assert self.rule.matches(sql)

    def test_no_match_with_cte(self) -> None:
        sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        assert not self.rule.matches(sql)

    def test_apply_fillfactor(self) -> None:
        sql = "CREATE TABLE t (id INTEGER) WITH (fillfactor=70)"
        result = self.rule.apply(sql)
        assert "fillfactor" not in result
        assert "WITH" not in result
        assert "CREATE TABLE t (id INTEGER)" in result

    def test_apply_toast(self) -> None:
        sql = "CREATE TABLE t (data TEXT) WITH (toast_tuple_target=8160)"
        result = self.rule.apply(sql)
        assert "toast_tuple_target" not in result


class TestP2OIncludeColumnsRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OIncludeColumnsRemovalRule()

    def test_matches_include(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (dept_id) INCLUDE (name, salary)"
        assert self.rule.matches(sql)

    def test_no_match_regular_index(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (dept_id)"
        assert not self.rule.matches(sql)

    def test_apply_include(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (dept_id) INCLUDE (name, salary)"
        result = self.rule.apply(sql)
        assert "INCLUDE" not in result
        assert "name, salary" not in result
        assert "CREATE INDEX idx_emp ON employees (dept_id)" in result


class TestP2OPartialIndexWhereRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OPartialIndexWhereRemovalRule()

    def test_matches_partial_index(self) -> None:
        sql = "CREATE INDEX idx_active ON employees (name) WHERE status = 'ACTIVE'"
        assert self.rule.matches(sql)

    def test_no_match_regular_index(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name)"
        assert not self.rule.matches(sql)

    def test_apply_partial_index(self) -> None:
        sql = "CREATE INDEX idx_active ON employees (name) WHERE status = 'ACTIVE'"
        result = self.rule.apply(sql)
        assert "WHERE status" not in result
        assert "SteinDB: partial index WHERE clause removed" in result
        assert "CREATE INDEX idx_active ON employees (name)" in result

    def test_apply_unique_partial_index(self) -> None:
        sql = "CREATE UNIQUE INDEX idx_email ON users (email) WHERE deleted_at IS NULL"
        result = self.rule.apply(sql)
        assert "WHERE deleted_at" not in result
        assert "CREATE UNIQUE INDEX idx_email ON users (email)" in result


class TestP2OConcurrentlyRemovalRule:
    def setup_method(self) -> None:
        self.rule = P2OConcurrentlyRemovalRule()

    def test_matches_concurrently(self) -> None:
        sql = "CREATE INDEX CONCURRENTLY idx_emp ON employees (name)"
        assert self.rule.matches(sql)

    def test_matches_unique_concurrently(self) -> None:
        sql = "CREATE UNIQUE INDEX CONCURRENTLY idx_email ON users (email)"
        assert self.rule.matches(sql)

    def test_no_match_regular_index(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name)"
        assert not self.rule.matches(sql)

    def test_apply_concurrently(self) -> None:
        sql = "CREATE INDEX CONCURRENTLY idx_emp ON employees (name)"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp ON employees (name)"
        assert "CONCURRENTLY" not in result

    def test_apply_unique_concurrently(self) -> None:
        sql = "CREATE UNIQUE INDEX CONCURRENTLY idx_email ON users (email)"
        result = self.rule.apply(sql)
        assert result == "CREATE UNIQUE INDEX idx_email ON users (email)"
