# Contributing to SteinDB

## License Notice

SteinDB is licensed under the [Business Source License 1.1 (BSL 1.1)](LICENSE). By contributing to SteinDB, you agree that your contributions will be licensed under BSL 1.1.

**What this means for contributors:**
- Your contributions are source-available under BSL 1.1, not a permissive open-source license.
- After 4 years, each version of SteinDB (including your contributions) automatically converts to the Apache License 2.0.
- The BSL 1.1 restricts others from offering SteinDB as a competing hosted service. It does NOT restrict anyone from using, modifying, or self-hosting SteinDB.
- This is the same model used by HashiCorp (Terraform), Sentry, CockroachDB, and MariaDB.

If you have questions about the license or how it affects your contributions, please reach out at cmesakh@ymail.com before submitting a PR.

## Development Setup

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/steindb/steindb.git && cd steindb
uv sync --all-extras

# Run tests
uv run pytest tests/unit/ -v

# Install pre-commit hooks
uv run pre-commit install
```

## How to Contribute

### Golden Test Pairs (Most Valuable!)
Add Oracle/PostgreSQL conversion pairs in `tests/golden/`:
1. Pick category (data_types, syntax, triggers, etc.)
2. Add YAML entry: `name`, `category`, `oracle`, `expected_postgresql`
3. Run tests, submit PR

### Rule Modules
1. Extend `Rule` base class in `src/steindb/rules/`
2. Write tests FIRST (TDD)
3. Add golden tests validating the rule

### Bug Reports
Use issue template. Include: Oracle input, expected output, actual output, version.

## Developer Certificate of Origin (DCO)

All contributions require a sign-off. Add to your commits:

`git commit -s -m "your message"`

This adds: `Signed-off-by: Your Name <email>`

See CLA.md for the full contributor agreement.

## Code Standards
- Python 3.12+, mypy --strict, pytest >90% coverage, ruff
- TDD: tests before implementation
- Golden tests are the source of truth
