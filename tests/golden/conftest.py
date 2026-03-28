"""Pytest conftest for golden test discovery."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from steindb.testing.loader import load_golden_tests

GOLDEN_DIR = Path(__file__).parent


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "golden_test" in metafunc.fixturenames:
        tests = load_golden_tests(GOLDEN_DIR)
        metafunc.parametrize(
            "golden_test",
            tests,
            ids=[f"{t.category}/{t.name}" for t in tests],
        )
