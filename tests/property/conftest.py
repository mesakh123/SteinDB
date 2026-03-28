"""Conftest for property-based tests.

Provides a shared RuleRegistry fixture for all Hypothesis tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from steindb.rules.loader import create_default_registry

if TYPE_CHECKING:
    from steindb.rules.registry import RuleRegistry


@pytest.fixture(scope="module")
def registry() -> RuleRegistry:
    """Create and return the default rule registry."""
    return create_default_registry()
