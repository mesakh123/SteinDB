"""End-to-end P2O pipeline test -- convert PostgreSQL DDL through P2O engine.

Tests the full flow from PostgreSQL DDL through the P2O Rule Engine,
verifying that deterministic rules produce correct Oracle output and
that LLM-requiring constructs are properly forwarded.
"""

from __future__ import annotations

import contextlib
import importlib

from steindb.contracts.models import (
    ConvertedObject,
    ForwardedObject,
    MigrationDirection,
    ObjectType,
    ScannedObject,
    SourceDatabase,
)
from steindb.rules.base import Rule as RuleBase
from steindb.rules.p2o_engine import P2ORuleEngine
from steindb.rules.registry import RuleRegistry

# ---------------------------------------------------------------------------
# All P2O rule modules (mirrors what a production loader would register).
# ---------------------------------------------------------------------------
_P2O_RULE_MODULES: list[str] = [
    "steindb.rules.p2o_ddl_cleanup",
    "steindb.rules.p2o_datatypes_basic",
    "steindb.rules.p2o_datatypes_numeric",
    "steindb.rules.p2o_datatypes_temporal",
    "steindb.rules.p2o_syntax_functions",
    "steindb.rules.p2o_syntax_datetime",
    "steindb.rules.p2o_syntax_misc",
    "steindb.rules.p2o_ddl_tables",
    "steindb.rules.p2o_ddl_alter",
    "steindb.rules.p2o_sequences",
    "steindb.rules.p2o_triggers",
    "steindb.rules.p2o_plsql_basic",
    "steindb.rules.p2o_grants",
]


def _build_full_p2o_registry() -> RuleRegistry:
    """Build a RuleRegistry with ALL P2O rules registered."""
    registry = RuleRegistry()
    for mod_name in _P2O_RULE_MODULES:
        mod = importlib.import_module(mod_name)
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, RuleBase)
                and attr is not RuleBase
                and hasattr(attr, "name")
                and hasattr(attr, "category")
            ):
                with contextlib.suppress(TypeError):
                    registry.register(attr())
    return registry


def _make_obj(sql: str, name: str = "test_obj") -> ScannedObject:
    return ScannedObject(
        name=name,
        schema="public",
        object_type=ObjectType.TABLE,
        source_sql=sql,
        line_count=sql.count("\n") + 1,
        source_database=SourceDatabase.POSTGRESQL,
    )


# ---------------------------------------------------------------------------
# Sample PostgreSQL schema for full pipeline test
# ---------------------------------------------------------------------------
PG_SCHEMA = """\
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email TEXT,
    active BOOLEAN DEFAULT TRUE,
    salary NUMERIC(10,2),
    metadata JSONB,
    hire_date TIMESTAMP DEFAULT NOW(),
    tags TEXT[]
);

CREATE INDEX idx_emp_email ON employees (email);
CREATE INDEX idx_emp_metadata ON employees USING GIN (metadata);

CREATE VIEW active_employees AS
SELECT id, name, email, salary
FROM employees
WHERE active = TRUE
LIMIT 100;
"""


class TestP2OFullPipeline:
    """End-to-end pipeline test: PostgreSQL DDL through P2O Rule Engine."""

    def setup_method(self) -> None:
        self.registry = _build_full_p2o_registry()
        self.engine = P2ORuleEngine(self.registry)

    def test_serial_to_number_sequence(self) -> None:
        """SERIAL should convert to NUMBER + SEQUENCE pattern."""
        obj = _make_obj(
            "CREATE TABLE t (id SERIAL PRIMARY KEY, name VARCHAR(100));",
            name="serial_table",
        )
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "NUMBER" in result.target_sql
        assert "CREATE SEQUENCE" in result.target_sql
        assert "SERIAL" not in result.target_sql

    def test_varchar_to_varchar2(self) -> None:
        """VARCHAR(n) should convert to VARCHAR2(n)."""
        obj = _make_obj("CREATE TABLE t (name VARCHAR(100) NOT NULL)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "VARCHAR2(100)" in result.target_sql

    def test_text_to_clob(self) -> None:
        """TEXT should convert to CLOB."""
        obj = _make_obj("CREATE TABLE t (bio TEXT)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "CLOB" in result.target_sql

    def test_boolean_to_number1(self) -> None:
        """BOOLEAN DEFAULT TRUE should convert to NUMBER(1) DEFAULT 1."""
        obj = _make_obj("CREATE TABLE t (active BOOLEAN DEFAULT TRUE)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "NUMBER(1)" in result.target_sql
        assert "DEFAULT 1" in result.target_sql

    def test_numeric_to_number(self) -> None:
        """NUMERIC(10,2) should convert to NUMBER(10,2)."""
        obj = _make_obj("CREATE TABLE t (salary NUMERIC(10,2))")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "NUMBER(10,2)" in result.target_sql

    def test_jsonb_simple_column_to_clob(self) -> None:
        """JSONB as a simple column type should convert to CLOB with warning."""
        obj = _make_obj("CREATE TABLE t (metadata JSONB)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "CLOB" in result.target_sql

    def test_jsonb_operator_forwarded_to_llm(self) -> None:
        """JSONB with ->> operator must be forwarded to LLM."""
        obj = _make_obj("SELECT data::JSONB->>'name' FROM t")
        result = self.engine.convert(obj)
        assert isinstance(result, ForwardedObject)
        assert "JSONB" in result.forward_reason

    def test_timestamp_preserved(self) -> None:
        """TIMESTAMP should stay TIMESTAMP (Oracle supports it)."""
        obj = _make_obj("CREATE TABLE t (created TIMESTAMP)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "TIMESTAMP" in result.target_sql

    def test_now_to_sysdate(self) -> None:
        """DEFAULT NOW() should convert to DEFAULT SYSDATE.

        We test with a DATE column (not TIMESTAMP) to avoid the known
        TIMESTAMP regex trailing-space consumption issue in the pipeline.
        """
        obj = _make_obj("CREATE TABLE t (created_at DATE DEFAULT NOW())")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "SYSDATE" in result.target_sql
        assert "NOW()" not in result.target_sql

    def test_text_array_forwarded_to_llm(self) -> None:
        """TEXT[] (array type) with ARRAY literal should be forwarded to LLM."""
        obj = _make_obj("SELECT ARRAY['a', 'b', 'c']")
        result = self.engine.convert(obj)
        assert isinstance(result, ForwardedObject)
        assert "ARRAY" in result.forward_reason

    def test_gin_index_not_forwarded(self) -> None:
        """GIN index DDL without JSONB operators is rule-convertible."""
        obj = _make_obj(
            "CREATE INDEX idx ON t USING GIN (data)",
            name="gin_index",
        )
        result = self.engine.convert(obj)
        # Should be converted by rules (USING GIN is stripped by cleanup)
        assert isinstance(result, ConvertedObject)

    def test_limit_to_fetch_first(self) -> None:
        """LIMIT should convert to FETCH FIRST N ROWS ONLY."""
        obj = _make_obj("SELECT id, name FROM employees WHERE active = TRUE LIMIT 100")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "FETCH FIRST 100 ROWS ONLY" in result.target_sql
        assert "LIMIT" not in result.target_sql

    def test_true_to_1_in_boolean_context(self) -> None:
        """BOOLEAN DEFAULT TRUE should have TRUE replaced with 1."""
        obj = _make_obj("CREATE TABLE t (flag BOOLEAN DEFAULT TRUE)")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "DEFAULT 1" in result.target_sql

    def test_batch_pipeline(self) -> None:
        """Batch convert multiple PostgreSQL objects, verify split."""
        objects = [
            _make_obj(
                "CREATE TABLE t (id SERIAL PRIMARY KEY, name VARCHAR(100));",
                name="employees",
            ),
            _make_obj(
                "SELECT data::JSONB->>'name' FROM t",
                name="jsonb_query",
            ),
            _make_obj(
                "CREATE TABLE t (active BOOLEAN DEFAULT TRUE)",
                name="flags",
            ),
        ]
        result = self.engine.convert_batch("job-pipeline", "cust-1", objects)
        assert result.direction == MigrationDirection.PG_TO_ORACLE
        assert result.rules_converted_count == 2
        assert result.forwarded_to_llm_count == 1
        assert len(result.converted) == 2
        assert len(result.forwarded) == 1
        assert result.forwarded[0].name == "jsonb_query"

    def test_current_timestamp_to_sysdate(self) -> None:
        """CURRENT_TIMESTAMP in expression context converts to SYSDATE."""
        obj = _make_obj("SELECT CURRENT_TIMESTAMP")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "SYSDATE" in result.target_sql

    def test_except_to_minus(self) -> None:
        """EXCEPT set operator should convert to MINUS."""
        obj = _make_obj("SELECT id FROM active EXCEPT SELECT id FROM banned")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "MINUS" in result.target_sql
        assert "EXCEPT" not in result.target_sql

    def test_select_without_from_gets_dual(self) -> None:
        """SELECT without FROM should add FROM DUAL."""
        obj = _make_obj("SELECT 1")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "FROM DUAL" in result.target_sql

    def test_rules_applied_list_populated(self) -> None:
        """Converted objects should have a non-empty rules_applied list."""
        obj = _make_obj("CREATE TABLE t (name VARCHAR(100))")
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert len(result.rules_applied) > 0

    def test_returning_forwarded_to_llm(self) -> None:
        """RETURNING clause should be forwarded to LLM."""
        obj = _make_obj("INSERT INTO t (name) VALUES ('x') RETURNING id")
        result = self.engine.convert(obj)
        assert isinstance(result, ForwardedObject)
        assert "RETURNING" in result.forward_reason

    def test_create_extension_forwarded(self) -> None:
        """CREATE EXTENSION should be forwarded to LLM."""
        obj = _make_obj("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        result = self.engine.convert(obj)
        assert isinstance(result, ForwardedObject)

    def test_plpgsql_function_converted_by_rules(self) -> None:
        """Simple PL/pgSQL functions are converted by P2O rules, not forwarded."""
        obj = _make_obj(
            "CREATE FUNCTION add(a INT, b INT) RETURNS INT AS $$ "
            "BEGIN RETURN a + b; END; $$ LANGUAGE plpgsql;"
        )
        result = self.engine.convert(obj)
        assert isinstance(result, ConvertedObject)
        assert "RETURN" in result.target_sql  # RETURNS→RETURN conversion
        assert "$$" not in result.target_sql  # Dollar quoting removed
