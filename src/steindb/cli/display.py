"""Rich-based display utilities for SteinDB CLI terminal output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def print_banner() -> None:
    """Print SteinDB ASCII banner."""
    console.print(
        Panel.fit(
            "[bold blue]SteinDB[/] \u2014 Oracle \u2192 PostgreSQL Migration",
            border_style="blue",
        )
    )


def print_scan_summary(
    scan_result: list[dict[str, Any]],
    complexity_scores: dict[str, float] | None = None,
) -> None:
    """Print a Rich table summarizing scan results.

    Args:
        scan_result: List of dicts with keys: name, object_type, schema, complexity.
        complexity_scores: Optional mapping of object name to complexity score.
    """
    if complexity_scores is None:
        complexity_scores = {}

    table = Table(title="Scan Results")
    table.add_column("Object", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Schema")
    table.add_column("Complexity", justify="right")
    table.add_column("Status", justify="center")

    for obj in scan_result:
        name = obj.get("name", "unknown")
        obj_type = obj.get("object_type", "unknown")
        schema = obj.get("schema", "")
        complexity = complexity_scores.get(name, obj.get("complexity", 0.0))
        status = _complexity_status(complexity)
        table.add_row(name, obj_type, schema, f"{complexity:.1f}", status)

    console.print(table)


def _complexity_status(score: float) -> str:
    """Return a colored status indicator based on complexity score."""
    if score <= 3.0:
        return "[green]\u2714 Simple[/green]"
    elif score <= 7.0:
        return "[yellow]\u26a0 Moderate[/yellow]"
    else:
        return "[red]\u2718 Complex[/red]"


def print_conversion_summary(
    converted_count: int,
    forwarded_count: int,
    failed_count: int,
) -> None:
    """Print conversion results summary."""
    total = converted_count + forwarded_count + failed_count
    table = Table(title="Conversion Summary")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    def _pct(n: int) -> str:
        return f"{n / total * 100:.1f}%" if total > 0 else "0.0%"

    table.add_row("[green]Rules Converted[/green]", str(converted_count), _pct(converted_count))
    table.add_row("[yellow]Forwarded to LLM[/yellow]", str(forwarded_count), _pct(forwarded_count))
    table.add_row("[red]Failed[/red]", str(failed_count), _pct(failed_count))
    table.add_row("[bold]Total[/bold]", str(total), "100.0%")

    console.print(table)


def print_verification_summary(results: list[dict[str, Any]]) -> None:
    """Print verification results with green/yellow/red indicators.

    Args:
        results: List of dicts with keys: object_name, object_type, status,
                 confidence, issues.
    """
    table = Table(title="Verification Report")
    table.add_column("Object", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Confidence", justify="right")
    table.add_column("Issues", justify="right")

    for r in results:
        status = r.get("status", "red")
        status_display = _status_indicator(status)
        confidence = r.get("confidence", 0.0)
        issue_count = len(r.get("issues", []))
        table.add_row(
            r.get("object_name", "unknown"),
            r.get("object_type", "unknown"),
            status_display,
            f"{confidence:.0%}",
            str(issue_count),
        )

    console.print(table)


def _status_indicator(status: str) -> str:
    """Return a colored status indicator."""
    status_lower = status.lower()
    if status_lower == "green":
        return "[green]\u2714 PASS[/green]"
    elif status_lower == "yellow":
        return "[yellow]\u26a0 WARN[/yellow]"
    else:
        return "[red]\u2718 FAIL[/red]"


def print_free_tier_warning(shown: int, total: int) -> None:
    """Print a registration prompt for AI features.

    Note: rules-only mode is unlimited. This prompt encourages registration
    to unlock AI-assisted conversion for complex objects.
    """
    console.print(
        Panel(
            "[yellow]Rules-only mode is free and unlimited.\n"
            "Register (free) to unlock AI-assisted conversion for complex objects:\n"
            "[bold]stein auth register[/bold][/yellow]",
            title="[yellow]Unlock AI Features[/yellow]",
            border_style="yellow",
        )
    )


def create_progress() -> Progress:
    """Create a Rich progress bar for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
