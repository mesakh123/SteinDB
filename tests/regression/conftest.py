"""Pytest conftest for regression test discovery from YAML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    import pytest

REGRESSION_DIR = Path(__file__).parent


@dataclass
class RegressionTestCase:
    """A single regression test case loaded from YAML."""

    id: str
    description: str
    oracle_input: str
    expected_postgresql: str
    bug_report: str = ""
    tags: list[str] | None = None


def load_regression_tests(
    directory: Path | None = None,
) -> list[RegressionTestCase]:
    """Load all regression test YAML files from the given directory.

    Each YAML file must contain a list of mappings with at least:
    - id: str
    - description: str
    - oracle_input: str
    - expected_postgresql: str
    """
    root = directory or REGRESSION_DIR
    results: list[RegressionTestCase] = []

    yaml_files = sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))
    for path in yaml_files:
        # Skip template files
        if "template" in path.name:
            continue
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            continue
        if not isinstance(raw, list):
            msg = f"{path}: expected a YAML list, got {type(raw).__name__}"
            raise ValueError(msg)
        for item in raw:
            results.append(
                RegressionTestCase(
                    id=item["id"],
                    description=item.get("description", ""),
                    oracle_input=item["oracle_input"],
                    expected_postgresql=item["expected_postgresql"],
                    bug_report=item.get("bug_report", ""),
                    tags=item.get("tags"),
                )
            )

    return results


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize regression tests from YAML files."""
    if "regression_test" in metafunc.fixturenames:
        tests = load_regression_tests(REGRESSION_DIR)
        if tests:
            metafunc.parametrize(
                "regression_test",
                tests,
                ids=[t.id for t in tests],
            )
        else:
            # No regression YAML files yet — skip parametrization
            metafunc.parametrize("regression_test", [], ids=[])
