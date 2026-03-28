"""Tests for P2O grant/revoke rules."""

from __future__ import annotations

from steindb.rules.p2o_grants import (
    P2OGrantExecuteRule,
    P2OGrantPassthroughRule,
    P2ORevokeExecuteRule,
)


class TestP2OGrantExecuteRule:
    def setup_method(self) -> None:
        self.rule = P2OGrantExecuteRule()

    def test_matches_grant_execute_on_function(self) -> None:
        sql = "GRANT EXECUTE ON FUNCTION public.my_func TO app_user"
        assert self.rule.matches(sql)

    def test_matches_grant_execute_on_procedure(self) -> None:
        sql = "GRANT EXECUTE ON PROCEDURE public.my_proc TO app_user"
        assert self.rule.matches(sql)

    def test_no_match_grant_without_function(self) -> None:
        sql = "GRANT EXECUTE ON public.my_func TO app_user"
        assert not self.rule.matches(sql)

    def test_no_match_grant_select(self) -> None:
        sql = "GRANT SELECT ON employees TO app_user"
        assert not self.rule.matches(sql)

    def test_apply_remove_function(self) -> None:
        sql = "GRANT EXECUTE ON FUNCTION public.my_func TO app_user"
        result = self.rule.apply(sql)
        assert result == "GRANT EXECUTE ON public.my_func TO app_user"
        assert "FUNCTION" not in result

    def test_apply_remove_procedure(self) -> None:
        sql = "GRANT EXECUTE ON PROCEDURE public.my_proc TO app_user"
        result = self.rule.apply(sql)
        assert result == "GRANT EXECUTE ON public.my_proc TO app_user"
        assert "PROCEDURE" not in result


class TestP2ORevokeExecuteRule:
    def setup_method(self) -> None:
        self.rule = P2ORevokeExecuteRule()

    def test_matches_revoke_execute_on_function(self) -> None:
        sql = "REVOKE EXECUTE ON FUNCTION public.my_func FROM app_user"
        assert self.rule.matches(sql)

    def test_no_match_revoke_without_function(self) -> None:
        sql = "REVOKE EXECUTE ON public.my_func FROM app_user"
        assert not self.rule.matches(sql)

    def test_apply_remove_function(self) -> None:
        sql = "REVOKE EXECUTE ON FUNCTION public.my_func FROM app_user"
        result = self.rule.apply(sql)
        assert result == "REVOKE EXECUTE ON public.my_func FROM app_user"
        assert "FUNCTION" not in result


class TestP2OGrantPassthroughRule:
    def setup_method(self) -> None:
        self.rule = P2OGrantPassthroughRule()

    def test_matches_grant(self) -> None:
        sql = "GRANT SELECT ON employees TO app_user"
        assert self.rule.matches(sql)

    def test_matches_revoke(self) -> None:
        sql = "REVOKE INSERT ON employees FROM app_user"
        assert self.rule.matches(sql)

    def test_no_match_create(self) -> None:
        sql = "CREATE TABLE t (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_passthrough(self) -> None:
        sql = "GRANT SELECT, INSERT ON employees TO app_user"
        result = self.rule.apply(sql)
        assert result == sql
