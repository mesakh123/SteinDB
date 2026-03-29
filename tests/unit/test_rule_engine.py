# tests/unit/test_rule_engine.py
"""Tests for the Rule Engine orchestrator."""

from __future__ import annotations

from steindb.contracts.models import (
    ConvertedObject,
    ForwardedObject,
    ObjectType,
    ScannedObject,
)
from steindb.rules.base import Rule, RuleCategory
from steindb.rules.engine import RuleEngine
from steindb.rules.registry import RuleRegistry


def _make_scanned(
    name: str = "test_obj",
    source_sql: str = "SELECT 1 FROM DUAL",
    object_type: ObjectType = ObjectType.TABLE,
) -> ScannedObject:
    return ScannedObject(
        name=name,
        schema="HR",
        object_type=object_type,
        source_sql=source_sql,
        line_count=1,
    )


class DualRemovalRule(Rule):
    """Simple test rule: removes FROM DUAL."""

    name = "dual_removal"
    category = RuleCategory.SYNTAX_MISC
    priority = 10

    def matches(self, sql: str) -> bool:
        return "FROM DUAL" in sql.upper()

    def apply(self, sql: str) -> str:
        import re

        return re.sub(r"\s+FROM\s+DUAL", "", sql, flags=re.IGNORECASE)


class TestRuleEngineConvert:
    def test_convert_simple_object(self) -> None:
        registry = RuleRegistry()
        registry.register(DualRemovalRule())
        engine = RuleEngine(registry)

        obj = _make_scanned(source_sql="SELECT 1 FROM DUAL")
        result = engine.convert(obj)

        assert isinstance(result, ConvertedObject)
        assert result.target_sql == "SELECT 1"
        assert result.confidence == 1.0
        assert result.method == "rules"
        assert "dual_removal" in result.rules_applied

    def test_convert_no_matching_rules(self) -> None:
        """Object with no matching rules still returns ConvertedObject (unchanged)."""
        registry = RuleRegistry()
        engine = RuleEngine(registry)

        obj = _make_scanned(source_sql="SELECT 1")
        result = engine.convert(obj)

        assert isinstance(result, ConvertedObject)
        assert result.target_sql == "SELECT 1"
        assert result.rules_applied == []

    def test_convert_preserves_metadata(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)

        obj = _make_scanned(name="my_table", source_sql="SELECT 1")
        result = engine.convert(obj)

        assert isinstance(result, ConvertedObject)
        assert result.name == "my_table"
        assert result.schema == "HR"
        assert result.object_type == ObjectType.TABLE


class TestLLMDecisionBoundary:
    def test_dbms_lob_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="BEGIN DBMS_LOB.OPEN(lob_loc); END;")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "DBMS_LOB" in reason

    def test_dbms_sql_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="v_cursor := DBMS_SQL.OPEN_CURSOR;")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "DBMS_SQL" in reason

    def test_utl_file_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="UTL_FILE.PUT_LINE(file_handle, 'data');")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "UTL_FILE" in reason

    def test_autonomous_transaction_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(
            source_sql="PRAGMA AUTONOMOUS_TRANSACTION; BEGIN INSERT INTO log; COMMIT; END;"
        )
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "AUTONOMOUS_TRANSACTION" in reason

    def test_pipe_row_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="PIPE ROW(out_rec); RETURN;")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "PIPE ROW" in reason

    def test_model_clause_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(
            source_sql="SELECT * FROM sales MODEL DIMENSION BY (product) MEASURES (qty) RULES (qty['A'] = 100)"  # noqa: E501
        )
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is True
        assert "MODEL" in reason

    def test_simple_table_not_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="CREATE TABLE employees (id NUMBER(10), name VARCHAR2(100))")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is False
        assert reason == ""

    def test_simple_select_not_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(source_sql="SELECT NVL(col, 0) FROM my_table")
        should_forward, reason = engine.should_forward_to_llm(obj)
        assert should_forward is False

    def test_forward_returns_forwarded_object(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        obj = _make_scanned(
            name="complex_proc",
            source_sql="BEGIN DBMS_SQL.PARSE(cur, stmt, DBMS_SQL.NATIVE); END;",
        )
        result = engine.convert(obj)
        assert isinstance(result, ForwardedObject)
        assert result.name == "complex_proc"
        assert "DBMS_SQL" in result.forward_reason


class TestRuleEngineBatch:
    def test_batch_splits_converted_and_forwarded(self) -> None:
        registry = RuleRegistry()
        registry.register(DualRemovalRule())
        engine = RuleEngine(registry)

        objects = [
            _make_scanned(name="simple", source_sql="SELECT 1 FROM DUAL"),
            _make_scanned(name="complex", source_sql="BEGIN DBMS_LOB.OPEN(x); END;"),
            _make_scanned(name="plain", source_sql="SELECT * FROM employees"),
        ]

        output = engine.convert_batch("job-1", "cust-1", objects)
        assert output.job_id == "job-1"
        assert output.customer_id == "cust-1"
        assert output.rules_converted_count == 2
        assert output.forwarded_to_llm_count == 1
        assert len(output.converted) == 2
        assert len(output.forwarded) == 1
        assert output.forwarded[0].name == "complex"

    def test_batch_empty_list(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        output = engine.convert_batch("job-2", "cust-2", [])
        assert output.rules_converted_count == 0
        assert output.forwarded_to_llm_count == 0

    def test_batch_all_forwarded(self) -> None:
        registry = RuleRegistry()
        engine = RuleEngine(registry)
        objects = [
            _make_scanned(name="a", source_sql="PRAGMA AUTONOMOUS_TRANSACTION;"),
            _make_scanned(name="b", source_sql="PIPE ROW(rec);"),
        ]
        output = engine.convert_batch("job-3", "cust-3", objects)
        assert output.rules_converted_count == 0
        assert output.forwarded_to_llm_count == 2
