# tests/unit/test_registry.py
"""Tests for the rule registry and base rule classes."""

from __future__ import annotations

import pytest
from steindb.rules.base import Rule, RuleCategory
from steindb.rules.registry import CATEGORY_ORDER, P2O_CATEGORY_ORDER, RuleRegistry


class FakeRule(Rule):
    """Test rule that uppercases SQL."""

    name = "fake_upper"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 10

    def apply(self, sql: str) -> str:
        return sql.upper()

    def matches(self, sql: str) -> bool:
        return True


class FakeLowerRule(Rule):
    """Test rule that lowercases SQL."""

    name = "fake_lower"
    category = RuleCategory.SYNTAX_FUNCTIONS
    priority = 20

    def apply(self, sql: str) -> str:
        return sql.lower()

    def matches(self, sql: str) -> bool:
        return True


class TestRuleBase:
    def test_rule_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Rule()  # type: ignore[abstract]

    def test_rule_subclass_has_defaults(self) -> None:
        rule = FakeRule()
        assert rule.confidence == 1.0
        assert rule.description == ""

    def test_rule_category_values(self) -> None:
        assert RuleCategory.DATATYPES_BASIC.value == "datatypes_basic"
        assert RuleCategory.PARTITIONING.value == "partitioning"

    def test_all_categories_in_order(self) -> None:
        """Every RuleCategory must appear exactly once across the two order lists.

        O2P categories (no ``p2o_`` prefix) go in CATEGORY_ORDER.
        P2O categories (``p2o_`` prefix) go in P2O_CATEGORY_ORDER.
        Together they must cover every member of RuleCategory.
        """
        o2p_values = {c.value for c in CATEGORY_ORDER}
        p2o_values = {c.value for c in P2O_CATEGORY_ORDER}
        all_order_values = o2p_values | p2o_values
        category_values = {c.value for c in RuleCategory}

        assert all_order_values == category_values, (
            f"Missing from order lists: {category_values - all_order_values}, "
            f"Extra in order lists: {all_order_values - category_values}"
        )
        assert len(CATEGORY_ORDER) == len(set(CATEGORY_ORDER)), "Duplicates in CATEGORY_ORDER"
        assert len(P2O_CATEGORY_ORDER) == len(
            set(P2O_CATEGORY_ORDER)
        ), "Duplicates in P2O_CATEGORY_ORDER"
        # No overlap between O2P and P2O order lists
        assert o2p_values.isdisjoint(
            p2o_values
        ), f"Overlap between O2P and P2O: {o2p_values & p2o_values}"


class TestRuleRegistry:
    def test_register_and_retrieve(self) -> None:
        registry = RuleRegistry()
        rule = FakeRule()
        registry.register(rule)
        assert len(registry.get_rules(RuleCategory.SYNTAX_FUNCTIONS)) == 1

    def test_rules_sorted_by_priority(self) -> None:
        registry = RuleRegistry()
        registry.register(FakeLowerRule())  # priority 20
        registry.register(FakeRule())  # priority 10
        rules = registry.get_rules(RuleCategory.SYNTAX_FUNCTIONS)
        assert rules[0].name == "fake_upper"
        assert rules[1].name == "fake_lower"

    def test_apply_rules_in_order(self) -> None:
        registry = RuleRegistry()
        registry.register(FakeRule())  # upper first (priority 10)
        registry.register(FakeLowerRule())  # lower second (priority 20)
        result, applied = registry.apply_category(RuleCategory.SYNTAX_FUNCTIONS, "NVL(Hello)")
        assert result == "nvl(hello)"
        assert len(applied) == 2

    def test_empty_category_returns_empty(self) -> None:
        registry = RuleRegistry()
        assert registry.get_rules(RuleCategory.DDL_TABLES) == []

    def test_apply_empty_category_returns_unchanged(self) -> None:
        registry = RuleRegistry()
        result, applied = registry.apply_category(RuleCategory.DDL_TABLES, "SELECT 1")
        assert result == "SELECT 1"
        assert applied == []

    def test_only_matching_rules_applied(self) -> None:
        class NoMatchRule(Rule):
            name = "no_match"
            category = RuleCategory.SYNTAX_FUNCTIONS
            priority = 5

            def apply(self, sql: str) -> str:
                return "SHOULD NOT APPEAR"

            def matches(self, sql: str) -> bool:
                return False

        registry = RuleRegistry()
        registry.register(NoMatchRule())
        result, applied = registry.apply_category(RuleCategory.SYNTAX_FUNCTIONS, "SELECT 1")
        assert result == "SELECT 1"
        assert applied == []

    def test_apply_all_crosses_categories(self) -> None:
        """Rules in different categories are applied in CATEGORY_ORDER."""

        class CleanupRule(Rule):
            name = "cleanup_strip"
            category = RuleCategory.DDL_CLEANUP
            priority = 1

            def matches(self, sql: str) -> bool:
                return "TABLESPACE" in sql.upper()

            def apply(self, sql: str) -> str:
                return sql.replace("TABLESPACE users", "").strip()

        class TypeRule(Rule):
            name = "varchar2_to_varchar"
            category = RuleCategory.DATATYPES_BASIC
            priority = 1

            def matches(self, sql: str) -> bool:
                return "VARCHAR2" in sql.upper()

            def apply(self, sql: str) -> str:
                return sql.replace("VARCHAR2", "VARCHAR")

        registry = RuleRegistry()
        registry.register(TypeRule())
        registry.register(CleanupRule())

        result, applied = registry.apply_all("CREATE TABLE t (name VARCHAR2(100)) TABLESPACE users")
        assert "TABLESPACE" not in result
        assert "VARCHAR2" not in result
        assert "VARCHAR" in result
        # Cleanup should run before datatypes per CATEGORY_ORDER
        assert applied.index("cleanup_strip") < applied.index("varchar2_to_varchar")

    def test_rule_count(self) -> None:
        registry = RuleRegistry()
        assert registry.rule_count == 0
        registry.register(FakeRule())
        registry.register(FakeLowerRule())
        assert registry.rule_count == 2
