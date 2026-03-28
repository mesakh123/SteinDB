"""Tests for HTML report renderer — structure, sections, styling."""

from __future__ import annotations

import pytest
from steindb.cli.report.html_renderer import HTMLReportRenderer
from steindb.contracts import ObjectType, ScannedObject, ScanResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_scan_result(objects: list[ScannedObject] | None = None) -> ScanResult:
    if objects is None:
        objects = [
            ScannedObject(
                name="EMPLOYEES",
                schema="HR",
                object_type=ObjectType.TABLE,
                source_sql="CREATE TABLE EMPLOYEES (id NUMBER, name VARCHAR2(100))",
                line_count=1,
            ),
            ScannedObject(
                name="GET_SALARY",
                schema="HR",
                object_type=ObjectType.PROCEDURE,
                source_sql="CREATE OR REPLACE PROCEDURE GET_SALARY AS BEGIN DBMS_OUTPUT.PUT_LINE('hi'); END;",  # noqa: E501
                line_count=3,
            ),
            ScannedObject(
                name="DEPT_VIEW",
                schema="HR",
                object_type=ObjectType.VIEW,
                source_sql="CREATE VIEW DEPT_VIEW AS SELECT * FROM DEPARTMENTS WHERE ROWNUM <= 10",
                line_count=1,
            ),
        ]
    return ScanResult(
        job_id="job-001",
        customer_id="cust-001",
        objects=objects,
        total_objects=len(objects),
        scan_duration_seconds=1.5,
    )


@pytest.fixture()
def sample_scan_result() -> ScanResult:
    return _make_scan_result()


@pytest.fixture()
def sample_complexity_scores() -> dict[str, float]:
    return {"EMPLOYEES": 2.0, "GET_SALARY": 8.5, "DEPT_VIEW": 4.0}


@pytest.fixture()
def sample_dependencies() -> dict[str, list[str]]:
    return {"DEPT_VIEW": ["DEPARTMENTS"], "GET_SALARY": ["EMPLOYEES"]}


@pytest.fixture()
def rendered_html(
    sample_scan_result: ScanResult,
    sample_complexity_scores: dict[str, float],
    sample_dependencies: dict[str, list[str]],
) -> str:
    renderer = HTMLReportRenderer()
    return renderer.render(sample_scan_result, sample_complexity_scores, sample_dependencies)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHTMLStructure:
    def test_is_valid_html(self, rendered_html: str) -> None:
        assert rendered_html.startswith("<!DOCTYPE html>")
        assert "</html>" in rendered_html

    def test_contains_head_and_body(self, rendered_html: str) -> None:
        assert "<head>" in rendered_html
        assert "<body>" in rendered_html

    def test_contains_title(self, rendered_html: str) -> None:
        assert "<title>SteinDB Migration Report</title>" in rendered_html

    def test_contains_charset(self, rendered_html: str) -> None:
        assert 'charset="utf-8"' in rendered_html


class TestHTMLSections:
    def test_executive_summary_section(self, rendered_html: str) -> None:
        assert "Executive Summary" in rendered_html

    def test_total_objects_displayed(self, rendered_html: str) -> None:
        # 3 objects
        assert ">3<" in rendered_html

    def test_object_inventory_section(self, rendered_html: str) -> None:
        assert "Object Inventory" in rendered_html

    def test_object_names_in_inventory(self, rendered_html: str) -> None:
        assert "EMPLOYEES" in rendered_html
        assert "GET_SALARY" in rendered_html
        assert "DEPT_VIEW" in rendered_html

    def test_object_types_in_inventory(self, rendered_html: str) -> None:
        assert "TABLE" in rendered_html
        assert "PROCEDURE" in rendered_html
        assert "VIEW" in rendered_html

    def test_complexity_breakdown_section(self, rendered_html: str) -> None:
        assert "Complexity Breakdown" in rendered_html

    def test_dependency_graph_section(self, rendered_html: str) -> None:
        assert "Dependency Graph" in rendered_html
        assert "DEPT_VIEW" in rendered_html
        assert "DEPARTMENTS" in rendered_html

    def test_oracle_constructs_section(self, rendered_html: str) -> None:
        assert "Oracle-Specific Constructs Detected" in rendered_html

    def test_detects_oracle_constructs(self, rendered_html: str) -> None:
        # DBMS_OUTPUT is in the GET_SALARY procedure
        assert "DBMS_OUTPUT" in rendered_html
        # VARCHAR2 is in the EMPLOYEES table
        assert "VARCHAR2" in rendered_html
        # NUMBER is in the EMPLOYEES table
        assert "NUMBER" in rendered_html

    def test_savings_estimate_section(self, rendered_html: str) -> None:
        assert "Estimated Savings" in rendered_html

    def test_footer_with_cta(self, rendered_html: str) -> None:
        assert "Upgrade to SteinDB Cloud" in rendered_html
        assert "https://app.steindb.com" in rendered_html


class TestHTMLStyling:
    def test_has_inline_styles(self, rendered_html: str) -> None:
        assert "<style>" in rendered_html

    def test_dark_theme_background(self, rendered_html: str) -> None:
        # Dark theme uses #0f172a as background
        assert "#0f172a" in rendered_html

    def test_self_contained_no_external_deps(self, rendered_html: str) -> None:
        # No external CSS or JS links
        assert "<link" not in rendered_html
        assert "<script" not in rendered_html

    def test_complexity_badges(self, rendered_html: str) -> None:
        assert "badge-low" in rendered_html
        assert "badge-high" in rendered_html


class TestHTMLComplexityClassification:
    def test_low_complexity_badge(self, rendered_html: str) -> None:
        # EMPLOYEES has score 2.0 -> low
        assert "badge-low" in rendered_html

    def test_high_complexity_badge(self, rendered_html: str) -> None:
        # GET_SALARY has score 8.5 -> high
        assert "badge-high" in rendered_html

    def test_medium_complexity_badge(self, rendered_html: str) -> None:
        # DEPT_VIEW has score 4.0 -> medium
        assert "badge-medium" in rendered_html


class TestHTMLInlineSVG:
    def test_svg_chart_present(self, rendered_html: str) -> None:
        assert "<svg" in rendered_html
        assert "</svg>" in rendered_html

    def test_svg_has_bars(self, rendered_html: str) -> None:
        assert "<rect" in rendered_html


class TestHTMLJobId:
    def test_job_id_in_report(self, rendered_html: str) -> None:
        assert "job-001" in rendered_html


class TestHTMLEmptyScan:
    def test_empty_objects(self) -> None:
        scan = _make_scan_result(objects=[])
        renderer = HTMLReportRenderer()
        html = renderer.render(scan, {}, {})
        assert "Executive Summary" in html
        assert "No objects to chart" in html

    def test_no_dependencies(self) -> None:
        scan = _make_scan_result()
        renderer = HTMLReportRenderer()
        html = renderer.render(scan, {"EMPLOYEES": 1.0, "GET_SALARY": 2.0, "DEPT_VIEW": 3.0}, {})
        assert "No dependencies detected" in html
