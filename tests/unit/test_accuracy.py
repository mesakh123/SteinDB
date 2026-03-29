"""Unit tests for accuracy measurement framework."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from steindb.contracts.models import GoldenTestCase
from steindb.rules.loader import create_default_registry

if TYPE_CHECKING:
    from steindb.rules.registry import RuleRegistry
from steindb.testing.accuracy import (
    AccuracyMetrics,
    AccuracyReport,
    _normalize_sql,
)

# -----------------------------------------------------------------------
# AccuracyMetrics
# -----------------------------------------------------------------------


class TestAccuracyMetrics:
    def test_empty_metrics(self) -> None:
        m = AccuracyMetrics()
        assert m.exact_match_rate == 0.0
        assert m.syntax_valid_rate == 0.0
        assert m.no_remnants_rate == 0.0
        assert m.confidence_calibration == 0.0

    def test_exact_match_rate(self) -> None:
        m = AccuracyMetrics(total_tests=10, exact_matches=8)
        assert m.exact_match_rate == pytest.approx(0.8)

    def test_syntax_valid_rate(self) -> None:
        m = AccuracyMetrics(total_tests=10, syntax_valid=9)
        assert m.syntax_valid_rate == pytest.approx(0.9)

    def test_no_remnants_rate(self) -> None:
        m = AccuracyMetrics(total_tests=5, no_remnants=5)
        assert m.no_remnants_rate == pytest.approx(1.0)

    def test_confidence_calibration_perfect(self) -> None:
        """When predictions exactly match actuals, calibration = 0."""
        m = AccuracyMetrics(
            confidence_scores=[1.0, 0.0, 1.0],
            predicted_confidences=[1.0, 0.0, 1.0],
        )
        assert m.confidence_calibration == pytest.approx(0.0)

    def test_confidence_calibration_worst(self) -> None:
        """When predictions are opposite of actuals, calibration = 1.0."""
        m = AccuracyMetrics(
            confidence_scores=[1.0, 0.0],
            predicted_confidences=[0.0, 1.0],
        )
        assert m.confidence_calibration == pytest.approx(1.0)

    def test_confidence_calibration_partial(self) -> None:
        m = AccuracyMetrics(
            confidence_scores=[1.0, 0.0],
            predicted_confidences=[0.8, 0.2],
        )
        # MAE = (|1.0-0.8| + |0.0-0.2|) / 2 = (0.2 + 0.2) / 2 = 0.2
        assert m.confidence_calibration == pytest.approx(0.2)

    def test_confidence_calibration_mismatched_lengths(self) -> None:
        m = AccuracyMetrics(
            confidence_scores=[1.0],
            predicted_confidences=[1.0, 0.5],
        )
        assert m.confidence_calibration == 1.0


# -----------------------------------------------------------------------
# _normalize_sql
# -----------------------------------------------------------------------


class TestNormalizeSql:
    def test_strips_whitespace(self) -> None:
        assert _normalize_sql("  SELECT 1  ") == "select 1"

    def test_collapses_whitespace(self) -> None:
        assert _normalize_sql("SELECT\n  1\n  FROM\n  t") == "select 1 from t"

    def test_removes_trailing_semicolons(self) -> None:
        assert _normalize_sql("SELECT 1;") == "select 1"
        assert _normalize_sql("SELECT 1;;;") == "select 1"

    def test_lowercases(self) -> None:
        assert _normalize_sql("SELECT Name FROM T") == "select name from t"


# -----------------------------------------------------------------------
# AccuracyReport
# -----------------------------------------------------------------------


class TestAccuracyReport:
    @pytest.fixture
    def registry(self) -> RuleRegistry:
        return create_default_registry()

    def test_empty_tests(self, registry: RuleRegistry) -> None:
        report = AccuracyReport(golden_tests=[], rule_registry=registry)
        result = report.measure()
        assert result["total_tests"] == 0
        assert result["exact_match_rate"] == 0.0

    def test_skips_tests_without_expected(self, registry: RuleRegistry) -> None:
        tests = [
            GoldenTestCase(
                name="no_expected",
                category="data_types",
                oracle="CREATE TABLE t (id NUMBER(10))",
                expected_postgresql=None,
            ),
        ]
        report = AccuracyReport(golden_tests=tests, rule_registry=registry)
        result = report.measure()
        assert result["total_tests"] == 0

    def test_measures_with_golden_tests(self, registry: RuleRegistry) -> None:
        """Run a basic accuracy measurement with a simple test case."""
        tests = [
            GoldenTestCase(
                name="simple_select",
                category="syntax",
                oracle="SELECT SYSDATE FROM DUAL",
                expected_postgresql="SELECT CURRENT_TIMESTAMP",
            ),
        ]
        report = AccuracyReport(golden_tests=tests, rule_registry=registry)
        result = report.measure()
        assert result["total_tests"] == 1
        assert 0.0 <= result["exact_match_rate"] <= 1.0
        assert 0.0 <= result["syntax_valid_rate"] <= 1.0
        assert 0.0 <= result["no_remnants_rate"] <= 1.0
        assert "metrics" in result

    def test_result_contains_all_keys(self, registry: RuleRegistry) -> None:
        tests = [
            GoldenTestCase(
                name="test",
                category="syntax",
                oracle="SELECT 1 FROM DUAL",
                expected_postgresql="SELECT 1",
            ),
        ]
        report = AccuracyReport(golden_tests=tests, rule_registry=registry)
        result = report.measure()
        expected_keys = {
            "exact_match_rate",
            "syntax_valid_rate",
            "no_remnants_rate",
            "confidence_calibration",
            "total_tests",
            "metrics",
        }
        assert expected_keys.issubset(result.keys())
