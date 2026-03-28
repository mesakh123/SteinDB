"""Tests for DDL index rules — cleanup and BITMAP index conversion."""

from __future__ import annotations

from steindb.rules.ddl_indexes import (
    BitmapIndexRule,
    CreateIndexCleanupRule,
)


class TestCreateIndexCleanupRule:
    def setup_method(self) -> None:
        self.rule = CreateIndexCleanupRule()

    def test_matches_compute_statistics(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) COMPUTE STATISTICS"
        assert self.rule.matches(sql)

    def test_matches_online(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) ONLINE"
        assert self.rule.matches(sql)

    def test_matches_reverse(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) REVERSE"
        assert self.rule.matches(sql)

    def test_no_match_plain_index(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name)"
        assert not self.rule.matches(sql)

    def test_no_match_non_index(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_compute_statistics(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) COMPUTE STATISTICS"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp ON employees (name)"

    def test_apply_online(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) ONLINE"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp ON employees (name)"

    def test_apply_reverse(self) -> None:
        sql = "CREATE INDEX idx_emp ON employees (name) REVERSE"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp ON employees (name)"


class TestBitmapIndexRule:
    def setup_method(self) -> None:
        self.rule = BitmapIndexRule()

    def test_matches(self) -> None:
        sql = "CREATE BITMAP INDEX idx_status ON orders (status)"
        assert self.rule.matches(sql)

    def test_no_match_regular_index(self) -> None:
        sql = "CREATE INDEX idx_name ON employees (name)"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "CREATE BITMAP INDEX idx_status ON orders (status)"
        result = self.rule.apply(sql)
        assert "CREATE INDEX idx_status ON orders (status)" in result
        assert "WARNING" in result
        assert "BITMAP" not in result.split("\n")[1]  # BITMAP removed from actual SQL
