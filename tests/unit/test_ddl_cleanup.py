"""Tests for DDL cleanup rules — Oracle physical storage clause removal."""

from __future__ import annotations

from steindb.rules.ddl_cleanup import (
    CACHERemovalRule,
    COMPRESSRemovalRule,
    LOGGINGRemovalRule,
    OracleHintRemovalRule,
    PARALLELRemovalRule,
    PCTRemovalRule,
    STORAGERemovalRule,
    TABLESPACERemovalRule,
)


class TestTABLESPACERemovalRule:
    def setup_method(self) -> None:
        self.rule = TABLESPACERemovalRule()

    def test_matches_create_table(self) -> None:
        sql = "CREATE TABLE hr.employees (id INTEGER) TABLESPACE users"
        assert self.rule.matches(sql)

    def test_matches_create_index(self) -> None:
        sql = "CREATE INDEX idx_emp_name ON hr.employees (name) TABLESPACE idx_ts"
        assert self.rule.matches(sql)

    def test_no_match_without_tablespace(self) -> None:
        sql = "CREATE TABLE hr.employees (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_create_table(self) -> None:
        sql = "CREATE TABLE hr.employees (id INTEGER, name VARCHAR(100)) TABLESPACE users"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE hr.employees (id INTEGER, name VARCHAR(100))"

    def test_apply_create_index(self) -> None:
        sql = "CREATE INDEX idx_emp_name ON hr.employees (name) TABLESPACE idx_ts"
        result = self.rule.apply(sql)
        assert result == "CREATE INDEX idx_emp_name ON hr.employees (name)"

    def test_apply_alter_table_move_tablespace(self) -> None:
        sql = "ALTER TABLE hr.employees MOVE TABLESPACE new_ts"
        result = self.rule.apply(sql)
        assert result == "-- ALTER TABLE MOVE TABLESPACE removed (no PostgreSQL equivalent)"

    def test_apply_unique_index_tablespace(self) -> None:
        sql = "CREATE UNIQUE INDEX uk_emp_email ON employees (email) TABLESPACE idx_ts"
        result = self.rule.apply(sql)
        assert result == "CREATE UNIQUE INDEX uk_emp_email ON employees (email)"


class TestSTORAGERemovalRule:
    def setup_method(self) -> None:
        self.rule = STORAGERemovalRule()

    def test_matches(self) -> None:
        sql = "CREATE TABLE orders (id INTEGER) STORAGE (INITIAL 64K NEXT 64K PCTINCREASE 0)"
        assert self.rule.matches(sql)

    def test_no_match(self) -> None:
        sql = "CREATE TABLE orders (id INTEGER)"
        assert not self.rule.matches(sql)

    def test_apply_simple(self) -> None:
        sql = "CREATE TABLE orders (id INTEGER, total NUMERIC(10,2)) STORAGE (INITIAL 64K NEXT 64K PCTINCREASE 0)"  # noqa: E501
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE orders (id INTEGER, total NUMERIC(10,2))"

    def test_apply_complex_storage(self) -> None:
        sql = (
            "CREATE TABLE t (id INTEGER)"
            " STORAGE (INITIAL 1M NEXT 1M MAXEXTENTS UNLIMITED PCTINCREASE 0 FREELISTS 4)"
        )
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE t (id INTEGER)"


class TestPCTRemovalRule:
    def setup_method(self) -> None:
        self.rule = PCTRemovalRule()

    def test_matches_pctfree(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) PCTFREE 10")

    def test_matches_pctused(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) PCTUSED 40")

    def test_matches_initrans(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) INITRANS 2")

    def test_matches_maxtrans(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) MAXTRANS 255")

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_pctfree_pctused(self) -> None:
        sql = "CREATE TABLE products (id INTEGER, name VARCHAR(200)) PCTFREE 10 PCTUSED 40"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE products (id INTEGER, name VARCHAR(200))"

    def test_apply_initrans_maxtrans(self) -> None:
        sql = "CREATE TABLE sessions (id INTEGER, token VARCHAR(256)) INITRANS 2 MAXTRANS 255"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE sessions (id INTEGER, token VARCHAR(256))"


class TestLOGGINGRemovalRule:
    def setup_method(self) -> None:
        self.rule = LOGGINGRemovalRule()

    def test_matches_logging(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) LOGGING")

    def test_matches_nologging(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) NOLOGGING")

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_logging(self) -> None:
        sql = "CREATE TABLE audit_trail (id INTEGER, action VARCHAR(50)) LOGGING"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE audit_trail (id INTEGER, action VARCHAR(50))"

    def test_apply_nologging(self) -> None:
        sql = "CREATE TABLE temp_data (id INTEGER, payload TEXT) NOLOGGING"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE temp_data (id INTEGER, payload TEXT)"


class TestPARALLELRemovalRule:
    def setup_method(self) -> None:
        self.rule = PARALLELRemovalRule()

    def test_matches_parallel(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) PARALLEL 4")

    def test_matches_noparallel(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) NOPARALLEL")

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_parallel(self) -> None:
        sql = "CREATE TABLE big_table (id INTEGER, data VARCHAR(4000)) PARALLEL 4"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE big_table (id INTEGER, data VARCHAR(4000))"

    def test_apply_noparallel(self) -> None:
        sql = "CREATE TABLE small_table (id INTEGER) NOPARALLEL"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE small_table (id INTEGER)"


class TestCOMPRESSRemovalRule:
    def setup_method(self) -> None:
        self.rule = COMPRESSRemovalRule()

    def test_matches_compress_for(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) COMPRESS FOR OLTP")

    def test_matches_nocompress(self) -> None:
        assert self.rule.matches("CREATE TABLE t (id INTEGER) NOCOMPRESS")

    def test_no_match(self) -> None:
        assert not self.rule.matches("CREATE TABLE t (id INTEGER)")

    def test_apply_compress_for(self) -> None:
        sql = "CREATE TABLE archive (id INTEGER, data TEXT) COMPRESS FOR OLTP"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE archive (id INTEGER, data TEXT)"

    def test_apply_nocompress(self) -> None:
        sql = "CREATE TABLE live_data (id INTEGER, val NUMERIC) NOCOMPRESS"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE live_data (id INTEGER, val NUMERIC)"


class TestCACHERemovalRule:
    def setup_method(self) -> None:
        self.rule = CACHERemovalRule()

    def test_matches_cache(self) -> None:
        assert self.rule.matches("CREATE TABLE ref_data (id INTEGER) CACHE")

    def test_no_match_sequence(self) -> None:
        # CACHE in sequence context should NOT be matched by this rule
        assert not self.rule.matches("CREATE SEQUENCE s CACHE 20")

    def test_no_match_alter_sequence(self) -> None:
        assert not self.rule.matches("ALTER SEQUENCE s CACHE 20")

    def test_apply_cache(self) -> None:
        sql = "CREATE TABLE ref_data (id INTEGER, label VARCHAR(50)) CACHE"
        result = self.rule.apply(sql)
        assert result == "CREATE TABLE ref_data (id INTEGER, label VARCHAR(50))"


class TestOracleHintRemovalRule:
    def setup_method(self) -> None:
        self.rule = OracleHintRemovalRule()

    def test_matches_index_hint(self) -> None:
        sql = "SELECT /*+ INDEX(t1 idx_name) */ * FROM t1"
        assert self.rule.matches(sql)

    def test_matches_full_hint(self) -> None:
        sql = "SELECT /*+ FULL(employees) */ * FROM employees"
        assert self.rule.matches(sql)

    def test_matches_parallel_hint(self) -> None:
        sql = "SELECT /*+ PARALLEL(orders, 4) */ * FROM orders"
        assert self.rule.matches(sql)

    def test_no_match_regular_comment(self) -> None:
        sql = "SELECT /* this is a comment */ * FROM t1"
        assert not self.rule.matches(sql)

    def test_no_match_no_hint(self) -> None:
        sql = "SELECT * FROM employees WHERE id = 1"
        assert not self.rule.matches(sql)

    def test_apply_index_hint(self) -> None:
        sql = "SELECT /*+ INDEX(t1 idx_name) */ * FROM t1"
        result = self.rule.apply(sql)
        assert "SteinDB: removed Oracle hint" in result
        assert "* FROM t1" in result

    def test_apply_full_hint(self) -> None:
        sql = "SELECT /*+ FULL(employees) */ employee_id FROM employees"
        result = self.rule.apply(sql)
        assert "SteinDB: removed Oracle hint" in result

    def test_apply_parallel_hint(self) -> None:
        sql = "SELECT /*+ PARALLEL(orders, 4) */ order_id FROM orders"
        result = self.rule.apply(sql)
        assert "SteinDB: removed Oracle hint" in result

    def test_apply_multiple_hints(self) -> None:
        sql = "SELECT /*+ INDEX(t1 idx1) */ a, /*+ FULL(t2) */ b FROM t1, t2"
        result = self.rule.apply(sql)
        assert result.count("SteinDB: removed Oracle hint") == 2

    def test_apply_multiline_hint(self) -> None:
        sql = "SELECT /*+ INDEX(t1 idx1)\n           PARALLEL(t1, 8) */ * FROM t1"
        result = self.rule.apply(sql)
        assert "SteinDB: removed Oracle hint" in result
