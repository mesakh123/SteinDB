"""stein verify — verify converted PostgreSQL output for correctness."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path  # noqa: TCH003

import typer
from rich.console import Console
from rich.table import Table

from steindb.contracts import VerifyResult, VerifyStatus
from steindb.verifier import Verifier

console = Console()


def _status_style(status: VerifyStatus) -> str:
    return {
        VerifyStatus.GREEN: "[bold green]GREEN[/]",
        VerifyStatus.YELLOW: "[bold yellow]YELLOW[/]",
        VerifyStatus.RED: "[bold red]RED[/]",
    }.get(status, str(status))


def _collect_sql_files(path: Path) -> list[Path]:
    """Collect .sql files from a file or directory."""
    if path.is_file():
        return [path]
    elif path.is_dir():
        return sorted(path.glob("*.sql"))
    return []


async def _verify_file(verifier: Verifier, sql_path: Path) -> VerifyResult:
    """Verify a single SQL file."""
    content = sql_path.read_text(encoding="utf-8")
    name = sql_path.stem
    # Use TABLE as default object type; real usage would carry metadata
    return await verifier.verify(
        object_name=name,
        object_type="TABLE",
        oracle_sql="",  # original not available from file alone
        postgresql=content,
    )


def verify_command(
    input: Path = typer.Argument(..., help="Converted PostgreSQL file or directory"),  # noqa: A002, B008
    report: str = typer.Option("table", "--report", "-r", help="Report format: table, json, html"),
) -> None:
    """Verify converted PostgreSQL output for correctness."""
    if not input.exists():
        console.print(f"[bold red]Error:[/] Input path does not exist: {input}")
        raise typer.Exit(code=1)

    sql_files = _collect_sql_files(input)
    if not sql_files:
        console.print("[yellow]No .sql files found.[/]")
        raise typer.Exit(code=0)

    console.print(f"\n[bold]SteinDB Verify[/] -- {len(sql_files)} file(s)")

    verifier = Verifier()
    results: list[VerifyResult] = []

    for sql_path in sql_files:
        result = asyncio.run(_verify_file(verifier, sql_path))
        results.append(result)

    # Output results
    if report == "json":
        _output_json(results)
    elif report == "html":
        _output_html(results)
    else:
        _output_table(results)

    # Summary
    green = sum(1 for r in results if r.status == VerifyStatus.GREEN)
    yellow = sum(1 for r in results if r.status == VerifyStatus.YELLOW)
    red = sum(1 for r in results if r.status == VerifyStatus.RED)

    console.print(f"\n[bold]Summary:[/] {green} green, {yellow} yellow, {red} red")

    if red > 0:
        raise typer.Exit(code=1)


def _output_table(results: list[VerifyResult]) -> None:
    table = Table(title="Verification Results")
    table.add_column("Object", style="bold")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Confidence", justify="right")
    table.add_column("Issues", justify="right")

    for r in results:
        table.add_row(
            r.object_name,
            r.object_type,
            _status_style(r.status),
            f"{r.confidence:.0%}",
            str(len(r.issues)),
        )

    console.print(table)


def _output_json(results: list[VerifyResult]) -> None:
    data = [r.model_dump() for r in results]
    console.print(json.dumps(data, indent=2, default=str))


def _output_html(results: list[VerifyResult]) -> None:
    """Minimal HTML output for verification results."""
    rows: list[str] = []
    for r in results:
        color = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}.get(
            r.status.value, "#94a3b8"
        )
        rows.append(
            f"<tr>"
            f"<td>{r.object_name}</td>"
            f"<td>{r.object_type}</td>"
            f"<td style='color:{color};font-weight:bold'>{r.status.value.upper()}</td>"
            f"<td>{r.confidence:.0%}</td>"
            f"<td>{len(r.issues)}</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows)
    html = f"""<!DOCTYPE html>
<html><head><title>SteinDB Verification Report</title>
<style>
body {{ background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; padding: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ padding: 0.5rem; border-bottom: 1px solid #334155; text-align: left; }}
th {{ color: #94a3b8; }}
</style>
</head><body>
<h1>Verification Results</h1>
<table>
<thead><tr><th>Object</th><th>Type</th><th>Status</th><th>Confidence</th><th>Issues</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body></html>"""
    console.print(html)
