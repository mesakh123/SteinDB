# src/steindb/rules/loader.py
"""Rule loader: builds a RuleRegistry with all available rules registered.

Extracted from CLI convert command so it can be reused by tests, accuracy
measurement, and other consumers.
"""

from __future__ import annotations

import contextlib
import importlib

from steindb.rules.base import Rule as RuleBase
from steindb.rules.registry import RuleRegistry

# Modules containing Rule subclasses, in load order.
_RULE_MODULES: list[str] = [
    "steindb.rules.ddl_cleanup",
    "steindb.rules.datatypes_basic",
    "steindb.rules.datatypes_numeric",
    "steindb.rules.datatypes_temporal",
    "steindb.rules.syntax_functions",
    "steindb.rules.syntax_datetime",
    "steindb.rules.syntax_joins",
    "steindb.rules.syntax_null",
    "steindb.rules.syntax_misc",
    "steindb.rules.ddl_tables",
    "steindb.rules.ddl_alter",
    "steindb.rules.ddl_indexes",
    "steindb.rules.sequences",
    "steindb.rules.triggers",
    "steindb.rules.plsql_basic",
    "steindb.rules.plsql_control_flow",
    "steindb.rules.packages",
    "steindb.rules.synonyms",
    "steindb.rules.materialized_views",
    "steindb.rules.grants",
    "steindb.rules.partitioning",
]


def create_default_registry() -> RuleRegistry:
    """Build a RuleRegistry with all available rules registered.

    Dynamically imports each rule module and registers all Rule subclasses
    found within. Silently skips modules that fail to import and classes
    that fail to instantiate.
    """
    registry = RuleRegistry()

    for mod_name in _RULE_MODULES:
        try:
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
        except ImportError:
            pass

    return registry
