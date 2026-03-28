"""Tests for grant/revoke rules."""

from __future__ import annotations

from steindb.rules.grants import GrantExecuteRule, GrantPassthroughRule


class TestGrantExecuteRule:
    rule = GrantExecuteRule()

    def test_matches_schema_qualified(self) -> None:
        assert self.rule.matches("GRANT EXECUTE ON pkg.func TO app_user;")

    def test_no_match_already_qualified(self) -> None:
        assert not self.rule.matches("GRANT EXECUTE ON FUNCTION pkg.func TO app_user;")

    def test_no_match_simple(self) -> None:
        assert not self.rule.matches("GRANT SELECT ON employees TO reader;")

    def test_apply(self) -> None:
        sql = "GRANT EXECUTE ON util_pkg.get_total TO app_user;"
        result = self.rule.apply(sql)
        assert "GRANT EXECUTE ON FUNCTION util_pkg.get_total TO app_user" in result

    def test_apply_preserves_grantee(self) -> None:
        sql = "GRANT EXECUTE ON pkg.proc TO admin_role;"
        result = self.rule.apply(sql)
        assert "TO admin_role" in result


class TestGrantPassthroughRule:
    rule = GrantPassthroughRule()

    def test_matches_grant(self) -> None:
        assert self.rule.matches("GRANT SELECT ON employees TO reader;")

    def test_matches_revoke(self) -> None:
        assert self.rule.matches("REVOKE INSERT ON orders FROM writer;")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT * FROM employees;")

    def test_apply_passthrough(self) -> None:
        sql = "GRANT SELECT, INSERT ON employees TO app_user;"
        result = self.rule.apply(sql)
        assert result == sql  # No changes

    def test_apply_revoke_passthrough(self) -> None:
        sql = "REVOKE ALL ON schema.table FROM old_user;"
        result = self.rule.apply(sql)
        assert result == sql
