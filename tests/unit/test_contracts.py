"""Tests for cross-agent Pydantic contract models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from steindb.contracts.models import (
    ConvertedObject,
    ForwardedObject,
    GoldenTestCase,
    Issue,
    ObjectType,
    RuleOutput,
    ScannedObject,
    ScanResult,
    TranspileResult,
    VerifyResult,
    VerifyStatus,
)


class TestScannedObject:
    def test_create(self) -> None:
        obj = ScannedObject(
            name="EMPLOYEES",
            schema="HR",
            object_type=ObjectType.TABLE,
            source_sql="CREATE TABLE HR.EMPLOYEES (ID NUMBER(10))",
            line_count=1,
        )
        assert obj.object_type == ObjectType.TABLE
        assert obj.line_count == 1

    def test_empty_sql_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScannedObject(
                name="BAD",
                schema="HR",
                object_type=ObjectType.TABLE,
                source_sql="",
                line_count=0,
            )

    def test_dependencies_default_empty(self) -> None:
        obj = ScannedObject(
            name="T",
            schema="S",
            object_type=ObjectType.TABLE,
            source_sql="CREATE TABLE T (id INT)",
            line_count=1,
        )
        assert obj.dependencies == []


class TestScanResult:
    def test_create(self) -> None:
        result = ScanResult(
            job_id="j-1",
            customer_id="c-1",
            objects=[
                ScannedObject(
                    name="T",
                    schema="S",
                    object_type=ObjectType.TABLE,
                    source_sql="CREATE TABLE T (id INT)",
                    line_count=1,
                )
            ],
            total_objects=1,
            scan_duration_seconds=2.5,
        )
        assert result.total_objects == 1


class TestRuleOutput:
    def test_converted_and_forwarded(self) -> None:
        output = RuleOutput(
            job_id="j-1",
            customer_id="c-1",
            converted=[
                ConvertedObject(
                    name="T",
                    schema="S",
                    object_type=ObjectType.TABLE,
                    source_sql="CREATE TABLE T (ID NUMBER(10))",
                    target_sql="CREATE TABLE t (id INTEGER)",
                    confidence=1.0,
                    method="rules",
                    rules_applied=["number_to_integer"],
                )
            ],
            forwarded=[
                ForwardedObject(
                    name="P",
                    schema="S",
                    object_type=ObjectType.PACKAGE,
                    source_sql="CREATE PACKAGE ...",
                    forward_reason="Contains DBMS_OUTPUT",
                )
            ],
            rules_converted_count=1,
            forwarded_to_llm_count=1,
        )
        assert output.converted[0].confidence == 1.0
        assert output.forwarded[0].forward_reason == "Contains DBMS_OUTPUT"


class TestTranspileResult:
    def test_valid(self) -> None:
        result = TranspileResult(
            postgresql="SELECT 1;",
            confidence=0.92,
            changes=["Converted NVL to COALESCE"],
            warnings=[],
            test_hints=["Test with NULL input"],
        )
        assert result.confidence == 0.92

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            TranspileResult(
                postgresql="X",
                confidence=1.5,
                changes=[],
                warnings=[],
                test_hints=[],
            )

    def test_empty_postgresql_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TranspileResult(
                postgresql="",
                confidence=0.5,
                changes=[],
                warnings=[],
                test_hints=[],
            )


class TestVerifyResult:
    def test_green(self) -> None:
        result = VerifyResult(
            object_name="get_total",
            object_type="FUNCTION",
            status=VerifyStatus.GREEN,
            confidence=0.97,
            parse_valid=True,
            explain_valid=True,
            issues=[],
        )
        assert result.status == VerifyStatus.GREEN

    def test_red_with_issues(self) -> None:
        result = VerifyResult(
            object_name="trg_audit",
            object_type="TRIGGER",
            status=VerifyStatus.RED,
            confidence=0.42,
            parse_valid=False,
            explain_valid=False,
            issues=[Issue(code="PARSE_FAIL", message="Syntax error", severity="error")],
        )
        assert len(result.issues) == 1

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            VerifyResult(
                object_name="x",
                object_type="TABLE",
                status=VerifyStatus.GREEN,
                confidence=1.5,
                parse_valid=True,
                explain_valid=True,
                issues=[],
            )
        with pytest.raises(ValidationError):
            VerifyResult(
                object_name="x",
                object_type="TABLE",
                status=VerifyStatus.GREEN,
                confidence=-0.1,
                parse_valid=True,
                explain_valid=True,
                issues=[],
            )


class TestGoldenTestCase:
    def test_minimal(self) -> None:
        tc = GoldenTestCase(
            name="varchar2_to_varchar",
            category="data_types",
            oracle="CREATE TABLE t (name VARCHAR2(100))",
            expected_postgresql="CREATE TABLE t (name VARCHAR(100))",
        )
        assert tc.category == "data_types"

    def test_with_metadata(self) -> None:
        tc = GoldenTestCase(
            name="connect_by_simple",
            category="connect_by",
            oracle="SELECT ... CONNECT BY ...",
            expected_postgresql="WITH RECURSIVE ...",
            complexity=4,
            constructs=["CONNECT BY", "LEVEL"],
            tags=["hierarchical"],
        )
        assert tc.complexity == 4
        assert len(tc.constructs) == 2
