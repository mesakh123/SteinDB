"""Tests for the scan command -- Task 7."""

import json

import pytest
from steindb.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

SAMPLE_DDL = """\
CREATE TABLE hr.employees (
    id NUMBER(10) NOT NULL,
    name VARCHAR2(100),
    hire_date DATE,
    salary NUMBER(10,2),
    CONSTRAINT pk_emp PRIMARY KEY (id)
);

CREATE SEQUENCE hr.emp_seq START WITH 1 INCREMENT BY 1;

CREATE OR REPLACE TRIGGER hr.trg_emp_bi
BEFORE INSERT ON hr.employees
FOR EACH ROW
BEGIN
    :NEW.id := hr.emp_seq.NEXTVAL;
END;
/

CREATE OR REPLACE VIEW hr.active_employees AS
SELECT * FROM hr.employees WHERE hire_date > SYSDATE - 365;
"""


@pytest.fixture
def ddl_file(tmp_path):
    f = tmp_path / "test.sql"
    f.write_text(SAMPLE_DDL)
    return f


@pytest.fixture
def ddl_dir(tmp_path):
    (tmp_path / "tables.sql").write_text(
        "CREATE TABLE hr.t1 (id NUMBER);\nCREATE TABLE hr.t2 (id NUMBER);"
    )
    (tmp_path / "views.sql").write_text("CREATE VIEW hr.v1 AS SELECT * FROM hr.t1;")
    return tmp_path


class TestScanCommand:
    def test_scan_file_table_output(self, ddl_file):
        result = runner.invoke(app, ["scan", str(ddl_file)])
        assert result.exit_code == 0
        assert "EMPLOYEES" in result.output
        assert "EMP_SEQ" in result.output

    def test_scan_file_json_output(self, ddl_file, tmp_path):
        out = tmp_path / "report.json"
        result = runner.invoke(app, ["scan", str(ddl_file), "-o", "json", "-f", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert "summary" in data
        assert "objects" in data
        assert data["summary"]["total"] == 4

    def test_scan_file_html_output(self, ddl_file, tmp_path):
        out = tmp_path / "report.html"
        result = runner.invoke(app, ["scan", str(ddl_file), "-o", "html", "-f", str(out)])
        assert result.exit_code == 0
        html = out.read_text()
        assert "SteinDB" in html
        assert "EMPLOYEES" in html

    def test_scan_directory(self, ddl_dir):
        result = runner.invoke(app, ["scan", str(ddl_dir)])
        assert result.exit_code == 0
        assert "T1" in result.output
        assert "V1" in result.output

    def test_scan_schema_filter(self, ddl_file):
        result = runner.invoke(app, ["scan", str(ddl_file), "--schema", "HR"])
        assert result.exit_code == 0
        assert "EMPLOYEES" in result.output

    def test_scan_nonexistent_path(self, tmp_path):
        result = runner.invoke(app, ["scan", str(tmp_path / "nope.sql")])
        assert result.exit_code == 1

    def test_scan_summary_displayed(self, ddl_file):
        result = runner.invoke(app, ["scan", str(ddl_file)])
        assert "Total Objects" in result.output
        assert "Summary" in result.output

    def test_scan_json_has_dependencies(self, ddl_file, tmp_path):
        out = tmp_path / "report.json"
        result = runner.invoke(app, ["scan", str(ddl_file), "-o", "json", "-f", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert "dependency_order" in data
