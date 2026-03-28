"""Tests for P2O Rule Engine -- forward detection and batch conversion."""

from __future__ import annotations

from steindb.contracts.models import (
    ConvertedObject,
    ForwardedObject,
    MigrationDirection,
    ObjectType,
    ScannedObject,
    SourceDatabase,
)
from steindb.rules.p2o_ddl_cleanup import P2O_DDL_CLEANUP_RULES
from steindb.rules.p2o_ddl_tables import P2O_DDL_TABLES_RULES
from steindb.rules.p2o_engine import P2ORuleEngine
from steindb.rules.p2o_grants import P2O_GRANTS_RULES
from steindb.rules.p2o_sequences import P2O_SEQUENCES_RULES
from steindb.rules.registry import RuleRegistry


def _make_obj(sql: str, name: str = "test_obj") -> ScannedObject:
    return ScannedObject(
        name=name,
        schema="public",
        object_type=ObjectType.TABLE,
        source_sql=sql,
        line_count=sql.count("\n") + 1,
        source_database=SourceDatabase.POSTGRESQL,
    )


def _build_registry() -> RuleRegistry:
    registry = RuleRegistry()
    for rule_list in [
        P2O_DDL_CLEANUP_RULES,
        P2O_DDL_TABLES_RULES,
        P2O_SEQUENCES_RULES,
        P2O_GRANTS_RULES,
    ]:
        for rule_cls in rule_list:
            registry.register(rule_cls())
    return registry


class TestP2OLLMForwardPatterns:
    """Test that LLM forward patterns correctly identify PG-specific constructs."""

    def setup_method(self) -> None:
        self.engine = P2ORuleEngine(_build_registry())

    def test_forward_jsonb_arrow(self) -> None:
        obj = _make_obj("SELECT data::JSONB->>'name' FROM t")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward
        assert "JSONB" in reason

    def test_forward_jsonb_containment(self) -> None:
        obj = _make_obj("SELECT * FROM t WHERE data::JSONB @> '{\"key\": 1}'")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_array_literal(self) -> None:
        obj = _make_obj("SELECT ARRAY[1, 2, 3]")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward
        assert "ARRAY" in reason

    def test_forward_unnest(self) -> None:
        obj = _make_obj("SELECT UNNEST(tags) FROM t")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_lateral(self) -> None:
        obj = _make_obj("SELECT * FROM t LEFT JOIN LATERAL (SELECT 1) s ON true")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward
        assert "LATERAL" in reason

    def test_forward_inherits(self) -> None:
        obj = _make_obj("CREATE TABLE child (extra TEXT) INHERITS (parent)")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_listen_notify(self) -> None:
        obj = _make_obj("LISTEN my_channel")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_distinct_on(self) -> None:
        obj = _make_obj("SELECT DISTINCT ON (dept) name FROM employees")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_create_extension(self) -> None:
        obj = _make_obj("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward
        assert "EXTENSION" in reason

    def test_forward_filter_where(self) -> None:
        obj = _make_obj("SELECT COUNT(*) FILTER (WHERE status = 'A') FROM t")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_forward_tablesample(self) -> None:
        obj = _make_obj("SELECT * FROM t TABLESAMPLE BERNOULLI (10)")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert should_forward

    def test_on_conflict_handled_by_rules(self) -> None:
        """Basic ON CONFLICT is handled by p2o_syntax_misc rules, not forwarded."""
        obj = _make_obj(
            "INSERT INTO t (id, val) VALUES (1, 'a') ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val"  # noqa: E501
        )
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert not should_forward

    def test_no_forward_simple_ddl(self) -> None:
        obj = _make_obj("CREATE TABLE t (id INTEGER, name VARCHAR(100))")
        should_forward, reason = self.engine.should_forward_to_llm(obj)
        assert not should_forward
        assert reason == ""


class TestP2ORuleEngineConvert:
    def setup_method(self) -> None:
        self.engine = P2ORuleEngine(_build_registry())

    def test_convert_simple_table(self) -> None:
        obj = _make_obj(
            "CREATE TABLE t (id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "DEFAULT SYSDATE" in result.target_sql
        assert result.confidence == 1.0
        assert result.method == "rules"

    def test_convert_forwards_jsonb(self) -> None:
        obj = _make_obj("SELECT data::JSONB->>'name' FROM t")
        result = self.engine.convert(obj)
        assert isinstance(result, ForwardedObject)
        assert "JSONB" in result.forward_reason

    def test_convert_temp_table(self) -> None:
        obj = _make_obj("CREATE TEMP TABLE tmp (id INTEGER)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "GLOBAL TEMPORARY TABLE" in result.target_sql

    def test_convert_grant(self) -> None:
        obj = _make_obj("GRANT EXECUTE ON FUNCTION public.my_func TO app_user")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "FUNCTION" not in result.target_sql
        assert "GRANT EXECUTE ON public.my_func" in result.target_sql


class TestP2ORuleEngineBatch:
    def setup_method(self) -> None:
        self.engine = P2ORuleEngine(_build_registry())

    def test_convert_batch(self) -> None:
        objects = [
            _make_obj("CREATE TABLE t (id INTEGER)", name="simple_table"),
            _make_obj("SELECT ARRAY[1, 2, 3]", name="array_expr"),
            _make_obj("GRANT SELECT ON t TO app_user", name="grant_stmt"),
        ]
        result = self.engine.convert_batch("job-1", "cust-1", objects)
        assert result.direction == MigrationDirection.PG_TO_ORACLE
        assert result.rules_converted_count == 2
        assert result.forwarded_to_llm_count == 1
        assert len(result.converted) == 2
        assert len(result.forwarded) == 1
        assert result.forwarded[0].name == "array_expr"

    def test_convert_batch_all_convertible(self) -> None:
        objects = [
            _make_obj("CREATE TABLE t (id INTEGER)", name="t1"),
            _make_obj("GRANT SELECT ON t TO u", name="g1"),
        ]
        result = self.engine.convert_batch("job-2", "cust-2", objects)
        assert result.rules_converted_count == 2
        assert result.forwarded_to_llm_count == 0

    def test_convert_batch_empty(self) -> None:
        result = self.engine.convert_batch("job-3", "cust-3", [])
        assert result.rules_converted_count == 0
        assert result.forwarded_to_llm_count == 0
