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

# P2O modules containing Rule subclasses, in load order.
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
    "steindb.rules.p2o_engine",
]


def _load_modules_into_registry(registry: RuleRegistry, modules: list[str]) -> RuleRegistry:
    """Import rule modules and register all Rule subclasses found within."""
    for mod_name in modules:
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


def create_default_registry() -> RuleRegistry:
    """Build a RuleRegistry with all available rules registered.

    Dynamically imports each rule module and registers all Rule subclasses
    found within. Silently skips modules that fail to import and classes
    that fail to instantiate.
    """
    return _load_modules_into_registry(RuleRegistry(), _RULE_MODULES)


def create_direction_registry(direction: str) -> RuleRegistry:
    """Build a RuleRegistry with only rules for the specified direction.

    Args:
        direction: Either "o2p" (Oracle-to-PostgreSQL) or "p2o"
            (PostgreSQL-to-Oracle).  Case-insensitive.

    Returns:
        A RuleRegistry containing only the rules for the requested direction.

    Raises:
        ValueError: If direction is not "o2p" or "p2o".
    """
    direction_lower = direction.lower()
    if direction_lower == "o2p":
        modules = _RULE_MODULES
    elif direction_lower == "p2o":
        modules = _P2O_RULE_MODULES
    else:
        msg = f"Invalid direction: {direction!r}. Must be 'o2p' or 'p2o'."
        raise ValueError(msg)

    return _load_modules_into_registry(RuleRegistry(), modules)
