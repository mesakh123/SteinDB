"""Tests for materialized view rules."""

from __future__ import annotations

from steindb.rules.materialized_views import (
    MViewBuildDeferredRule,
    MViewCleanupRule,
    MViewRefreshRule,
)


class TestMViewRefreshRule:
    rule = MViewRefreshRule()

    def test_matches_refresh_fast(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv REFRESH FAST ON COMMIT AS SELECT * FROM t;"
        assert self.rule.matches(sql)

    def test_matches_refresh_complete(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv REFRESH COMPLETE AS SELECT 1;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_no_match_no_mview(self) -> None:
        assert not self.rule.matches("REFRESH FAST;")

    def test_apply_strips_refresh(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv REFRESH FAST AS SELECT * FROM t;"
        result = self.rule.apply(sql)
        assert "REFRESH FAST" not in result
        assert "CREATE MATERIALIZED VIEW mv" in result

    def test_apply_on_commit_adds_note(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv REFRESH FAST ON COMMIT AS SELECT 1;"
        result = self.rule.apply(sql)
        assert "pg_cron" in result or "REFRESH MATERIALIZED VIEW" in result

    def test_apply_refresh_force(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv REFRESH FORCE ON DEMAND AS SELECT 1;"
        result = self.rule.apply(sql)
        assert "REFRESH FORCE" not in result


class TestMViewBuildDeferredRule:
    rule = MViewBuildDeferredRule()

    def test_matches(self) -> None:
        assert self.rule.matches("CREATE MATERIALIZED VIEW mv BUILD DEFERRED AS SELECT 1;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE MATERIALIZED VIEW mv AS SELECT 1;")

    def test_apply(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv BUILD DEFERRED AS SELECT 1;"
        result = self.rule.apply(sql)
        assert "WITH NO DATA" in result
        assert "BUILD DEFERRED" not in result


class TestMViewCleanupRule:
    rule = MViewCleanupRule()

    def test_matches_build_immediate(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv BUILD IMMEDIATE AS SELECT 1;"
        assert self.rule.matches(sql)

    def test_matches_query_rewrite(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv ENABLE QUERY REWRITE AS SELECT 1;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE MATERIALIZED VIEW mv AS SELECT 1;")

    def test_apply_build_immediate(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv BUILD IMMEDIATE AS SELECT 1;"
        result = self.rule.apply(sql)
        assert "BUILD IMMEDIATE" not in result
        assert "CREATE MATERIALIZED VIEW mv" in result

    def test_apply_query_rewrite(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv ENABLE QUERY REWRITE AS SELECT 1;"
        result = self.rule.apply(sql)
        assert "ENABLE QUERY REWRITE" not in result

    def test_apply_multiple_options(self) -> None:
        sql = "CREATE MATERIALIZED VIEW mv BUILD IMMEDIATE ENABLE QUERY REWRITE USING INDEX AS SELECT 1;"  # noqa: E501
        result = self.rule.apply(sql)
        assert "BUILD IMMEDIATE" not in result
        assert "ENABLE QUERY REWRITE" not in result
        assert "USING INDEX" not in result
