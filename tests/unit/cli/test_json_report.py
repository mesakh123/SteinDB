"""Tests for JSON report renderer — structure and schema validation."""

from __future__ import annotations

import json

import pytest
from steindb.cli.report.generator import ReportGenerator
from steindb.cli.report.json_renderer import JSONReportRenderer
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
                name="EMP_SEQ",
                schema="HR",
                object_type=ObjectType.SEQUENCE,
                source_sql="CREATE SEQUENCE EMP_SEQ START WITH 1 INCREMENT BY 1",
                line_count=1,
            ),
        ]
    return ScanResult(
        job_id="job-002",
        customer_id="cust-002",
        objects=objects,
        total_objects=len(objects),
        scan_duration_seconds=2.0,
    )


@pytest.fixture()
def sample_scan_result() -> ScanResult:
    return _make_scan_result()


@pytest.fixture()
def sample_complexity_scores() -> dict[str, float]:
    return {"EMPLOYEES": 1.5, "GET_SALARY": 9.0, "EMP_SEQ": 1.0}


@pytest.fixture()
def sample_dependencies() -> dict[str, list[str]]:
    return {"GET_SALARY": ["EMPLOYEES", "EMP_SEQ"]}


@pytest.fixture()
def rendered_json(
    sample_scan_result: ScanResult,
    sample_complexity_scores: dict[str, float],
    sample_dependencies: dict[str, list[str]],
) -> dict:
    renderer = JSONReportRenderer()
    raw = renderer.render(sample_scan_result, sample_complexity_scores, sample_dependencies)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJSONStructure:
    def test_is_valid_json(
        self,
        sample_scan_result: ScanResult,
        sample_complexity_scores: dict[str, float],
        sample_dependencies: dict[str, list[str]],
    ) -> None:
        renderer = JSONReportRenderer()
        raw = renderer.render(sample_scan_result, sample_complexity_scores, sample_dependencies)
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_top_level_keys(self, rendered_json: dict) -> None:
        expected_keys = {
            "version",
            "generated_at",
            "job_id",
            "customer_id",
            "summary",
            "objects",
            "dependencies",
            "complexity_factors",
        }
        assert expected_keys.issubset(set(rendered_json.keys()))

    def test_version(self, rendered_json: dict) -> None:
        assert rendered_json["version"] == "0.1.0"

    def test_generated_at_format(self, rendered_json: dict) -> None:
        # Should be ISO 8601 format
        assert "T" in rendered_json["generated_at"]
        assert rendered_json["generated_at"].endswith("Z")

    def test_job_id(self, rendered_json: dict) -> None:
        assert rendered_json["job_id"] == "job-002"

    def test_customer_id(self, rendered_json: dict) -> None:
        assert rendered_json["customer_id"] == "cust-002"


class TestJSONSummary:
    def test_total_objects(self, rendered_json: dict) -> None:
        assert rendered_json["summary"]["total_objects"] == 3

    def test_by_type(self, rendered_json: dict) -> None:
        by_type = rendered_json["summary"]["by_type"]
        assert by_type["TABLE"] == 1
        assert by_type["PROCEDURE"] == 1
        assert by_type["SEQUENCE"] == 1

    def test_avg_complexity(self, rendered_json: dict) -> None:
        avg = rendered_json["summary"]["avg_complexity"]
        # (1.5 + 9.0 + 1.0) / 3 = 3.833...
        assert 3.8 <= avg <= 3.84

    def test_complexity_breakdown(self, rendered_json: dict) -> None:
        breakdown = rendered_json["summary"]["complexity_breakdown"]
        assert "low" in breakdown
        assert "medium" in breakdown
        assert "high" in breakdown
        # EMPLOYEES=1.5 (low), EMP_SEQ=1.0 (low), GET_SALARY=9.0 (high)
        assert breakdown["low"] == 2
        assert breakdown["medium"] == 0
        assert breakdown["high"] == 1

    def test_rule_convertible(self, rendered_json: dict) -> None:
        assert rendered_json["summary"]["rule_convertible"] == 2

    def test_llm_required(self, rendered_json: dict) -> None:
        assert rendered_json["summary"]["llm_required"] == 1


class TestJSONObjects:
    def test_object_count(self, rendered_json: dict) -> None:
        assert len(rendered_json["objects"]) == 3

    def test_object_fields(self, rendered_json: dict) -> None:
        obj = rendered_json["objects"][0]
        required_fields = {
            "name",
            "schema",
            "object_type",
            "line_count",
            "complexity_score",
            "complexity_class",
            "dependencies",
        }
        assert required_fields.issubset(set(obj.keys()))

    def test_object_complexity_class(self, rendered_json: dict) -> None:
        by_name = {o["name"]: o for o in rendered_json["objects"]}
        assert by_name["EMPLOYEES"]["complexity_class"] == "low"
        assert by_name["GET_SALARY"]["complexity_class"] == "high"
        assert by_name["EMP_SEQ"]["complexity_class"] == "low"


class TestJSONDependencies:
    def test_dependencies_present(self, rendered_json: dict) -> None:
        deps = rendered_json["dependencies"]
        assert "GET_SALARY" in deps
        assert "EMPLOYEES" in deps["GET_SALARY"]
        assert "EMP_SEQ" in deps["GET_SALARY"]


class TestJSONComplexityFactors:
    def test_detects_oracle_constructs(self, rendered_json: dict) -> None:
        factors = rendered_json["complexity_factors"]
        # DBMS_OUTPUT appears in GET_SALARY
        assert "DBMS_OUTPUT" in factors
        # NUMBER appears in EMPLOYEES
        assert "NUMBER" in factors
        # VARCHAR2 appears in EMPLOYEES
        assert "VARCHAR2" in factors


class TestReportGenerator:
    def test_html_format(
        self,
        sample_scan_result: ScanResult,
        sample_complexity_scores: dict[str, float],
        sample_dependencies: dict[str, list[str]],
    ) -> None:
        gen = ReportGenerator()
        result = gen.generate(
            sample_scan_result, sample_complexity_scores, sample_dependencies, format="html"
        )
        assert "<!DOCTYPE html>" in result

    def test_json_format(
        self,
        sample_scan_result: ScanResult,
        sample_complexity_scores: dict[str, float],
        sample_dependencies: dict[str, list[str]],
    ) -> None:
        gen = ReportGenerator()
        result = gen.generate(
            sample_scan_result, sample_complexity_scores, sample_dependencies, format="json"
        )
        parsed = json.loads(result)
        assert parsed["version"] == "0.1.0"

    def test_unknown_format_raises(
        self,
        sample_scan_result: ScanResult,
        sample_complexity_scores: dict[str, float],
        sample_dependencies: dict[str, list[str]],
    ) -> None:
        gen = ReportGenerator()
        with pytest.raises(ValueError, match="Unknown format"):
            gen.generate(
                sample_scan_result, sample_complexity_scores, sample_dependencies, format="pdf"
            )


class TestJSONEmptyScan:
    def test_empty_objects(self) -> None:
        scan = _make_scan_result(objects=[])
        renderer = JSONReportRenderer()
        raw = renderer.render(scan, {}, {})
        parsed = json.loads(raw)
        assert parsed["summary"]["total_objects"] == 0
        assert parsed["objects"] == []
        assert parsed["summary"]["avg_complexity"] == 0.0
