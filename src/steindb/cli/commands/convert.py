"""stein convert — run Oracle-to-PostgreSQL conversion using rules or AI."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from steindb.contracts import (
    ConvertedObject,
    ForwardedObject,
    ObjectType,
    ScannedObject,
    ScanResult,
)
from steindb.rules import RuleEngine
from steindb.rules.loader import create_direction_registry
from steindb.rules.p2o_engine import P2ORuleEngine


def _parse_ddl_file(path: Path) -> list[ScannedObject]:
    """Parse a DDL file into ScannedObject instances (simple heuristic splitter)."""
    content = path.read_text(encoding="utf-8")
    statements = _split_statements(content)
    objects: list[ScannedObject] = []

    for i, stmt in enumerate(statements):
        stripped = stmt.strip()
        if not stripped:
            continue
        obj_type = _detect_object_type(stripped)
        obj_name = _detect_object_name(stripped, obj_type)
        objects.append(
            ScannedObject(
                name=obj_name or f"object_{i}",
                schema="PUBLIC",
                object_type=obj_type,
                source_sql=stripped,
                line_count=stripped.count("\n") + 1,
            )
        )
    return objects


def _split_statements(content: str) -> list[str]:
    """Split SQL content by semicolons, respecting PL/SQL blocks."""
    import re

    # Split on standalone '/' lines (PL/SQL block terminators)
    blocks = re.split(r"\n\s*/\s*\n", content)
    results: list[str] = []
    for block in blocks:
        if any(
            kw in block.upper()
            for kw in [
                "CREATE OR REPLACE PROCEDURE",
                "CREATE OR REPLACE FUNCTION",
                "CREATE OR REPLACE PACKAGE",
                "CREATE OR REPLACE TRIGGER",
                "BEGIN",
                "DECLARE",
            ]
        ):
            results.append(block.strip())
        else:
            for part in block.split(";"):
                part = part.strip()
                if part:
                    results.append(part)
    return results


def _detect_object_type(sql: str) -> ObjectType:
    """Detect Oracle object type from SQL statement."""
    upper = sql.upper().lstrip()
    if upper.startswith("CREATE") or upper.startswith("ALTER"):
        if "MATERIALIZED" in upper[:80] and "VIEW" in upper[:80]:
            return ObjectType.MATERIALIZED_VIEW
        if "TABLE" in upper[:80]:
            return ObjectType.TABLE
        if "INDEX" in upper[:80]:
            return ObjectType.INDEX
        if "SEQUENCE" in upper[:80]:
            return ObjectType.SEQUENCE
        if "VIEW" in upper[:80]:
            return ObjectType.VIEW
        if "TRIGGER" in upper[:80]:
            return ObjectType.TRIGGER
        if "PROCEDURE" in upper[:80]:
            return ObjectType.PROCEDURE
        if "FUNCTION" in upper[:80]:
            return ObjectType.FUNCTION
        if "PACKAGE BODY" in upper[:80]:
            return ObjectType.PACKAGE_BODY
        if "PACKAGE" in upper[:80]:
            return ObjectType.PACKAGE
        if "TYPE" in upper[:80]:
            return ObjectType.TYPE
        if "SYNONYM" in upper[:80]:
            return ObjectType.SYNONYM
    return ObjectType.TABLE  # fallback


def _detect_object_name(sql: str, obj_type: ObjectType) -> str | None:
    """Try to extract the object name from the SQL statement."""
    import re

    pattern = r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?)" r"(?:UNIQUE\s+)?(?:\w+\s+){0,2}(\w+\.)?(\w+)"
    m = re.search(pattern, sql, re.IGNORECASE)
    if m:
        return m.group(2)
    return None


def _load_scan_result_json(path: Path) -> ScanResult:
    """Load a ScanResult from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ScanResult(**data)


def convert_command(
    input: Path = typer.Argument(..., help="Oracle DDL file or scan result JSON"),  # noqa: A002, B008
    output: Path = typer.Option(Path("output/"), "--output", "-o", help="Output directory"),  # noqa: B008
    mode: str = typer.Option("rules", "--mode", "-m", help="Conversion mode: rules, ai, auto"),
    direction: str = typer.Option(
        "o2p", "--direction", "-d", help="Migration direction: o2p or p2o"
    ),
    api_key: str | None = typer.Option(None, "--api-key", help="BYOK API key for AI mode"),
    model: str = typer.Option("gpt-4o", "--model", help="LLM model for AI mode"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be converted without converting"
    ),
) -> None:
    """Convert Oracle SQL/PL-SQL to PostgreSQL (or PostgreSQL to Oracle with --direction p2o)."""
    if not input.exists():
        typer.echo(f"Error: Input path does not exist: {input}", err=True)
        raise typer.Exit(code=1)

    # Validate mode
    if mode not in ("rules", "ai", "auto"):
        typer.echo(f"Error: Invalid mode '{mode}'. Use: rules, ai, auto", err=True)
        raise typer.Exit(code=1)

    # Validate direction
    if direction not in ("o2p", "p2o"):
        typer.echo(f"Error: Invalid direction '{direction}'. Use: o2p, p2o", err=True)
        raise typer.Exit(code=1)

    # AI mode requires authentication (free registration minimum)
    if mode in ("ai", "auto") and not api_key:
        typer.echo(
            "AI-assisted conversion requires a free account.\n"
            "\n"
            "Register in 30 seconds:\n"
            "  stein auth register --email you@company.com\n"
            "\n"
            "Or use rules-only mode (covers 90% of conversions):\n"
            f"  stein convert {input}",
            err=True,
        )
        raise typer.Exit(code=1)

    # Parse input
    if input.suffix == ".json":
        try:
            scan_result = _load_scan_result_json(input)
            objects = scan_result.objects
        except Exception as e:
            typer.echo(f"Error parsing JSON: {e}", err=True)
            raise typer.Exit(code=1) from None
    else:
        objects = _parse_ddl_file(input)

    if not objects:
        typer.echo("No objects found in input.")
        raise typer.Exit(code=0)

    typer.echo(f"SteinDB Convert -- {len(objects)} objects, mode={mode}, direction={direction}")

    # Build Rule Engine with direction-appropriate rules
    registry = create_direction_registry(direction)
    engine = P2ORuleEngine(registry) if direction == "p2o" else RuleEngine(registry)

    converted_list: list[ConvertedObject] = []
    forwarded_list: list[ForwardedObject] = []
    failed_count = 0

    for obj in objects:
        try:
            result = engine.convert(obj)
            if isinstance(result, ConvertedObject):
                converted_list.append(result)
            else:
                forwarded_list.append(result)
        except Exception:
            failed_count += 1

    # Dry-run: show summary only
    if dry_run:
        typer.echo("Dry Run Summary")
        _print_summary(converted_list, forwarded_list, failed_count)
        raise typer.Exit(code=0)

    # Write output files
    output.mkdir(parents=True, exist_ok=True)

    for conv in converted_list:
        out_file = output / f"{conv.name}.sql"
        out_file.write_text(conv.target_sql, encoding="utf-8")

    # Write forwarded objects as SQL files (with LLM_FORWARD comment) + JSON manifest
    for fwd in forwarded_list:
        out_file = output / f"{fwd.name}.sql"
        comment = f"/* LLM_FORWARD: {fwd.forward_reason or 'requires AI conversion'} */\n"
        out_file.write_text(comment + fwd.source_sql, encoding="utf-8")

    if forwarded_list:
        forwarded_manifest = output / "forwarded.json"
        forwarded_data = [f.model_dump() for f in forwarded_list]
        forwarded_manifest.write_text(json.dumps(forwarded_data, indent=2), encoding="utf-8")

    typer.echo(f"Output written to: {output}")
    _print_summary(converted_list, forwarded_list, failed_count)


def _print_summary(
    converted: list[ConvertedObject],
    forwarded: list[ForwardedObject],
    failed: int,
) -> None:
    typer.echo("Conversion Summary")
    typer.echo(f"  Converted (rules): {len(converted)}")
    typer.echo(f"  Forwarded to LLM:  {len(forwarded)}")
    typer.echo(f"  Failed:            {failed}")
    typer.echo(f"  Total:             {len(converted) + len(forwarded) + failed}")
