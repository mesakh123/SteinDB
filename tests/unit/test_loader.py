"""Tests for the golden test YAML loader."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003

import pytest
from steindb.contracts.models import GoldenTestCase
from steindb.testing.loader import (
    load_golden_tests,
    load_golden_tests_by_category,
    validate_golden_test,
)


class TestLoadGoldenTests:
    def test_load_returns_list_of_golden_test_cases(self, tmp_path: Path) -> None:
        yaml_content = """
- name: varchar2_basic
  category: data_types
  oracle: "VARCHAR2(100)"
  expected_postgresql: "VARCHAR(100)"
- name: number_integer
  category: data_types
  oracle: "NUMBER(9)"
  expected_postgresql: "INTEGER"
"""
        (tmp_path / "data_types.yaml").write_text(yaml_content)
        tests = load_golden_tests(tmp_path)
        assert len(tests) == 2
        assert all(isinstance(t, GoldenTestCase) for t in tests)

    def test_load_by_category(self, tmp_path: Path) -> None:
        dt_dir = tmp_path / "data_types"
        dt_dir.mkdir()
        (dt_dir / "basic.yaml").write_text("""
- name: varchar2
  category: data_types
  oracle: "VARCHAR2(100)"
  expected_postgresql: "VARCHAR(100)"
""")
        syn_dir = tmp_path / "syntax"
        syn_dir.mkdir()
        (syn_dir / "nvl.yaml").write_text("""
- name: nvl_simple
  category: syntax
  oracle: "NVL(x, 0)"
  expected_postgresql: "COALESCE(x, 0)"
""")
        by_cat = load_golden_tests_by_category(tmp_path)
        assert "data_types" in by_cat
        assert "syntax" in by_cat
        assert len(by_cat["data_types"]) == 1
        assert len(by_cat["syntax"]) == 1

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert load_golden_tests(tmp_path) == []

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("not: valid: yaml: [")
        with pytest.raises(Exception):  # noqa: B017
            load_golden_tests(tmp_path)

    def test_empty_yaml_file_skipped(self, tmp_path: Path) -> None:
        """Cover line 46: YAML file that parses to None (empty file) is skipped."""
        (tmp_path / "empty.yaml").write_text("")
        tests = load_golden_tests(tmp_path)
        assert tests == []

    def test_non_list_yaml_raises_value_error(self, tmp_path: Path) -> None:
        """Cover lines 48-49: YAML file containing a dict instead of a list raises ValueError."""
        (tmp_path / "bad_structure.yaml").write_text("name: foo\ncategory: data_types\n")
        with pytest.raises(ValueError, match="expected a YAML list"):
            load_golden_tests(tmp_path)

    def test_yml_extension_loaded(self, tmp_path: Path) -> None:
        """Ensure .yml files are loaded (not just .yaml)."""
        yaml_content = """
- name: test_yml
  category: data_types
  oracle: "VARCHAR2(50)"
  expected_postgresql: "VARCHAR(50)"
"""
        (tmp_path / "test.yml").write_text(yaml_content)
        tests = load_golden_tests(tmp_path)
        assert len(tests) == 1
        assert tests[0].name == "test_yml"

    def test_empty_yml_file_skipped(self, tmp_path: Path) -> None:
        """Cover line 46 via .yml extension: empty .yml is skipped."""
        (tmp_path / "empty.yml").write_text("")
        tests = load_golden_tests(tmp_path)
        assert tests == []

    def test_non_list_yml_raises(self, tmp_path: Path) -> None:
        """Cover lines 48-49 via .yml: dict in .yml raises ValueError."""
        (tmp_path / "dict.yml").write_text("key: value\n")
        with pytest.raises(ValueError, match="expected a YAML list"):
            load_golden_tests(tmp_path)


class TestValidateGoldenTest:
    def test_valid_case(self) -> None:
        tc = GoldenTestCase(
            name="test1",
            category="data_types",
            oracle="VARCHAR2(100)",
            expected_postgresql="VARCHAR(100)",
        )
        errors = validate_golden_test(tc)
        assert errors == []

    def test_missing_expected_for_rules_category(self) -> None:
        tc = GoldenTestCase(
            name="test1",
            category="data_types",
            oracle="VARCHAR2(100)",
            expected_postgresql=None,
        )
        errors = validate_golden_test(tc)
        assert len(errors) == 1
        assert "expected_postgresql" in errors[0].lower()
