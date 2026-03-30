"""Tests for trigger rewrite rules."""

from __future__ import annotations

from steindb.contracts.models import ScannedObject
from steindb.rules.engine import O2PRuleEngine
from steindb.rules.loader import create_direction_registry
from steindb.rules.triggers import (
    AutoIncrementTriggerRule,
    NewOldPrefixRule,
    RaiseApplicationErrorRule,
    TriggerBodyExtractionRule,
)


class TestNewOldPrefixRule:
    rule = NewOldPrefixRule()

    def test_matches_new(self) -> None:
        assert self.rule.matches(":NEW.col := 1;")

    def test_matches_old(self) -> None:
        assert self.rule.matches(":OLD.salary")

    def test_no_match(self) -> None:
        assert not self.rule.matches("SELECT NEW.col FROM t")

    def test_apply_new(self) -> None:
        result = self.rule.apply(":NEW.employee_id := seq.NEXTVAL;")
        assert result == "NEW.employee_id := seq.NEXTVAL;"

    def test_apply_old(self) -> None:
        result = self.rule.apply("IF :OLD.salary != :NEW.salary THEN")
        assert result == "IF OLD.salary != NEW.salary THEN"

    def test_apply_mixed_case(self) -> None:
        result = self.rule.apply(":new.col := :Old.val;")
        assert result == "NEW.col := OLD.val;"

    def test_multiple_refs(self) -> None:
        sql = ":NEW.a := :OLD.b + :NEW.c;"
        result = self.rule.apply(sql)
        assert ":NEW" not in result
        assert ":OLD" not in result
        assert "NEW.a" in result
        assert "OLD.b" in result
        assert "NEW.c" in result


class TestRaiseApplicationErrorRule:
    rule = RaiseApplicationErrorRule()

    def test_matches(self) -> None:
        assert self.rule.matches("RAISE_APPLICATION_ERROR(-20001, 'Bad input');")

    def test_no_match(self) -> None:
        assert not self.rule.matches("RAISE EXCEPTION 'error';")

    def test_apply(self) -> None:
        result = self.rule.apply("RAISE_APPLICATION_ERROR(-20001, 'Invalid ID');")
        assert result == "RAISE EXCEPTION 'Invalid ID';"

    def test_apply_with_concatenation(self) -> None:
        result = self.rule.apply("RAISE_APPLICATION_ERROR(-20002, 'Error: ' || v_msg)")
        assert "RAISE EXCEPTION '%', 'Error: ' || v_msg" in result

    def test_positive_error_code(self) -> None:
        result = self.rule.apply("RAISE_APPLICATION_ERROR(20001, 'msg')")
        assert "RAISE EXCEPTION 'msg'" in result


class TestAutoIncrementTriggerRule:
    rule = AutoIncrementTriggerRule()

    def test_matches_sequence_trigger(self) -> None:
        sql = "SELECT emp_seq.NEXTVAL INTO :NEW.id FROM DUAL;"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("INSERT INTO t VALUES (1);")

    def test_apply(self) -> None:
        sql = "SELECT emp_seq.NEXTVAL INTO :NEW.id FROM DUAL;"
        result = self.rule.apply(sql)
        assert "GENERATED ALWAYS AS IDENTITY" in result
        assert "id" in result

    def test_identifies_column(self) -> None:
        sql = "SELECT my_seq.NEXTVAL INTO :NEW.employee_id FROM DUAL;"
        result = self.rule.apply(sql)
        assert "employee_id" in result


class TestTriggerBodyExtractionRule:
    rule = TriggerBodyExtractionRule()

    def test_matches_simple_trigger(self) -> None:
        sql = (
            "CREATE OR REPLACE TRIGGER trg_audit "
            "BEFORE INSERT ON employees FOR EACH ROW "
            "BEGIN "
            "NEW.created_at := CURRENT_TIMESTAMP; "
            "END;"
        )
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INT);")

    def test_apply_simple(self) -> None:
        sql = (
            "CREATE OR REPLACE TRIGGER trg_audit "
            "BEFORE INSERT ON employees FOR EACH ROW "
            "BEGIN "
            "NEW.created_at := CURRENT_TIMESTAMP; "
            "END;"
        )
        result = self.rule.apply(sql)
        assert "CREATE OR REPLACE FUNCTION trg_audit_func() RETURNS TRIGGER" in result
        assert "$$ LANGUAGE plpgsql;" in result
        assert "CREATE TRIGGER trg_audit BEFORE INSERT ON employees" in result
        assert "EXECUTE FUNCTION trg_audit_func()" in result

    def test_apply_after_update(self) -> None:
        sql = (
            "CREATE TRIGGER trg_log "
            "AFTER UPDATE ON orders FOR EACH ROW "
            "BEGIN "
            "INSERT INTO audit_log VALUES(1); "
            "END;"
        )
        result = self.rule.apply(sql)
        assert "AFTER UPDATE" in result
        assert "trg_log_func" in result
        assert "RETURN NULL;" in result

    def test_apply_before_delete_returns_old(self) -> None:
        sql = (
            "CREATE TRIGGER trg_del "
            "BEFORE DELETE ON orders FOR EACH ROW "
            "BEGIN "
            "INSERT INTO audit_log VALUES(1); "
            "END;"
        )
        result = self.rule.apply(sql)
        assert "RETURN OLD;" in result

    def test_apply_before_insert_returns_new(self) -> None:
        sql = (
            "CREATE OR REPLACE TRIGGER trg_audit "
            "BEFORE INSERT ON employees FOR EACH ROW "
            "BEGIN "
            "NEW.created_at := CURRENT_TIMESTAMP; "
            "END;"
        )
        result = self.rule.apply(sql)
        assert "RETURN NEW;" in result

    def test_preserves_declare(self) -> None:
        sql = (
            "CREATE OR REPLACE TRIGGER trg_calc "
            "BEFORE INSERT ON items FOR EACH ROW "
            "DECLARE v_total NUMBER; "
            "BEGIN "
            "v_total := 0; "
            "END;"
        )
        result = self.rule.apply(sql)
        assert "DECLARE" in result
        assert "v_total" in result


class TestTriggerNoDuplicateLanguagePlpgsql:
    """Regression: $$ LANGUAGE plpgsql; must appear exactly once after full pipeline."""

    def test_no_duplicate_language_plpgsql_via_engine(self) -> None:
        sql = (
            "CREATE OR REPLACE TRIGGER trg_emp_audit\n"
            "BEFORE UPDATE ON employees\n"
            "FOR EACH ROW\n"
            "BEGIN\n"
            "  INSERT INTO audit_log (action, old_name, new_name)\n"
            "  VALUES ('UPDATE', :OLD.name, :NEW.name);\n"
            "END;"
        )
        registry = create_direction_registry("o2p")
        engine = O2PRuleEngine(registry)
        obj = ScannedObject(
            name="trg_emp_audit",
            object_type="TRIGGER",
            source_sql=sql,
            schema="HR",
            line_count=7,
        )
        result = engine.convert(obj)
        target = result.target_sql
        count = target.count("$$ LANGUAGE plpgsql;")
        assert count == 1, (
            f"Expected exactly 1 occurrence of '$$ LANGUAGE plpgsql;', "
            f"found {count}.\nOutput:\n{target}"
        )
        # Verify correct structure
        assert "CREATE OR REPLACE FUNCTION trg_emp_audit_func()" in target
        assert "RETURNS TRIGGER" in target
        assert "CREATE TRIGGER trg_emp_audit BEFORE UPDATE ON employees" in target
        assert "EXECUTE FUNCTION trg_emp_audit_func()" in target
        assert "RETURN NEW;" in target
        # :OLD/:NEW should be converted
        assert ":OLD" not in target
        assert ":NEW" not in target
