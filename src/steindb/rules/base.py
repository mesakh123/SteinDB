# src/steindb/rules/base.py
"""Base classes for Rule Engine rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum


class RuleCategory(StrEnum):
    """Categories for organizing rules by execution priority.

    Bidirectional: 22 Oracle-to-PostgreSQL (O2P) categories + 22 PostgreSQL-to-Oracle
    (P2O) mirror categories = 44 total.

    The original unprefixed names (e.g. ``DATATYPES_BASIC``) are the canonical O2P
    categories and remain fully backward-compatible.  Explicit ``O2P_`` aliases point
    to the same enum *values* for code that wants to be direction-explicit.
    """

    # =========================================================================
    # Oracle-to-PostgreSQL categories (original 22 — unchanged values)
    # =========================================================================

    # Data Type modules (3)
    DATATYPES_BASIC = "datatypes_basic"
    DATATYPES_NUMERIC = "datatypes_numeric"
    DATATYPES_TEMPORAL = "datatypes_temporal"
    # SQL Syntax modules (7)
    SYNTAX_FUNCTIONS = "syntax_functions"
    SYNTAX_DATETIME = "syntax_datetime"
    SYNTAX_JOINS = "syntax_joins"
    SYNTAX_NULL = "syntax_null"
    SYNTAX_MISC = "syntax_misc"
    SYNTAX_CONNECT_BY = "syntax_connect_by"
    SYNTAX_TYPE_CASTING = "syntax_type_casting"
    # DDL modules (4)
    DDL_TABLES = "ddl_tables"
    DDL_ALTER = "ddl_alter"
    DDL_CLEANUP = "ddl_cleanup"
    DDL_INDEXES = "ddl_indexes"
    # Object modules (8)
    SEQUENCES = "sequences"
    TRIGGERS = "triggers"
    PLSQL_BASIC = "plsql_basic"
    PLSQL_CONTROL_FLOW = "plsql_control_flow"
    PACKAGES = "packages"
    SYNONYMS = "synonyms"
    MATERIALIZED_VIEWS = "materialized_views"
    GRANTS = "grants"
    PARTITIONING = "partitioning"

    # =========================================================================
    # PostgreSQL-to-Oracle categories (22 mirror categories)
    # =========================================================================

    # Data Type modules (3)
    P2O_DATATYPES_BASIC = "p2o_datatypes_basic"
    P2O_DATATYPES_NUMERIC = "p2o_datatypes_numeric"
    P2O_DATATYPES_TEMPORAL = "p2o_datatypes_temporal"
    # SQL Syntax modules (7)
    P2O_SYNTAX_FUNCTIONS = "p2o_syntax_functions"
    P2O_SYNTAX_DATETIME = "p2o_syntax_datetime"
    P2O_SYNTAX_JOINS = "p2o_syntax_joins"
    P2O_SYNTAX_NULL = "p2o_syntax_null"
    P2O_SYNTAX_MISC = "p2o_syntax_misc"
    P2O_SYNTAX_RECURSIVE_CTE = "p2o_syntax_recursive_cte"
    P2O_SYNTAX_TYPE_CASTING = "p2o_syntax_type_casting"
    # DDL modules (4)
    P2O_DDL_TABLES = "p2o_ddl_tables"
    P2O_DDL_ALTER = "p2o_ddl_alter"
    P2O_DDL_CLEANUP = "p2o_ddl_cleanup"
    P2O_DDL_INDEXES = "p2o_ddl_indexes"
    # Object modules (8)
    P2O_SEQUENCES = "p2o_sequences"
    P2O_TRIGGERS = "p2o_triggers"
    P2O_PLPGSQL_BASIC = "p2o_plpgsql_basic"
    P2O_PLPGSQL_CONTROL_FLOW = "p2o_plpgsql_control_flow"
    P2O_SCHEMAS = "p2o_schemas"
    P2O_EXTENSIONS = "p2o_extensions"
    P2O_MATERIALIZED_VIEWS = "p2o_materialized_views"
    P2O_GRANTS = "p2o_grants"
    P2O_PARTITIONING = "p2o_partitioning"


class Rule(ABC):
    """Base class for all conversion rules.

    Each rule:
    - Has a name, category, and priority (lower = runs first)
    - Implements matches() to check if the rule applies
    - Implements apply() to transform the SQL
    - Has confidence = 1.0 (deterministic rules only; never guess)
    """

    name: str
    category: RuleCategory
    priority: int  # Lower = runs first
    description: str = ""
    confidence: float = 1.0  # Always 1.0 for deterministic rules

    @abstractmethod
    def matches(self, sql: str) -> bool:
        """Return True if this rule should be applied to the given SQL."""
        ...

    @abstractmethod
    def apply(self, sql: str) -> str:
        """Apply the transformation and return the modified SQL."""
        ...
