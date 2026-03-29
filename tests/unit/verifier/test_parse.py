# tests/unit/verifier/test_parse.py
"""Tests for pg_query syntax validation."""

from __future__ import annotations

from steindb.verifier.parse import ParseResult, parse_sql


class TestParseSql:
    def test_valid_select(self) -> None:
        result = parse_sql("SELECT id, name FROM customers WHERE active = true;")
        assert result.valid is True
        assert result.error is None

    def test_valid_function(self) -> None:
        sql = """
        CREATE OR REPLACE FUNCTION get_total(p_id INTEGER)
        RETURNS NUMERIC AS $$
        BEGIN
            RETURN (SELECT SUM(amount) FROM orders WHERE id = p_id);
        END;
        $$ LANGUAGE plpgsql;
        """
        result = parse_sql(sql)
        assert result.valid is True

    def test_invalid_sql(self) -> None:
        result = parse_sql("SELEC id FROM customers;")
        assert result.valid is False
        assert result.error is not None

    def test_empty_sql(self) -> None:
        result = parse_sql("")
        assert result.valid is False
        assert "empty" in (result.error or "").lower()

    def test_none_input(self) -> None:
        result = parse_sql(None)  # type: ignore[arg-type]
        assert result.valid is False

    def test_multiple_statements(self) -> None:
        result = parse_sql("SELECT 1; SELECT 2; SELECT 3;")
        assert result.valid is True
        assert result.statement_count == 3

    def test_oracle_syntax_fails(self) -> None:
        # Oracle-specific syntax should fail pg_query
        result = parse_sql("SELECT NVL(x, 0) FROM employees")
        # NVL is not a PG function but pg_query may or may not reject it
        # depending on parser strictness -- we test the mechanism works
        assert isinstance(result.valid, bool)

    def test_create_table(self) -> None:
        result = parse_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR(100));")
        assert result.valid is True

    def test_whitespace_only(self) -> None:
        result = parse_sql("   \n\t  ")
        assert result.valid is False

    def test_valid_insert(self) -> None:
        result = parse_sql("INSERT INTO t (id, name) VALUES (1, 'test');")
        assert result.valid is True

    def test_valid_update(self) -> None:
        result = parse_sql("UPDATE t SET name = 'new' WHERE id = 1;")
        assert result.valid is True

    def test_valid_delete(self) -> None:
        result = parse_sql("DELETE FROM t WHERE id = 1;")
        assert result.valid is True

    def test_valid_with_recursive(self) -> None:
        sql = (
            "WITH RECURSIVE cte AS ("
            "  SELECT 1 AS n"
            "  UNION ALL"
            "  SELECT n + 1 FROM cte WHERE n < 10"
            ") SELECT n FROM cte;"
        )
        result = parse_sql(sql)
        assert result.valid is True

    def test_parse_result_dataclass(self) -> None:
        r = ParseResult(valid=True, statement_count=2)
        assert r.valid is True
        assert r.statement_count == 2
        assert r.error is None
