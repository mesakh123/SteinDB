"""Tests for Rich-based display utilities — banner, tables, progress bar."""

from io import StringIO

import pytest
from rich.console import Console
from steindb.cli import display


@pytest.fixture()
def capture_console(monkeypatch):
    """Replace the module-level console with one that captures output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True, width=120)
    monkeypatch.setattr(display, "console", test_console)
    return buf


class TestPrintBanner:
    def test_banner_prints_steindb(self, capture_console):
        display.print_banner()
        output = capture_console.getvalue()
        assert "SteinDB" in output

    def test_banner_prints_migration_text(self, capture_console):
        display.print_banner()
        output = capture_console.getvalue()
        assert "PostgreSQL" in output


class TestPrintScanSummary:
    def test_scan_summary_shows_table_title(self, capture_console):
        display.print_scan_summary([])
        output = capture_console.getvalue()
        assert "Scan Results" in output

    def test_scan_summary_shows_objects(self, capture_console):
        objects = [
            {"name": "employees", "object_type": "TABLE", "schema": "hr", "complexity": 2.0},
            {"name": "emp_seq", "object_type": "SEQUENCE", "schema": "hr", "complexity": 1.0},
        ]
        display.print_scan_summary(objects)
        output = capture_console.getvalue()
        assert "employees" in output
        assert "TABLE" in output
        assert "emp_seq" in output
        assert "SEQUENCE" in output

    def test_scan_summary_uses_complexity_scores(self, capture_console):
        objects = [{"name": "employees", "object_type": "TABLE", "schema": "hr", "complexity": 1.0}]
        scores = {"employees": 8.5}
        display.print_scan_summary(objects, complexity_scores=scores)
        output = capture_console.getvalue()
        assert "8.5" in output

    def test_scan_summary_empty_list(self, capture_console):
        display.print_scan_summary([])
        output = capture_console.getvalue()
        assert "Scan Results" in output


class TestComplexityStatus:
    def test_simple_status(self):
        result = display._complexity_status(2.0)
        assert "Simple" in result

    def test_moderate_status(self):
        result = display._complexity_status(5.0)
        assert "Moderate" in result

    def test_complex_status(self):
        result = display._complexity_status(9.0)
        assert "Complex" in result

    def test_boundary_simple_moderate(self):
        assert "Simple" in display._complexity_status(3.0)
        assert "Moderate" in display._complexity_status(3.1)

    def test_boundary_moderate_complex(self):
        assert "Moderate" in display._complexity_status(7.0)
        assert "Complex" in display._complexity_status(7.1)


class TestPrintConversionSummary:
    def test_conversion_summary_shows_counts(self, capture_console):
        display.print_conversion_summary(8, 2, 0)
        output = capture_console.getvalue()
        assert "8" in output
        assert "2" in output
        assert "Conversion Summary" in output

    def test_conversion_summary_shows_percentages(self, capture_console):
        display.print_conversion_summary(8, 2, 0)
        output = capture_console.getvalue()
        assert "80.0%" in output
        assert "20.0%" in output

    def test_conversion_summary_zero_total(self, capture_console):
        display.print_conversion_summary(0, 0, 0)
        output = capture_console.getvalue()
        assert "0.0%" in output

    def test_conversion_summary_all_failed(self, capture_console):
        display.print_conversion_summary(0, 0, 5)
        output = capture_console.getvalue()
        assert "100.0%" in output


class TestPrintVerificationSummary:
    def test_verification_summary_shows_results(self, capture_console):
        results = [
            {
                "object_name": "employees",
                "object_type": "TABLE",
                "status": "green",
                "confidence": 0.95,
                "issues": [],
            },
            {
                "object_name": "give_raise",
                "object_type": "PROCEDURE",
                "status": "yellow",
                "confidence": 0.70,
                "issues": [{"code": "W001", "message": "test"}],
            },
        ]
        display.print_verification_summary(results)
        output = capture_console.getvalue()
        assert "employees" in output
        assert "give_raise" in output
        assert "PASS" in output
        assert "WARN" in output

    def test_verification_summary_red_status(self, capture_console):
        results = [
            {
                "object_name": "broken",
                "object_type": "VIEW",
                "status": "red",
                "confidence": 0.2,
                "issues": [{"code": "E001"}, {"code": "E002"}],
            },
        ]
        display.print_verification_summary(results)
        output = capture_console.getvalue()
        assert "FAIL" in output
        assert "2" in output

    def test_verification_summary_empty_list(self, capture_console):
        display.print_verification_summary([])
        output = capture_console.getvalue()
        assert "Verification Report" in output


class TestStatusIndicator:
    def test_green(self):
        assert "PASS" in display._status_indicator("green")

    def test_yellow(self):
        assert "WARN" in display._status_indicator("yellow")

    def test_red(self):
        assert "FAIL" in display._status_indicator("red")

    def test_case_insensitive(self):
        assert "PASS" in display._status_indicator("GREEN")
        assert "WARN" in display._status_indicator("Yellow")


class TestFreeTierWarning:
    def test_warning_shows_registration_prompt(self, capture_console):
        display.print_free_tier_warning(10, 25)
        output = capture_console.getvalue()
        assert "stein auth register" in output

    def test_warning_shows_rules_unlimited(self, capture_console):
        display.print_free_tier_warning(10, 50)
        output = capture_console.getvalue()
        assert "free and unlimited" in output

    def test_warning_shows_ai_label(self, capture_console):
        display.print_free_tier_warning(10, 20)
        output = capture_console.getvalue()
        assert "AI Features" in output


class TestCreateProgress:
    def test_returns_progress_instance(self):
        progress = display.create_progress()
        assert isinstance(progress, display.Progress)

    def test_progress_has_columns(self):
        progress = display.create_progress()
        assert len(progress.columns) == 4
