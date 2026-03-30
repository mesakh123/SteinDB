"""Tests for trigger function body indentation consistency."""

from __future__ import annotations


def test_trigger_body_consistent_indentation() -> None:
    """Multi-line trigger body should have consistent 2-space indentation."""
    from steindb.contracts.models import ScannedObject
    from steindb.rules.engine import O2PRuleEngine
    from steindb.rules.loader import create_direction_registry

    sql = """CREATE OR REPLACE TRIGGER trg_audit
BEFORE UPDATE ON employees
FOR EACH ROW
BEGIN
  :NEW.updated_at := SYSDATE;
  :NEW.updated_by := USER;
END;"""
    registry = create_direction_registry("o2p")
    engine = O2PRuleEngine(registry)
    obj = ScannedObject(
        name="trg_audit",
        object_type="TRIGGER",
        source_sql=sql,
        schema="PUBLIC",
        line_count=7,
    )
    result = engine.convert(obj)

    # Check indentation consistency in the function body
    lines = result.target_sql.split("\n")
    body_lines: list[str] = []
    in_body = False
    for line in lines:
        if line.strip() == "BEGIN":
            in_body = True
            continue
        if line.strip().startswith("END"):
            in_body = False
            continue
        if in_body and line.strip():
            body_lines.append(line)

    # All body lines should have same indentation (2 spaces)
    for line in body_lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        assert indent == 2, f"Inconsistent indent ({indent} spaces) in: '{line}'"
