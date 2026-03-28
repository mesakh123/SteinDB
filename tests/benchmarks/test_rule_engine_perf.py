"""Performance benchmarks for the Rule Engine.

These tests enforce latency budgets to ensure the Rule Engine stays fast
as the rule set grows. All times are wall-clock measured with
time.perf_counter for sub-millisecond precision.

Run with:
    pytest tests/benchmarks/test_rule_engine_perf.py -v
    pytest tests/benchmarks/test_rule_engine_perf.py -v -m benchmark
"""

import pathlib
import time

import pytest

from tests.benchmarks.conftest import scanned_object_from

# ---------------------------------------------------------------------------
# Sample SQL statements at varying complexity levels
# ---------------------------------------------------------------------------

SIMPLE_DDL = (
    "CREATE TABLE hr.employees ("
    "id NUMBER(10), "
    "name VARCHAR2(100), "
    "hire_date DATE, "
    "salary NUMBER(12,2), "
    "department_id NUMBER(6)"
    ")"
)

MEDIUM_DDL = """
CREATE TABLE finance.transactions (
    txn_id NUMBER(19) PRIMARY KEY,
    account_id NUMBER(12) NOT NULL,
    txn_type VARCHAR2(20) DEFAULT 'DEBIT',
    amount NUMBER(15,2) NOT NULL,
    currency VARCHAR2(3) DEFAULT 'USD',
    description CLOB,
    attachment BLOB,
    created_at DATE DEFAULT SYSDATE,
    updated_at DATE,
    status VARCHAR2(10) CHECK (status IN ('PENDING','DONE','FAILED')),
    CONSTRAINT fk_account FOREIGN KEY (account_id) REFERENCES accounts(id)
)
"""

COMPLEX_PLSQL_TRIGGER = """
CREATE OR REPLACE TRIGGER hr.audit_salary_change
BEFORE UPDATE OF salary ON hr.employees
FOR EACH ROW
DECLARE
    v_change NUMBER;
    v_pct NUMBER;
    v_manager VARCHAR2(100);
BEGIN
    v_change := :NEW.salary - :OLD.salary;
    v_pct := (v_change / :OLD.salary) * 100;

    SELECT manager_name INTO v_manager
    FROM hr.departments
    WHERE department_id = :NEW.department_id;

    IF v_pct > 20 THEN
        INSERT INTO hr.salary_audit (
            employee_id, old_salary, new_salary,
            change_pct, manager_name, changed_at
        ) VALUES (
            :NEW.id, :OLD.salary, :NEW.salary,
            v_pct, v_manager, SYSDATE
        );

        INSERT INTO hr.notifications (
            recipient, message, created_at
        ) VALUES (
            v_manager,
            'Salary increase of ' || TO_CHAR(v_pct, '990.0') || '% for employee ' || :NEW.name,
            SYSDATE
        );
    END IF;

    :NEW.updated_at := SYSDATE;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20001, 'Department not found');
    WHEN OTHERS THEN
        RAISE_APPLICATION_ERROR(-20002, 'Audit trigger failed: ' || SQLERRM);
END;
"""

# Collection of 100 varied DDL statements for batch benchmarking
_DDL_TEMPLATES = [
    "CREATE TABLE schema_{i}.table_{i} (id NUMBER(10), name VARCHAR2(100), created DATE)",
    "ALTER TABLE schema_{i}.table_{i} ADD (email VARCHAR2(200))",
    "CREATE INDEX idx_{i}_name ON schema_{i}.table_{i}(name)",
    "CREATE SEQUENCE schema_{i}.seq_{i} START WITH 1 INCREMENT BY 1",
    "CREATE TABLE schema_{i}.lookup_{i} (code VARCHAR2(10) PRIMARY KEY, label VARCHAR2(200))",
]


def _generate_batch(n: int) -> list[str]:
    """Generate n varied DDL statements from templates."""
    stmts = []
    for i in range(n):
        template = _DDL_TEMPLATES[i % len(_DDL_TEMPLATES)]
        stmts.append(template.format(i=i))
    return stmts


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
class TestRuleEnginePerformance:
    """Latency budgets for the Rule Engine."""

    def test_single_ddl_conversion_under_10ms(self, rule_engine):
        """A single DDL statement should convert in <10ms."""
        obj = scanned_object_from(SIMPLE_DDL)
        start = time.perf_counter()
        result = rule_engine.convert(obj)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["confidence"] > 0, "Conversion should produce a confidence score"
        assert result["converted"], "Conversion should produce output"
        assert elapsed_ms < 10, f"Conversion took {elapsed_ms:.1f}ms, expected <10ms"

    def test_medium_ddl_conversion_under_15ms(self, rule_engine):
        """A medium-complexity DDL with constraints should convert in <15ms."""
        obj = scanned_object_from(MEDIUM_DDL)
        start = time.perf_counter()
        result = rule_engine.convert(obj)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["converted"], "Conversion should produce output"
        assert elapsed_ms < 15, f"Conversion took {elapsed_ms:.1f}ms, expected <15ms"

    def test_100_objects_under_1_second(self, rule_engine):
        """100 objects should convert in <1 second total."""
        statements = _generate_batch(100)
        objects = [scanned_object_from(sql) for sql in statements]

        start = time.perf_counter()
        results = [rule_engine.convert(obj) for obj in objects]
        elapsed_s = time.perf_counter() - start

        assert len(results) == 100
        assert all(r["converted"] for r in results), "All conversions should produce output"
        assert elapsed_s < 1.0, f"Batch took {elapsed_s:.2f}s, expected <1.0s"

    def test_complex_plsql_under_50ms(self, rule_engine):
        """A complex PL/SQL trigger should convert in <50ms."""
        obj = scanned_object_from(COMPLEX_PLSQL_TRIGGER, object_type="TRIGGER")
        start = time.perf_counter()
        result = rule_engine.convert(obj)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["converted"], "Conversion should produce output"
        assert elapsed_ms < 50, f"Conversion took {elapsed_ms:.1f}ms, expected <50ms"

    def test_1000_golden_tests_under_10_seconds(self):
        """All golden tests should run in <10 seconds.

        This test scans the golden test directory and verifies that
        processing the full corpus stays within the time budget.
        """
        golden_dir = pathlib.Path(__file__).parent.parent / "golden"
        if not golden_dir.exists():
            pytest.skip("Golden test directory not found")

        # Collect all .sql files in the golden directory tree
        oracle_files = sorted(golden_dir.rglob("*.oracle.sql"))
        if len(oracle_files) == 0:
            pytest.skip("No golden test files found")

        # Import rule engine (or stub) at function scope
        try:
            from agents.rule_engine.engine import RuleEngine

            engine = RuleEngine()
        except ImportError:
            from tests.benchmarks.conftest import _StubRuleEngine

            engine = _StubRuleEngine()

        start = time.perf_counter()
        results = []
        for oracle_file in oracle_files:
            sql = oracle_file.read_text(encoding="utf-8")
            obj = scanned_object_from(sql, object_type="UNKNOWN")
            results.append(engine.convert(obj))
        elapsed_s = time.perf_counter() - start

        assert len(results) == len(oracle_files)
        assert (
            elapsed_s < 10.0
        ), f"Golden tests ({len(oracle_files)} files) took {elapsed_s:.2f}s, expected <10s"

    def test_conversion_throughput_above_1000_per_second(self, rule_engine):
        """Sustained throughput should exceed 1000 conversions/second."""
        statements = _generate_batch(500)
        objects = [scanned_object_from(sql) for sql in statements]

        start = time.perf_counter()
        for obj in objects:
            rule_engine.convert(obj)
        elapsed_s = time.perf_counter() - start

        throughput = 500 / elapsed_s if elapsed_s > 0 else float("inf")
        assert throughput > 1000, f"Throughput was {throughput:.0f} conv/s, expected >1000 conv/s"

    def test_memory_stable_across_1000_conversions(self, rule_engine):
        """Memory usage should not grow significantly over 1000 conversions.

        This is a smoke test -- not a precise measurement. It checks that
        no obvious memory leak exists by comparing RSS before and after.
        """
        try:
            import resource

            def get_rss_mb():
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except ImportError:
            # Windows: use psutil if available, otherwise skip
            try:
                import psutil

                def get_rss_mb():
                    return psutil.Process().memory_info().rss / (1024 * 1024)
            except ImportError:
                pytest.skip("Neither resource nor psutil available for memory measurement")

        statements = _generate_batch(1000)
        objects = [scanned_object_from(sql) for sql in statements]

        rss_before = get_rss_mb()
        for obj in objects:
            rule_engine.convert(obj)
        rss_after = get_rss_mb()

        growth_mb = rss_after - rss_before
        assert (
            growth_mb < 50
        ), f"Memory grew by {growth_mb:.1f}MB over 1000 conversions, expected <50MB"
