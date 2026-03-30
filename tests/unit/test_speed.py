"""Tests for speed optimizations."""

import time


def test_category_short_circuit_skips_irrelevant():
    """Categories should be skipped when SQL has no relevant keywords."""
    from steindb.rules.loader import create_default_registry
    from steindb.rules.registry import CATEGORY_ORDER

    registry = create_default_registry()
    sql = "CREATE TABLE t (id INTEGER PRIMARY KEY)"

    start = time.perf_counter()
    for _ in range(100):
        registry.apply_all(sql, category_order=CATEGORY_ORDER)
    elapsed = time.perf_counter() - start

    assert elapsed < 2.0, f"Too slow: {elapsed:.3f}s for 100 iterations"


def test_lazy_loading_only_loads_requested_direction():
    """Lazy loader should only import O2P modules for O2P direction."""
    from steindb.rules.base import RuleCategory
    from steindb.rules.loader import create_direction_registry

    registry = create_direction_registry("o2p")
    o2p_count = len(registry.get_rules(RuleCategory.DATATYPES_BASIC))
    p2o_count = len(registry.get_rules(RuleCategory.P2O_DATATYPES_BASIC))
    assert o2p_count > 0
    assert p2o_count == 0


def test_lazy_loading_p2o_direction():
    """Lazy loader should only import P2O modules for P2O direction."""
    from steindb.rules.base import RuleCategory
    from steindb.rules.loader import create_direction_registry

    registry = create_direction_registry("p2o")
    p2o_count = len(registry.get_rules(RuleCategory.P2O_DATATYPES_BASIC))
    o2p_count = len(registry.get_rules(RuleCategory.DATATYPES_BASIC))
    assert p2o_count > 0
    assert o2p_count == 0


def test_regex_cache_reuses_compiled_patterns():
    """Pre-compiled regex cache should not recompile on each call."""
    from steindb.rules.speed import RegexCache

    cache = RegexCache()
    pattern = r"\bVARCHAR2\b"

    compiled1 = cache.get(pattern)
    compiled2 = cache.get(pattern)

    assert compiled1 is compiled2


def test_short_circuit_skips_joins_for_simple_ddl():
    """SYNTAX_JOINS category should be skipped for DDL without join syntax."""
    from steindb.rules.base import RuleCategory
    from steindb.rules.speed import should_skip_category

    sql_upper = "CREATE TABLE T (ID NUMBER PRIMARY KEY)"
    assert should_skip_category(RuleCategory.SYNTAX_JOINS, sql_upper) is True


def test_short_circuit_does_not_skip_relevant():
    """Category should NOT be skipped when relevant keywords are present."""
    from steindb.rules.base import RuleCategory
    from steindb.rules.speed import should_skip_category

    sql_upper = "SELECT * FROM A, B WHERE A.ID = B.ID(+)"
    assert should_skip_category(RuleCategory.SYNTAX_JOINS, sql_upper) is False
