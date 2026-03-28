# src/steindb/rules/registry.py
"""Rule Registry: stores, organizes, and applies conversion rules."""

from __future__ import annotations

from collections import defaultdict

from steindb.rules.base import Rule, RuleCategory

__all__ = [
    "CATEGORY_ORDER",
    "O2P_CATEGORY_ORDER",
    "P2O_CATEGORY_ORDER",
    "RuleCategory",
    "RuleRegistry",
]

# ---------------------------------------------------------------------------
# Oracle-to-PostgreSQL (O2P) canonical execution order — 22 categories.
# DDL_CLEANUP runs first (strip Oracle-specific clauses), then data types,
# then syntax transforms, then DDL structure, then object-level conversions.
# ---------------------------------------------------------------------------
CATEGORY_ORDER: list[RuleCategory] = [
    # Phase 0: Strip Oracle storage/physical clauses
    RuleCategory.DDL_CLEANUP,
    # Phase 1: Data types
    RuleCategory.DATATYPES_BASIC,
    RuleCategory.DATATYPES_NUMERIC,
    RuleCategory.DATATYPES_TEMPORAL,
    # Phase 2: SQL syntax transforms
    RuleCategory.SYNTAX_FUNCTIONS,
    RuleCategory.SYNTAX_DATETIME,
    RuleCategory.SYNTAX_JOINS,
    RuleCategory.SYNTAX_NULL,
    RuleCategory.SYNTAX_MISC,
    RuleCategory.SYNTAX_CONNECT_BY,
    RuleCategory.SYNTAX_TYPE_CASTING,
    # Phase 3: DDL structure
    RuleCategory.DDL_TABLES,
    RuleCategory.DDL_ALTER,
    RuleCategory.DDL_INDEXES,
    # Phase 4: Object-level conversions
    RuleCategory.SEQUENCES,
    RuleCategory.TRIGGERS,
    RuleCategory.PLSQL_BASIC,
    RuleCategory.PLSQL_CONTROL_FLOW,
    RuleCategory.PACKAGES,
    RuleCategory.SYNONYMS,
    RuleCategory.MATERIALIZED_VIEWS,
    RuleCategory.GRANTS,
    RuleCategory.PARTITIONING,
]

# Convenience alias for direction-explicit code.
O2P_CATEGORY_ORDER = CATEGORY_ORDER

# ---------------------------------------------------------------------------
# PostgreSQL-to-Oracle (P2O) canonical execution order — 22 categories.
# Mirror of O2P: cleanup PG-specific clauses first, then data types,
# then syntax transforms, then DDL structure, then object-level conversions.
# ---------------------------------------------------------------------------
P2O_CATEGORY_ORDER: list[RuleCategory] = [
    # Phase 0: Strip PostgreSQL-specific clauses
    RuleCategory.P2O_DDL_CLEANUP,
    # Phase 1: Data types
    RuleCategory.P2O_DATATYPES_BASIC,
    RuleCategory.P2O_DATATYPES_NUMERIC,
    RuleCategory.P2O_DATATYPES_TEMPORAL,
    # Phase 2: SQL syntax transforms
    RuleCategory.P2O_SYNTAX_FUNCTIONS,
    RuleCategory.P2O_SYNTAX_DATETIME,
    RuleCategory.P2O_SYNTAX_JOINS,
    RuleCategory.P2O_SYNTAX_NULL,
    RuleCategory.P2O_SYNTAX_MISC,
    RuleCategory.P2O_SYNTAX_RECURSIVE_CTE,
    RuleCategory.P2O_SYNTAX_TYPE_CASTING,
    # Phase 3: DDL structure
    RuleCategory.P2O_DDL_TABLES,
    RuleCategory.P2O_DDL_ALTER,
    RuleCategory.P2O_DDL_INDEXES,
    # Phase 4: Object-level conversions
    RuleCategory.P2O_SEQUENCES,
    RuleCategory.P2O_TRIGGERS,
    RuleCategory.P2O_PLPGSQL_BASIC,
    RuleCategory.P2O_PLPGSQL_CONTROL_FLOW,
    RuleCategory.P2O_SCHEMAS,
    RuleCategory.P2O_EXTENSIONS,
    RuleCategory.P2O_MATERIALIZED_VIEWS,
    RuleCategory.P2O_GRANTS,
    RuleCategory.P2O_PARTITIONING,
]


class RuleRegistry:
    """Registry that stores rules grouped by category and applies them in order."""

    def __init__(self) -> None:
        self._rules: dict[RuleCategory, list[Rule]] = defaultdict(list)

    def register(self, rule: Rule) -> None:
        """Register a rule in its category bucket."""
        self._rules[rule.category].append(rule)
        # Keep sorted by priority (lower = runs first)
        self._rules[rule.category].sort(key=lambda r: r.priority)

    def get_rules(self, category: RuleCategory) -> list[Rule]:
        """Return rules for a category, sorted by priority (lower first)."""
        return list(self._rules.get(category, []))

    def apply_category(self, category: RuleCategory, sql: str) -> tuple[str, list[str]]:
        """Apply all matching rules in a category to the SQL string.

        Returns:
            A tuple of (transformed_sql, list_of_applied_rule_names).
        """
        applied: list[str] = []
        result = sql
        for rule in self.get_rules(category):
            if rule.matches(result):
                result = rule.apply(result)
                applied.append(rule.name)
        return result, applied

    def apply_all(
        self,
        sql: str,
        category_order: list[RuleCategory] | None = None,
    ) -> tuple[str, list[str]]:
        """Apply ALL categories in canonical order.

        Args:
            sql: The SQL string to transform.
            category_order: Optional explicit category order.  Defaults to
                :data:`CATEGORY_ORDER` (O2P).  Pass :data:`P2O_CATEGORY_ORDER`
                for PostgreSQL-to-Oracle conversions.

        Returns:
            A tuple of (transformed_sql, all_applied_rule_names).
        """
        if category_order is None:
            category_order = CATEGORY_ORDER
        all_applied: list[str] = []
        result = sql
        for category in category_order:
            result, applied = self.apply_category(category, result)
            all_applied.extend(applied)
        return result, all_applied

    @property
    def rule_count(self) -> int:
        """Total number of registered rules across all categories."""
        return sum(len(rules) for rules in self._rules.values())
