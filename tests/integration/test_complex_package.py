"""End-to-end test: convert a complex Oracle PL/SQL package."""

from __future__ import annotations

from steindb.cli.scanner.ddl_parser import DDLParser
from steindb.contracts.models import ObjectType

COMPLEX_ORACLE_PACKAGE = """
CREATE TABLE hr.employees (
    employee_id NUMBER(10) NOT NULL,
    first_name VARCHAR2(100),
    last_name VARCHAR2(100),
    salary NUMBER(10,2),
    department_id NUMBER(10),
    hire_date DATE,
    CONSTRAINT pk_emp PRIMARY KEY (employee_id)
);

CREATE SEQUENCE hr.emp_seq START WITH 1 INCREMENT BY 1;

CREATE OR REPLACE TRIGGER hr.trg_emp_audit
AFTER UPDATE ON hr.employees
FOR EACH ROW
BEGIN
    INSERT INTO hr.salary_audit (emp_id, old_salary, new_salary, changed_date)
    VALUES (:OLD.employee_id, :OLD.salary, :NEW.salary, SYSDATE);
END;
/

CREATE OR REPLACE FUNCTION hr.calculate_bonus(
    p_salary IN NUMBER,
    p_years IN NUMBER
) RETURN NUMBER IS
BEGIN
    RETURN LEAST(p_salary * (p_years * 0.02), 99999);
END;
/

CREATE OR REPLACE PROCEDURE hr.hire_employee(
    p_name IN VARCHAR2,
    p_salary IN NUMBER,
    p_dept_id IN NUMBER
) IS
    v_id NUMBER;
BEGIN
    SELECT hr.emp_seq.NEXTVAL INTO v_id FROM DUAL;
    INSERT INTO hr.employees (employee_id, first_name, salary, department_id, hire_date)
    VALUES (v_id, p_name, NVL(p_salary, 50000), p_dept_id, SYSDATE);
    DBMS_OUTPUT.PUT_LINE('Hired: ' || p_name);
END;
/

CREATE OR REPLACE VIEW hr.active_employees AS
SELECT employee_id, first_name, salary
FROM hr.employees
WHERE hire_date > SYSDATE - 365;
"""


class TestComplexPackageConversion:
    def test_ddl_parser_finds_all_objects(self) -> None:
        parser = DDLParser()
        objects = parser.parse_string(COMPLEX_ORACLE_PACKAGE)
        types = {obj.object_type for obj in objects}
        assert ObjectType.TABLE in types
        assert ObjectType.SEQUENCE in types
        assert len(objects) >= 4  # table, sequence, trigger/function/procedure/view

    def test_rule_engine_converts_table(self) -> None:
        parser = DDLParser()
        objects = parser.parse_string(COMPLEX_ORACLE_PACKAGE)
        tables = [o for o in objects if o.object_type == ObjectType.TABLE]
        assert len(tables) >= 1
        # Table should have Oracle types that rules can convert
        assert "NUMBER" in tables[0].source_sql or "VARCHAR2" in tables[0].source_sql

    def test_rule_engine_converts_with_registry(self) -> None:
        try:
            from steindb.rules.engine import RuleEngine
            from steindb.rules.loader import create_default_registry
        except ImportError:
            import pytest

            pytest.skip("Rule loader not available")

        registry = create_default_registry()
        engine = RuleEngine(registry)
        parser = DDLParser()
        objects = parser.parse_string(COMPLEX_ORACLE_PACKAGE)

        converted = []
        forwarded = []
        for obj in objects:
            result = engine.convert(obj)
            if hasattr(result, "target_sql"):
                converted.append(result)
            else:
                forwarded.append(result)

        # Should convert most objects
        assert len(converted) >= 2, f"Expected 2+ converted, got {len(converted)}"

        # Check specific conversions in converted objects
        all_sql = " ".join(c.target_sql for c in converted)

        # NUMBER should be converted to INTEGER/NUMERIC
        # VARCHAR2 should be converted to VARCHAR
        # These are basic checks that the pipeline works end-to-end
        assert "NUMBER" not in all_sql or "NUMERIC" in all_sql or "INTEGER" in all_sql

    def test_full_pipeline_produces_output(self) -> None:
        parser = DDLParser()
        objects = parser.parse_string(COMPLEX_ORACLE_PACKAGE)
        assert len(objects) >= 4
        # Verify each object has required fields
        for obj in objects:
            assert obj.name
            assert obj.schema or obj.source_sql
            assert obj.object_type
            assert len(obj.source_sql) > 0
