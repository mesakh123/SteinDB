"""Scan command -- parse DDL, score complexity, analyze dependencies."""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from steindb.cli.config_manager import ConfigManager
from steindb.cli.licensing import LicenseManager
from steindb.cli.scanner.complexity import ComplexityScorer
from steindb.cli.scanner.ddl_parser import DDLParser
from steindb.cli.scanner.dependency import DependencyGraph, build_dependency_graph
from steindb.contracts import ObjectType, ScannedObject

console = Console()

# Map Oracle object type strings from ALL_OBJECTS to our ObjectType enum.
_ORACLE_TYPE_MAP: dict[str, ObjectType] = {
    "TABLE": ObjectType.TABLE,
    "VIEW": ObjectType.VIEW,
    "INDEX": ObjectType.INDEX,
    "SEQUENCE": ObjectType.SEQUENCE,
    "TRIGGER": ObjectType.TRIGGER,
    "PROCEDURE": ObjectType.PROCEDURE,
    "FUNCTION": ObjectType.FUNCTION,
    "PACKAGE": ObjectType.PACKAGE,
    "PACKAGE BODY": ObjectType.PACKAGE_BODY,
    "SYNONYM": ObjectType.SYNONYM,
    "MATERIALIZED VIEW": ObjectType.MATERIALIZED_VIEW,
    "TYPE": ObjectType.TYPE,
}


def _get_config_manager() -> ConfigManager:
    """Return the default ConfigManager. Patched in tests."""
    return ConfigManager()


def scan_command(
    input_path: Path = typer.Argument(  # noqa: B008
        ..., help="Oracle DDL file or directory (ignored when --host is set)"
    ),
    schema: str | None = typer.Option(None, "--schema", "-s", help="Filter by schema"),  # noqa: B008
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, html"),  # noqa: B008
    output_file: Path | None = typer.Option(None, "--file", "-f", help="Write report to file"),  # noqa: B008
    host: str | None = typer.Option(None, "--host", help="Oracle host for live connection"),
    port: int = typer.Option(1521, "--port", help="Oracle port (default 1521)"),
    service: str | None = typer.Option(None, "--service", help="Oracle service name"),
    sid: str | None = typer.Option(None, "--sid", help="Oracle SID"),
    user: str | None = typer.Option(None, "--user", help="Oracle username"),
    password: str | None = typer.Option(None, "--password", help="Oracle password"),
) -> None:
    """Scan Oracle schema and generate migration readiness report."""
    start = time.monotonic()

    scorer = ComplexityScorer()

    if host:
        # --- Live Oracle connection mode ---
        objects = _scan_live_oracle(
            host=host,
            port=port,
            service=service,
            sid=sid,
            user=user or "",
            password=password or "",
            schema=schema,
        )
    else:
        # --- DDL file/directory mode ---
        parser = DDLParser()
        input_path = Path(input_path)
        if not input_path.exists():
            console.print(f"[red]Error:[/red] Path not found: {input_path}")
            raise typer.Exit(code=1)

        if input_path.is_dir():
            objects = parser.parse_directory(input_path)
        else:
            objects = parser.parse_file(input_path)

    if not objects:
        console.print("[yellow]No Oracle objects found in the input.[/yellow]")
        raise typer.Exit(code=0)

    if schema:
        schema_upper = schema.upper()
        objects = [o for o in objects if o.schema == schema_upper]

    # License tier detection (no object limit -- rules-only is unlimited)
    mgr = _get_config_manager()
    license_mgr = LicenseManager(mgr)
    total_objects = len(objects)
    display_objects = objects

    scores: dict[str, tuple[float, list[str]]] = {}
    for obj in display_objects:
        s, factors = scorer.score(obj)
        scores[f"{obj.schema}.{obj.name}"] = (s, factors)

    dep_graph = build_dependency_graph(display_objects)
    topo_order = dep_graph.topological_sort()

    elapsed = time.monotonic() - start

    if output == "json":
        report = _build_json_report(
            display_objects,
            scores,
            dep_graph,
            topo_order,
            elapsed,
            total_objects=total_objects,
            tier=license_mgr.get_tier(),
        )
        if output_file:
            output_file.write_text(json.dumps(report, indent=2))
            console.print(f"[green]Report written to {output_file}[/green]")
        else:
            console.print_json(json.dumps(report, indent=2))
    elif output == "html":
        html = _build_html_report(display_objects, scores, dep_graph, topo_order, elapsed)
        if output_file:
            output_file.write_text(html)
            console.print(f"[green]HTML report written to {output_file}[/green]")
        else:
            console.print(html)
    else:
        _print_table_report(display_objects, scores, dep_graph, topo_order, elapsed)


def _scan_live_oracle(
    host: str,
    port: int,
    service: str | None,
    sid: str | None,
    user: str,
    password: str,
    schema: str | None,
) -> list[ScannedObject]:
    """Connect to a live Oracle database and scan schema objects."""
    from steindb.cli.scanner.oracle_connection import (
        OracleConnectionConfig,
        OracleScanner,
    )

    config = OracleConnectionConfig(
        host=host,
        port=port,
        service_name=service,
        sid=sid,
        user=user,
        password=password,
    )
    scanner = OracleScanner(config)
    try:
        scanner.connect()
    except ImportError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    try:
        schemas_to_scan = [schema.upper()] if schema else scanner.get_schemas()

        objects: list[ScannedObject] = []
        for s in schemas_to_scan:
            for raw in scanner.get_objects(s):
                obj_type = _ORACLE_TYPE_MAP.get(raw["object_type"])
                if obj_type is None:
                    continue
                source = raw["source_sql"] or ""
                objects.append(
                    ScannedObject(
                        name=raw["name"],
                        schema=raw["schema"].upper(),
                        object_type=obj_type,
                        source_sql=source if source else f"-- empty source for {raw['name']}",
                        line_count=source.count("\n") + 1 if source else 0,
                    )
                )
        return objects
    finally:
        scanner.disconnect()


def _color_for_score(score: float) -> str:
    if score <= 3.0:
        return "green"
    elif score <= 6.0:
        return "yellow"
    return "red"


def _print_table_report(
    objects: list[ScannedObject],
    scores: dict[str, tuple[float, list[str]]],
    dep_graph: DependencyGraph,
    topo_order: list[str],
    elapsed: float,
) -> None:
    table = Table(title="SteinDB Scan Results", show_lines=True)
    table.add_column("Schema", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Lines", justify="right")
    table.add_column("Complexity", justify="right")
    table.add_column("Deps", justify="right")

    green = yellow = red = 0
    for obj in objects:
        key = f"{obj.schema}.{obj.name}"
        s, factors = scores.get(key, (0.0, []))
        color = _color_for_score(s)
        if color == "green":
            green += 1
        elif color == "yellow":
            yellow += 1
        else:
            red += 1
        deps = dep_graph.get_dependencies(key)
        table.add_row(
            obj.schema,
            obj.name,
            obj.object_type.value,
            str(obj.line_count),
            f"[{color}]{s:.1f}[/{color}]",
            str(len(deps)),
        )

    console.print(table)
    console.print()

    summary = Table(title="Summary", show_header=False)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value")
    summary.add_row("Total Objects", str(len(objects)))
    summary.add_row("Green (easy)", f"[green]{green}[/green]")
    summary.add_row("Yellow (moderate)", f"[yellow]{yellow}[/yellow]")
    summary.add_row("Red (complex)", f"[red]{red}[/red]")
    summary.add_row("Scan Duration", f"{elapsed:.2f}s")
    avg_score = sum(s for s, _ in scores.values()) / max(len(scores), 1)
    summary.add_row("Avg Complexity", f"{avg_score:.1f}")
    est_savings = len(objects) * 2000
    summary.add_row("Est. Annual Savings", f"${est_savings:,}")
    console.print(summary)


def _build_json_report(
    objects: list[ScannedObject],
    scores: dict[str, tuple[float, list[str]]],
    dep_graph: DependencyGraph,
    topo_order: list[str],
    elapsed: float,
    *,
    total_objects: int | None = None,
    tier: str = "free",
) -> dict[str, object]:
    obj_list = []
    for obj in objects:
        key = f"{obj.schema}.{obj.name}"
        s, factors = scores.get(key, (0.0, []))
        obj_list.append(
            {
                "schema": obj.schema,
                "name": obj.name,
                "type": obj.object_type.value,
                "line_count": obj.line_count,
                "complexity_score": round(s, 2),
                "complexity_factors": factors,
                "color": _color_for_score(s),
                "dependencies": list(dep_graph.get_dependencies(key)),
            }
        )
    green = sum(1 for o in obj_list if o["color"] == "green")
    yellow = sum(1 for o in obj_list if o["color"] == "yellow")
    red = sum(1 for o in obj_list if o["color"] == "red")
    return {
        "summary": {
            "total": total_objects if total_objects is not None else len(objects),
            "displayed": len(objects),
            "green": green,
            "yellow": yellow,
            "red": red,
            "scan_duration_seconds": round(elapsed, 2),
            "tier": tier,
        },
        "objects": obj_list,
        "dependency_order": topo_order,
    }


def _build_html_report(
    objects: list[ScannedObject],
    scores: dict[str, tuple[float, list[str]]],
    dep_graph: DependencyGraph,
    topo_order: list[str],
    elapsed: float,
) -> str:
    rows = ""
    for obj in objects:
        key = f"{obj.schema}.{obj.name}"
        s, factors = scores.get(key, (0.0, []))
        color = _color_for_score(s)
        deps = dep_graph.get_dependencies(key)
        rows += (
            f"<tr class='{color}'><td>{obj.schema}</td><td>{obj.name}</td>"
            f"<td>{obj.object_type.value}</td><td>{obj.line_count}</td>"
            f"<td>{s:.1f}</td><td>{len(deps)}</td></tr>\n"
        )
    return (
        "<!DOCTYPE html><html><head><title>SteinDB Scan Report</title></head>"
        "<body><h1>SteinDB Scan Report</h1>"
        f"<p>Objects: {len(objects)} | Duration: {elapsed:.2f}s</p>"
        "<table><tr><th>Schema</th><th>Name</th><th>Type</th>"
        "<th>Lines</th><th>Complexity</th><th>Deps</th></tr>"
        f"{rows}</table></body></html>"
    )


def register_scan_commands(scan_app: typer.Typer) -> None:
    scan_app.command("ddl")(scan_command)
