"""Tests for DDL parser -- Task 4."""

from pathlib import Path

import pytest
from steindb.cli.scanner.ddl_parser import DDLParser
from steindb.contracts import ObjectType


@pytest.fixture
def parser():
    return DDLParser()


class TestParseString:
    def test_parse_single_create_table(self, parser):
        sql = "CREATE TABLE hr.employees (id NUMBER PRIMARY KEY, name VARCHAR2(100));"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.TABLE
        assert objects[0].name == "EMPLOYEES"
        assert objects[0].schema == "HR"

    def test_parse_table_without_schema(self, parser):
        sql = "CREATE TABLE employees (id NUMBER);"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].schema == "PUBLIC"
        assert objects[0].name == "EMPLOYEES"

    def test_parse_create_index(self, parser):
        sql = "CREATE INDEX hr.idx_emp ON hr.employees(name);"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.INDEX
        assert objects[0].name == "IDX_EMP"

    def test_parse_create_unique_index(self, parser):
        sql = "CREATE UNIQUE INDEX hr.idx_uniq ON hr.employees(id);"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.INDEX

    def test_parse_create_sequence(self, parser):
        sql = "CREATE SEQUENCE hr.emp_seq START WITH 1 INCREMENT BY 1;"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.SEQUENCE
        assert objects[0].name == "EMP_SEQ"

    def test_parse_create_view(self, parser):
        sql = "CREATE VIEW hr.active_emp AS SELECT * FROM hr.employees;"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.VIEW

    def test_parse_create_or_replace_view(self, parser):
        sql = "CREATE OR REPLACE VIEW hr.v1 AS SELECT 1 FROM dual;"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.VIEW

    def test_parse_materialized_view(self, parser):
        sql = "CREATE MATERIALIZED VIEW hr.mv1 AS SELECT * FROM hr.employees;"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.MATERIALIZED_VIEW

    def test_parse_create_synonym(self, parser):
        sql = "CREATE SYNONYM hr.emp FOR hr.employees;"
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.SYNONYM

    def test_parse_create_package(self, parser):
        sql = """
        CREATE OR REPLACE PACKAGE hr.emp_pkg AS
          PROCEDURE hire(p_name VARCHAR2);
          FUNCTION get_salary(p_id NUMBER) RETURN NUMBER;
        END emp_pkg;
        /
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.PACKAGE

    def test_parse_create_package_body(self, parser):
        sql = """
        CREATE OR REPLACE PACKAGE BODY hr.emp_pkg AS
          PROCEDURE hire(p_name VARCHAR2) IS
          BEGIN
            INSERT INTO hr.employees (name) VALUES (p_name);
          END;
        END emp_pkg;
        /
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.PACKAGE_BODY

    def test_parse_procedure(self, parser):
        sql = """
        CREATE OR REPLACE PROCEDURE hr.update_sal(p_id NUMBER) AS
        BEGIN
            UPDATE hr.employees SET salary = 100 WHERE id = p_id;
        END;
        /
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.PROCEDURE
        assert objects[0].name == "UPDATE_SAL"

    def test_parse_function(self, parser):
        sql = """
        CREATE OR REPLACE FUNCTION hr.get_count RETURN NUMBER AS
            v_count NUMBER;
        BEGIN
            SELECT COUNT(*) INTO v_count FROM hr.employees;
            RETURN v_count;
        END;
        /
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.FUNCTION

    def test_parse_trigger(self, parser):
        sql = """
        CREATE OR REPLACE TRIGGER hr.trg_emp_bi
        BEFORE INSERT ON hr.employees
        FOR EACH ROW
        BEGIN
            :NEW.id := hr.emp_seq.NEXTVAL;
        END;
        /
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 1
        assert objects[0].object_type == ObjectType.TRIGGER
        assert objects[0].name == "TRG_EMP_BI"

    def test_parse_multiple_objects(self, parser):
        sql = """
        CREATE TABLE t1 (id NUMBER);
        CREATE VIEW v1 AS SELECT * FROM t1;
        CREATE SEQUENCE s1 START WITH 1;
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 3
        types = {o.object_type for o in objects}
        assert types == {ObjectType.TABLE, ObjectType.VIEW, ObjectType.SEQUENCE}

    def test_parse_mixed_plsql_and_ddl(self, parser):
        sql = """
        CREATE TABLE hr.t1 (id NUMBER);

        CREATE OR REPLACE TRIGGER hr.trg1
        BEFORE INSERT ON hr.t1
        FOR EACH ROW
        BEGIN
            :NEW.id := 1;
        END;
        /

        CREATE SEQUENCE hr.s1 START WITH 1;
        """
        objects = parser.parse_string(sql)
        assert len(objects) == 3

    def test_line_count(self, parser):
        sql = "CREATE TABLE t1 (\n    id NUMBER,\n    name VARCHAR2(100)\n);"
        objects = parser.parse_string(sql)
        assert objects[0].line_count == 4

    def test_empty_string(self, parser):
        assert parser.parse_string("") == []
        assert parser.parse_string("   ") == []

    def test_non_create_statements_ignored(self, parser):
        sql = "ALTER TABLE hr.employees ADD (email VARCHAR2(200));"
        objects = parser.parse_string(sql)
        assert len(objects) == 0


class TestParseFile:
    def test_parse_file(self, parser, tmp_path):
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("CREATE TABLE t1 (id NUMBER);\nCREATE SEQUENCE s1;")
        objects = parser.parse_file(sql_file)
        assert len(objects) == 2

    def test_parse_sample_fixture(self, parser):
        fixture = Path(__file__).parent.parent.parent / "fixtures" / "sample_oracle.sql"
        if fixture.exists():
            objects = parser.parse_file(fixture)
            assert (
                len(objects) >= 8
            )  # table, table, seq, trigger, view, proc, func, synonym, index, mview


class TestParseDirectory:
    def test_parse_directory(self, parser, tmp_path):
        (tmp_path / "tables.sql").write_text("CREATE TABLE t1 (id NUMBER);")
        (tmp_path / "views.sql").write_text("CREATE VIEW v1 AS SELECT 1 FROM dual;")
        objects = parser.parse_directory(tmp_path)
        assert len(objects) == 2

    def test_parse_directory_ignores_non_sql(self, parser, tmp_path):
        (tmp_path / "tables.sql").write_text("CREATE TABLE t1 (id NUMBER);")
        (tmp_path / "readme.txt").write_text("not sql")
        objects = parser.parse_directory(tmp_path)
        assert len(objects) == 1

    def test_parse_empty_directory(self, parser, tmp_path):
        objects = parser.parse_directory(tmp_path)
        assert objects == []
