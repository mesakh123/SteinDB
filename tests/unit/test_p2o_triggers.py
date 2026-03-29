"""Tests for P2O trigger rewrite rules."""

from __future__ import annotations

from steindb.rules.p2o_triggers import (
    PGNewOldToColonRule,
    SimpleTriggerBodyRule,
    TriggerFunctionMergeRule,
)


class TestPGNewOldToColonRule:
    rule = PGNewOldToColonRule()

    def test_matches_new_in_trigger(self) -> None:
        sql = (
            "CREATE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION f(); NEW.col := 1;"
        )
        assert self.rule.matches(sql)

    def test_matches_old_in_trigger(self) -> None:
        sql = "CREATE TRIGGER trg BEFORE UPDATE ON t FOR EACH ROW EXECUTE FUNCTION f(); OLD.salary"
        assert self.rule.matches(sql)

    def test_no_match_without_trigger_context(self) -> None:
        assert not self.rule.matches("NEW.col := 1;")

    def test_no_match_already_colon(self) -> None:
        sql = "CREATE TRIGGER trg BEFORE INSERT ON t; :NEW.col := 1;"
        assert not self.rule.matches(sql)

    def test_apply(self) -> None:
        sql = "CREATE TRIGGER trg BEFORE INSERT ON t; NEW.employee_id := 1;"
        result = self.rule.apply(sql)
        assert ":NEW.employee_id" in result

    def test_apply_old(self) -> None:
        sql = "CREATE TRIGGER trg AFTER UPDATE ON t; IF OLD.salary != NEW.salary THEN"
        result = self.rule.apply(sql)
        assert ":OLD.salary" in result
        assert ":NEW.salary" in result


class TestTriggerFunctionMergeRule:
    rule = TriggerFunctionMergeRule()

    def test_matches_simple(self) -> None:
        sql = (
            "CREATE OR REPLACE FUNCTION trg_audit_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    NEW.created_at := CURRENT_TIMESTAMP;\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "\n"
            "CREATE TRIGGER trg_audit BEFORE INSERT ON employees\n"
            "FOR EACH ROW EXECUTE FUNCTION trg_audit_func();"
        )
        assert self.rule.matches(sql)

    def test_no_match_no_trigger(self) -> None:
        sql = (
            "CREATE OR REPLACE FUNCTION my_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;"
        )
        assert not self.rule.matches(sql)

    def test_no_match_mismatched_func(self) -> None:
        sql = (
            "CREATE FUNCTION func_a() RETURNS TRIGGER AS $$\n"
            "BEGIN RETURN NEW; END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION func_b();"
        )
        assert not self.rule.matches(sql)

    def test_apply_simple(self) -> None:
        sql = (
            "CREATE OR REPLACE FUNCTION trg_audit_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    NEW.created_at := CURRENT_TIMESTAMP;\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "\n"
            "CREATE TRIGGER trg_audit BEFORE INSERT ON employees\n"
            "FOR EACH ROW EXECUTE FUNCTION trg_audit_func();"
        )
        result = self.rule.apply(sql)
        assert "CREATE OR REPLACE TRIGGER trg_audit" in result
        assert "BEFORE INSERT ON employees" in result
        assert "FOR EACH ROW" in result
        assert "BEGIN" in result
        assert "END trg_audit;" in result
        assert "RETURNS TRIGGER" not in result
        assert "$$ LANGUAGE plpgsql" not in result
        assert "EXECUTE FUNCTION" not in result

    def test_apply_removes_return_new(self) -> None:
        sql = (
            "CREATE FUNCTION trg_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    NEW.updated_at := CURRENT_TIMESTAMP;\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg BEFORE UPDATE ON t\n"
            "FOR EACH ROW EXECUTE FUNCTION trg_func();"
        )
        result = self.rule.apply(sql)
        assert "RETURN NEW" not in result

    def test_apply_after_trigger(self) -> None:
        sql = (
            "CREATE FUNCTION log_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    INSERT INTO audit_log VALUES(1);\n"
            "    RETURN NULL;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg_log AFTER INSERT ON orders\n"
            "FOR EACH ROW EXECUTE FUNCTION log_func();"
        )
        result = self.rule.apply(sql)
        assert "AFTER INSERT ON orders" in result
        assert "RETURN NULL" not in result

    def test_apply_removes_multiple_return_new(self) -> None:
        """Bug fix: multiple RETURN NEW/OLD in IF/ELSE branches should all be removed."""
        sql = (
            "CREATE FUNCTION trg_func() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    IF NEW.status = 'active' THEN\n"
            "        NEW.created_at := CURRENT_TIMESTAMP;\n"
            "        RETURN NEW;\n"
            "    ELSE\n"
            "        NEW.updated_at := CURRENT_TIMESTAMP;\n"
            "        RETURN NEW;\n"
            "    END IF;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg_ts BEFORE INSERT OR UPDATE ON items\n"
            "FOR EACH ROW EXECUTE FUNCTION trg_func();"
        )
        result = self.rule.apply(sql)
        assert "RETURN NEW" not in result
        assert "BEFORE INSERT OR UPDATE ON items" in result

    def test_apply_with_declare(self) -> None:
        sql = (
            "CREATE FUNCTION trg_calc_func() RETURNS TRIGGER AS $$\n"
            "DECLARE v_total NUMBER;\n"
            "BEGIN\n"
            "    v_total := 0;\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg_calc BEFORE INSERT ON items\n"
            "FOR EACH ROW EXECUTE FUNCTION trg_calc_func();"
        )
        result = self.rule.apply(sql)
        assert "DECLARE" in result
        assert "v_total" in result

    def test_apply_no_func_match_returns_unchanged(self) -> None:
        """Line 107: apply() returns early when function or trigger not found."""
        sql = "CREATE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION f();"
        result = self.rule.apply(sql)
        # No function definition present, so apply should return unchanged
        assert result == sql

    def test_apply_mismatched_func_names_returns_unchanged(self) -> None:
        """Line 113: apply() returns early when function names don't match."""
        sql = (
            "CREATE FUNCTION func_alpha() RETURNS TRIGGER AS $$\n"
            "BEGIN\n"
            "    NEW.col := 1;\n"
            "    RETURN NEW;\n"
            "END;\n"
            "$$ LANGUAGE plpgsql;\n"
            "CREATE TRIGGER trg BEFORE INSERT ON t\n"
            "FOR EACH ROW EXECUTE FUNCTION func_beta();"
        )
        result = self.rule.apply(sql)
        # Function names don't match, so apply should return unchanged
        assert result == sql


class TestSimpleTriggerBodyRule:
    rule = SimpleTriggerBodyRule()

    def test_matches_tg_op(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS TRIGGER AS $$ BEGIN IF TG_OP = 'INSERT' THEN END IF; END; $$"  # noqa: E501
        assert self.rule.matches(sql)

    def test_matches_perform(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS TRIGGER AS $$ BEGIN PERFORM notify(); END; $$"
        assert self.rule.matches(sql)

    def test_no_match_simple(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS TRIGGER AS $$ BEGIN NEW.col := 1; END; $$"
        assert not self.rule.matches(sql)

    def test_no_match_no_trigger(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS INT AS $$ BEGIN IF TG_OP THEN END IF; END; $$"
        assert not self.rule.matches(sql)

    def test_apply_adds_comment(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS TRIGGER AS $$ BEGIN IF TG_OP = 'INSERT' THEN END IF; END; $$"  # noqa: E501
        result = self.rule.apply(sql)
        assert "LLM_FORWARD" in result
        assert "Complex trigger detected" in result
        assert "TG_OP" in result

    def test_apply_multiple_features(self) -> None:
        sql = "CREATE FUNCTION f() RETURNS TRIGGER AS $$ BEGIN IF TG_OP THEN PERFORM log(); END IF; END; $$"  # noqa: E501
        result = self.rule.apply(sql)
        assert "TG_OP" in result
        assert "PERFORM" in result
