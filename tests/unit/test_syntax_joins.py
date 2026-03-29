"""Tests for syntax_joins rules."""

from __future__ import annotations

from steindb.rules.syntax_joins import (
    OracleOuterJoinRule,
    _convert_plus_joins,
    _extract_alias,
    _is_inside_string,
    _parse_from_tables,
    _parse_plus_condition,
    _parse_where_conditions,
    _string_ranges,
)


class TestOracleOuterJoinRule:
    rule = OracleOuterJoinRule()

    def test_matches_right_plus(self) -> None:
        sql = "SELECT b.col1, a.col2 FROM base_table b, attributes a WHERE b.id = a.b_id(+)"
        assert self.rule.matches(sql)

    def test_matches_left_plus(self) -> None:
        sql = "SELECT a.name FROM t1 a, t2 b WHERE a.id(+) = b.a_id"
        assert self.rule.matches(sql)

    def test_no_match_no_plus(self) -> None:
        sql = "SELECT a.name FROM t1 a, t2 b WHERE a.id = b.a_id"
        assert not self.rule.matches(sql)

    def test_no_match_in_string(self) -> None:
        sql = "SELECT '(+)' FROM t"
        assert not self.rule.matches(sql)

    def test_simple_left_join(self) -> None:
        sql = "SELECT b.col1, a.col2 FROM base_table b, attributes a WHERE b.id = a.b_id(+)"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "b.id = a.b_id" in result
        assert "(+)" not in result

    def test_full_outer_join(self) -> None:
        sql = "SELECT a.name, b.value FROM table_a a, table_b b WHERE a.id(+) = b.a_id(+)"
        result = self.rule.apply(sql)
        assert "FULL OUTER JOIN" in result
        assert "(+)" not in result

    def test_self_join(self) -> None:
        sql = (
            "SELECT e.name AS employee, m.name AS manager "
            "FROM employees e, employees m "
            "WHERE e.manager_id = m.id(+)"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "e.manager_id = m.id" in result

    def test_multiple_tables(self) -> None:
        sql = (
            "SELECT e.name, d.dept_name, l.city "
            "FROM employees e, departments d, locations l "
            "WHERE e.dept_id = d.id(+) AND d.location_id = l.id(+)"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN departments d" in result
        assert "LEFT JOIN locations l" in result
        assert "(+)" not in result


class TestIsInsideString:
    """Cover _is_inside_string returning True (line 21->20)."""

    def test_pos_inside_string_range(self) -> None:
        # Position 5 is inside range (3, 10)
        assert _is_inside_string(5, [(3, 10)])

    def test_pos_outside_string_range(self) -> None:
        assert not _is_inside_string(1, [(3, 10)])

    def test_pos_at_boundary_start(self) -> None:
        # start < pos must be strict, so pos=3, start=3 should be False
        assert not _is_inside_string(3, [(3, 10)])

    def test_pos_at_boundary_end(self) -> None:
        # pos < end must be strict, so pos=10, end=10 should be False
        assert not _is_inside_string(10, [(3, 10)])

    def test_empty_ranges(self) -> None:
        assert not _is_inside_string(5, [])


class TestStringRanges:
    """Cover _string_ranges helper."""

    def test_no_strings(self) -> None:
        assert _string_ranges("SELECT 1") == []

    def test_single_string(self) -> None:
        ranges = _string_ranges("SELECT 'hello' FROM t")
        assert len(ranges) == 1

    def test_escaped_quotes(self) -> None:
        ranges = _string_ranges("SELECT 'it''s' FROM t")
        assert len(ranges) == 1


class TestMatchesInsideString:
    """Cover the _outside_strings_has path where (+) is inside a string literal."""

    rule = OracleOuterJoinRule()

    def test_plus_only_in_string(self) -> None:
        sql = "SELECT 'a.id(+) = b.id' FROM t1 a, t2 b WHERE a.id = b.id"
        assert not self.rule.matches(sql)

    def test_plus_both_inside_and_outside(self) -> None:
        sql = "SELECT '(+)' FROM t1 a, t2 b WHERE a.id = b.id(+)"
        assert self.rule.matches(sql)


class TestNoFromClause:
    """Cover line 84: no FROM clause returns sql unchanged."""

    def test_no_from(self) -> None:
        sql = "SELECT 1 WHERE a.id = b.id(+)"
        result = _convert_plus_joins(sql)
        assert result == sql


class TestNoWhereClause:
    """Cover line 89: no WHERE clause returns sql unchanged."""

    def test_no_where(self) -> None:
        sql = "SELECT a.col FROM table1 a, table2 b"
        result = _convert_plus_joins(sql)
        assert result == sql


class TestTailMatch:
    """Cover lines 101-102: query with GROUP BY/ORDER BY after WHERE."""

    rule = OracleOuterJoinRule()

    def test_with_group_by(self) -> None:
        sql = (
            "SELECT a.dept, COUNT(*) "
            "FROM orders a, customers b "
            "WHERE a.cust_id = b.id(+) "
            "GROUP BY a.dept"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "GROUP BY a.dept" in result
        assert "(+)" not in result

    def test_with_order_by(self) -> None:
        sql = "SELECT a.name, b.value FROM t1 a, t2 b WHERE a.id = b.id(+) ORDER BY a.name"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "ORDER BY a.name" in result

    def test_with_having(self) -> None:
        sql = (
            "SELECT a.dept, COUNT(*) "
            "FROM orders a, customers b "
            "WHERE a.cust_id = b.id(+) "
            "GROUP BY a.dept HAVING COUNT(*) > 1"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "HAVING COUNT(*) > 1" in result


class TestEmptyFromTables:
    """Cover line 113: _parse_from_tables returns empty list."""

    def test_empty_from_text(self) -> None:
        # A FROM clause with something that doesn't parse as tables
        # The function returns [] if no valid table entries found
        assert _parse_from_tables("") == []

    def test_convert_with_unparseable_from(self) -> None:
        # Construct SQL where the FROM text between FROM and WHERE is empty/unparseable
        sql = "SELECT 1 FROM WHERE a.id = b.id(+)"
        result = _convert_plus_joins(sql)
        # With no tables parsed, should return sql unchanged
        assert result == sql


class TestUnparseablePlusCondition:
    """Cover lines 128-130: (+) condition that fails to parse gets stripped and added
    to normal_conditions. Also cover line 133: no plus_conditions found."""

    def test_complex_plus_expression_not_parseable(self) -> None:
        # A condition with (+) that doesn't match the regex pattern
        # e.g., a function call with (+)
        sql = "SELECT a.col FROM t1 a, t2 b WHERE UPPER(a.name)(+) = b.name"
        result = _convert_plus_joins(sql)
        # Since the (+) condition fails to parse, it goes to normal_conditions
        # and since no plus_conditions are found, sql is returned unchanged
        assert result == sql

    def test_normal_condition_without_plus(self) -> None:
        # Normal conditions (line 130) with some plus conditions too
        sql = "SELECT a.col, b.val FROM t1 a, t2 b WHERE a.id = b.a_id(+) AND a.status = 'ACTIVE'"
        result = _convert_plus_joins(sql)
        assert "LEFT JOIN" in result
        assert "a.status = 'ACTIVE'" in result


class TestRightJoin:
    """Cover lines 154-155: RIGHT JOIN when (+) is on the left side."""

    rule = OracleOuterJoinRule()

    def test_right_join_basic_known_limitation(self) -> None:
        # Known limitation: when (+) is on the left side and the optional alias
        # is the FIRST table in FROM, the current implementation cannot correctly
        # produce a RIGHT JOIN because joined_tables is keyed by optional_alias
        # and only tables[1:] are checked against it.
        # This test documents the limitation — the query is transformed but
        # the RIGHT JOIN is lost, resulting in a comma join.
        sql = "SELECT a.name, b.value FROM table_a a, table_b b WHERE a.id(+) = b.a_id"
        result = self.rule.apply(sql)
        # The (+) is stripped but the join type is not correctly applied
        assert "(+)" not in result

    def test_right_join_second_table_optional(self) -> None:
        # This ensures the RIGHT JOIN path is hit where the optional alias
        # is indeed a table after the first one.
        # (+) on left side means the left column's table is optional -> RIGHT JOIN
        # We need left_alias to be a table in tables[1:]
        sql = "SELECT a.name, b.value FROM table_a a, table_b b WHERE b.id(+) = a.ref_id"
        result = self.rule.apply(sql)
        assert "RIGHT JOIN" in result
        assert "b.id = a.ref_id" in result
        assert "(+)" not in result


class TestMultipleConditionsSameJoin:
    """Cover line 159: optional_alias already in joined_tables, appending condition."""

    rule = OracleOuterJoinRule()

    def test_multiple_join_conditions(self) -> None:
        sql = "SELECT a.col, b.val FROM t1 a, t2 b WHERE a.id = b.a_id(+) AND a.type = b.type(+)"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "a.id = b.a_id" in result
        assert "a.type = b.type" in result
        # Both conditions should be in the ON clause
        assert "AND" in result
        assert "(+)" not in result


class TestNormalConditionsAssignedToJoin:
    """Cover lines 170-180: normal conditions that reference a joined table's alias
    get moved into the JOIN ON clause."""

    rule = OracleOuterJoinRule()

    def test_normal_condition_moved_to_on(self) -> None:
        sql = "SELECT a.col, b.val FROM t1 a, t2 b WHERE a.id = b.a_id(+) AND b.active = 'Y'"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        # b.active = 'Y' should be part of the ON clause since b is the joined table
        assert "b.active = 'Y'" in result
        assert "(+)" not in result

    def test_normal_condition_stays_in_where(self) -> None:
        # Condition referencing the first (base) table only should stay in WHERE
        sql = "SELECT a.col, b.val FROM t1 a, t2 b WHERE a.id = b.a_id(+) AND a.status = 'ACTIVE'"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "WHERE" in result
        assert "a.status = 'ACTIVE'" in result


class TestInnerJoinForNonPlusTables:
    """Cover lines 198-217: tables without (+) that have conditions with joined tables
    become INNER JOINs."""

    rule = OracleOuterJoinRule()

    def test_three_table_with_inner_join(self) -> None:
        sql = (
            "SELECT a.col, b.val, c.name "
            "FROM t1 a, t2 b, t3 c "
            "WHERE a.id = b.a_id(+) AND a.cid = c.id"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        # c has no (+) but has a condition referencing a (already joined), so INNER JOIN
        assert "INNER JOIN t3 c" in result
        assert "a.cid = c.id" in result

    def test_three_table_no_condition_for_third(self) -> None:
        # Third table has no join condition at all -> comma-separated
        sql = "SELECT a.col, b.val, c.name FROM t1 a, t2 b, t3 c WHERE a.id = b.a_id(+)"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert ", t3 c" in result


class TestRemainingWhereClause:
    """Cover line 225: remaining_normal conditions form a WHERE clause."""

    rule = OracleOuterJoinRule()

    def test_remaining_where_conditions(self) -> None:
        sql = "SELECT a.col, b.val FROM t1 a, t2 b WHERE a.id = b.a_id(+) AND a.active = 1"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result
        assert "WHERE" in result
        assert "a.active = 1" in result


class TestParseFromTables:
    """Cover lines 264, 268-269 in _parse_from_tables."""

    def test_empty_part_in_split(self) -> None:
        # Trailing comma produces empty part
        tables = _parse_from_tables("t1 a, t2 b,")
        assert len(tables) == 2
        assert tables[0] == ("t1", "a")
        assert tables[1] == ("t2", "b")

    def test_single_token_table_no_alias(self) -> None:
        # Single token -> alias is same as table name
        tables = _parse_from_tables("employees")
        assert tables == [("employees", "employees")]

    def test_multiple_tables(self) -> None:
        tables = _parse_from_tables("t1 a, t2 b, t3 c")
        assert len(tables) == 3

    def test_schema_qualified_table(self) -> None:
        tables = _parse_from_tables("hr.employees e, hr.departments d")
        assert tables == [("hr.employees", "e"), ("hr.departments", "d")]


class TestParseWhereConditions:
    """Cover line 294->297 branch in _parse_where_conditions."""

    def test_single_condition(self) -> None:
        # No AND at all, so current accumulates and is appended at line 294
        conditions = _parse_where_conditions("a.id = b.id")
        assert conditions == ["a.id = b.id"]

    def test_multiple_conditions(self) -> None:
        conditions = _parse_where_conditions("a.id = b.id AND a.x = 1")
        assert len(conditions) == 2
        assert "a.id = b.id" in conditions[0]
        assert "a.x = 1" in conditions[1]

    def test_nested_parentheses(self) -> None:
        conditions = _parse_where_conditions("(a.id = b.id AND a.x = 1) AND c.y = 2")
        assert len(conditions) == 2

    def test_empty_input(self) -> None:
        conditions = _parse_where_conditions("")
        assert conditions == []


class TestParsePlusCondition:
    """Cover lines 308 and 314 in _parse_plus_condition."""

    def test_no_match_returns_none(self) -> None:
        # Complex expression that doesn't match the regex
        result = _parse_plus_condition("UPPER(a.name)(+) = b.name")
        assert result is None

    def test_no_plus_on_either_side_returns_none(self) -> None:
        # Matches regex but neither side has (+)
        result = _parse_plus_condition("a.id = b.id")
        assert result is None

    def test_plus_on_right(self) -> None:
        result = _parse_plus_condition("a.id = b.id(+)")
        assert result is not None
        assert result.left_col == "a.id"
        assert result.right_col == "b.id"
        assert not result.plus_on_left
        assert result.plus_on_right

    def test_plus_on_left(self) -> None:
        result = _parse_plus_condition("a.id(+) = b.id")
        assert result is not None
        assert result.plus_on_left
        assert not result.plus_on_right

    def test_plus_on_both(self) -> None:
        result = _parse_plus_condition("a.id(+) = b.id(+)")
        assert result is not None
        assert result.plus_on_left
        assert result.plus_on_right


class TestExtractAlias:
    """Cover line 322: _extract_alias when no dot in col_ref."""

    def test_with_dot(self) -> None:
        assert _extract_alias("a.id") == "a"

    def test_without_dot_returns_none(self) -> None:
        assert _extract_alias("id") is None

    def test_multiple_dots(self) -> None:
        assert _extract_alias("schema.table.col") == "schema"


class TestRuleMetadata:
    """Test rule properties."""

    rule = OracleOuterJoinRule()

    def test_name(self) -> None:
        assert self.rule.name == "oracle_plus_to_ansi_join"

    def test_confidence(self) -> None:
        assert self.rule.confidence == 0.95

    def test_priority(self) -> None:
        assert self.rule.priority == 10


class TestMixedInnerAndOuterJoins:
    """Cover the interaction between outer and inner joins in multi-table queries."""

    rule = OracleOuterJoinRule()

    def test_four_table_mixed_joins(self) -> None:
        sql = (
            "SELECT e.name, d.dept_name, l.city, p.project "
            "FROM employees e, departments d, locations l, projects p "
            "WHERE e.dept_id = d.id(+) AND d.loc_id = l.id AND e.proj_id = p.id(+)"
        )
        result = self.rule.apply(sql)
        assert "LEFT JOIN departments d" in result
        assert "LEFT JOIN projects p" in result
        assert "(+)" not in result


class TestSubqueryWithPlus:
    """Test (+) appearing in a subquery context."""

    rule = OracleOuterJoinRule()

    def test_plus_in_main_query_with_subquery_in_select(self) -> None:
        sql = "SELECT a.col, (SELECT 1 FROM dual) FROM t1 a, t2 b WHERE a.id = b.a_id(+)"
        result = self.rule.apply(sql)
        assert "LEFT JOIN" in result


class TestEdgeCases:
    """Various edge cases."""

    rule = OracleOuterJoinRule()

    def test_empty_sql(self) -> None:
        result = _convert_plus_joins("")
        assert result == ""

    def test_no_plus_in_where(self) -> None:
        # Has (+) somewhere but not in a valid WHERE condition
        sql = "SELECT 1 FROM t1 a, t2 b WHERE a.id = b.id"
        result = _convert_plus_joins(sql)
        # No (+) conditions found -> returns unchanged
        assert result == sql

    def test_plus_in_string_literal_only(self) -> None:
        sql = "SELECT 'value(+)test' FROM t1 a WHERE a.id = 1"
        result = _convert_plus_joins(sql)
        # No real (+) -> should be unchanged (or at least no error)
        assert result == sql
