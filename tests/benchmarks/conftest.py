"""Fixtures for performance benchmark tests."""

import os
import sys

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class ScannedObject:
    """Minimal representation of a scanned Oracle object for benchmarking."""

    def __init__(
        self,
        sql: str,
        object_type: str = "TABLE",
        schema: str = "HR",
        name: str = "TEST_OBJECT",
    ):
        self.sql = sql
        self.object_type = object_type
        self.schema = schema
        self.name = name
        self.dependencies: list[str] = []


def scanned_object_from(sql: str, object_type: str = "TABLE") -> ScannedObject:
    """Create a ScannedObject from raw SQL for benchmark tests."""
    return ScannedObject(sql=sql, object_type=object_type)


@pytest.fixture
def rule_engine():
    """
    Provide the Rule Engine instance for benchmarks.

    Attempts to import the real RuleEngine; falls back to a stub that
    simulates deterministic conversion latency for CI environments
    where the full engine is not installed.
    """
    try:
        from agents.rule_engine.engine import RuleEngine

        return RuleEngine()
    except ImportError:
        return _StubRuleEngine()


class _StubRuleEngine:
    """Lightweight stub that mimics RuleEngine.convert() for benchmarking."""

    # Deterministic type mappings (subset)
    _TYPE_MAP = {
        "NUMBER": "NUMERIC",
        "VARCHAR2": "VARCHAR",
        "DATE": "TIMESTAMP",
        "CLOB": "TEXT",
        "BLOB": "BYTEA",
        "SYSDATE": "CURRENT_TIMESTAMP",
    }

    def convert(self, obj: ScannedObject) -> dict:
        """Return a converted result dict with confidence 1.0."""
        sql = obj.sql
        for oracle_type, pg_type in self._TYPE_MAP.items():
            sql = sql.replace(oracle_type, pg_type)
        return {
            "original": obj.sql,
            "converted": sql,
            "confidence": 1.0,
            "method": "rule_engine",
        }


@pytest.fixture
def make_scanned_object():
    """Factory fixture to create ScannedObject instances."""
    return scanned_object_from


# Re-export for direct import in test files
__all__ = ["scanned_object_from", "ScannedObject"]
