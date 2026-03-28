#!/usr/bin/env bash
# SteinDB Quality Gate — run all checks before merge
# Uses uv for fast dependency management
set -euo pipefail

echo "=== SteinDB Quality Gate ==="
echo ""

# Step 1: Pre-commit (lint + format + type check)
echo "--- Step 1: Pre-commit hooks ---"
uv run pre-commit run --all-files
echo "PASS: pre-commit"
echo ""

# Step 2: Unit tests with coverage
echo "--- Step 2: pytest with coverage ---"
uv run pytest tests/unit/ -v --cov=src/steindb --cov-report=term-missing --cov-fail-under=90
echo "PASS: unit tests (coverage >= 90%)"
echo ""

# Step 3: Golden tests
echo "--- Step 3: Golden test loading ---"
uv run python -c "
from steindb.testing.loader import load_golden_tests
tests = load_golden_tests()
print(f'Loaded {len(tests)} golden tests')
if len(tests) == 0:
    print('WARNING: No golden tests found')
"
echo "PASS: golden tests loaded"
echo ""

echo "=== ALL QUALITY GATES PASSED ==="
