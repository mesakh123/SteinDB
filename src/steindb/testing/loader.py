"""Golden test YAML loader for SteinDB."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from steindb.contracts.models import GoldenTestCase

# Default directory for golden tests, relative to project root.
GOLDEN_TEST_DIR: Path = Path(__file__).resolve().parents[3] / "tests" / "golden"

# Categories where expected_postgresql is mandatory (deterministic rules).
RULES_CATEGORIES: set[str] = {
    "data_types",
    "syntax",
    "ddl",
    "sequences",
    "functions",
    "triggers",
    "plsql_control_flow",
    "packages",
    "synonyms",
    "materialized_views",
    "partitioning",
    "grants",
}


def load_golden_tests(directory: Path | None = None) -> list[GoldenTestCase]:
    """Load all golden test YAML files recursively from *directory*.

    Each YAML file must contain a list of mappings that conform to
    :class:`GoldenTestCase`.  Files with ``.yaml`` or ``.yml`` extensions
    are loaded.  Returns an empty list when no YAML files are found.
    """
    root = directory or GOLDEN_TEST_DIR
    results: list[GoldenTestCase] = []

    yaml_files = sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))
    for path in yaml_files:
        # Skip P2O (bidirectional) test files — they use BidirectionalTestCase.
        if "p2o" in path.parts:
            continue
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            continue
        if not isinstance(raw, list):
            msg = f"{path}: expected a YAML list, got {type(raw).__name__}"
            raise ValueError(msg)
        for item in raw:
            results.append(GoldenTestCase(**item))

    return results


def load_golden_tests_by_category(
    directory: Path | None = None,
) -> dict[str, list[GoldenTestCase]]:
    """Load golden tests and group them by category."""
    tests = load_golden_tests(directory)
    by_category: dict[str, list[GoldenTestCase]] = defaultdict(list)
    for tc in tests:
        by_category[tc.category].append(tc)
    return dict(by_category)


def validate_golden_test(tc: GoldenTestCase) -> list[str]:
    """Return a list of validation error strings for *tc*.

    Rules:
    * If the category belongs to :data:`RULES_CATEGORIES` and
      ``expected_postgresql`` is ``None``, an error is reported.
    """
    errors: list[str] = []

    if tc.category in RULES_CATEGORIES and tc.expected_postgresql is None:
        errors.append(f"expected_postgresql is required for category '{tc.category}'")

    return errors
