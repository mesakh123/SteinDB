"""stein cloud — cloud provider integration commands."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 — needed at runtime by Typer

import typer
import yaml
from rich.console import Console
from rich.table import Table

from steindb.cloud.connectors import build_dsn
from steindb.cloud.models import (
    CloudConnection,
    CloudProvider,
    ManagedService,
)
from steindb.cloud.planner import CloudMigrationPlanner

app = typer.Typer(no_args_is_help=True)
console = Console()

# ---- Helpers ----------------------------------------------------------------


def _load_cloud_config(path: Path) -> CloudConnection:
    """Load a CloudConnection from a YAML config file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CloudConnection(
        provider=CloudProvider(data["provider"]),
        service=ManagedService(data["service"]),
        host=data.get("host", ""),
        port=int(data.get("port", 5432)),
        database=data.get("database", ""),
        username=data.get("username", ""),
        password=data.get("password", ""),
        ssl_mode=data.get("ssl_mode", "require"),
        region=data.get("region", ""),
        aws_access_key=data.get("aws_access_key", ""),
        aws_secret_key=data.get("aws_secret_key", ""),
        rds_instance_id=data.get("rds_instance_id", ""),
        gcp_project=data.get("gcp_project", ""),
        gcp_instance=data.get("gcp_instance", ""),
        azure_subscription=data.get("azure_subscription", ""),
        azure_resource_group=data.get("azure_resource_group", ""),
    )


# ---- Commands ---------------------------------------------------------------


@app.command("providers")
def providers_command() -> None:
    """List supported cloud providers and managed database services."""
    table = Table(title="Supported Cloud Providers & Services")
    table.add_column("Provider", style="cyan")
    table.add_column("Service", style="green")
    table.add_column("Type", style="yellow")

    rows: list[tuple[str, str, str]] = [
        ("AWS", "rds_oracle", "Oracle"),
        ("AWS", "rds_postgresql", "PostgreSQL"),
        ("AWS", "aurora_postgresql", "PostgreSQL"),
        ("GCP", "cloud_sql_postgresql", "PostgreSQL"),
        ("GCP", "alloydb", "PostgreSQL"),
        ("Azure", "azure_postgresql", "PostgreSQL"),
        ("Azure", "azure_postgresql_flex", "PostgreSQL"),
        ("Local", "local_oracle", "Oracle"),
        ("Local", "local_postgresql", "PostgreSQL"),
    ]
    for provider, service, db_type in rows:
        table.add_row(provider, service, db_type)

    console.print(table)


@app.command("connect")
def connect_command(
    provider: str = typer.Option(
        ..., "--provider", "-p", help="Cloud provider (aws/gcp/azure/local)"
    ),
    service: str = typer.Option(..., "--service", "-s", help="Managed service name"),
    host: str = typer.Option(..., "--host", help="Database host"),
    port: int = typer.Option(5432, "--port", help="Database port"),
    database: str = typer.Option("", "--database", "-d", help="Database name"),
    username: str = typer.Option("", "--username", "-u", help="Username"),
    ssl_mode: str = typer.Option("require", "--ssl-mode", help="SSL mode"),
) -> None:
    """Test a cloud database connection and print the DSN."""
    try:
        conn = CloudConnection(
            provider=CloudProvider(provider),
            service=ManagedService(service),
            host=host,
            port=port,
            database=database,
            username=username,
            ssl_mode=ssl_mode,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    try:
        dsn = build_dsn(conn)
    except ValueError as exc:
        typer.echo(f"Error building DSN: {exc}", err=True)
        raise typer.Exit(code=1) from None

    console.print(f"[green]Provider:[/green] {conn.provider.value}")
    console.print(f"[green]Service:[/green]  {conn.service.value}")
    console.print(f"[green]DSN:[/green]      {dsn}")


@app.command("plan")
def plan_command(
    source_config: Path = typer.Option(  # noqa: B008
        ..., "--source", help="Path to source connection YAML config"
    ),
    target_config: Path = typer.Option(  # noqa: B008
        ..., "--target", help="Path to target connection YAML config"
    ),
) -> None:
    """Generate a migration plan from source and target cloud configs."""
    if not source_config.exists():
        typer.echo(f"Error: source config not found: {source_config}", err=True)
        raise typer.Exit(code=1)
    if not target_config.exists():
        typer.echo(f"Error: target config not found: {target_config}", err=True)
        raise typer.Exit(code=1)

    source = _load_cloud_config(source_config)
    target = _load_cloud_config(target_config)

    planner = CloudMigrationPlanner()
    migration_plan = planner.plan(source, target)

    console.print("[bold]Migration Plan[/bold]")
    console.print(f"  Direction: {migration_plan.direction.upper()}")
    console.print(f"  Source:    {source.provider.value} / {source.service.value} ({source.host})")
    console.print(f"  Target:    {target.provider.value} / {target.service.value} ({target.host})")

    if migration_plan.warnings:
        console.print(f"\n[yellow]Warnings ({len(migration_plan.warnings)}):[/yellow]")
        for warning in migration_plan.warnings:
            console.print(f"  - {warning}")
    else:
        console.print("\n[green]No warnings.[/green]")


@app.command("migrate")
def migrate_command(
    source_config: Path = typer.Option(  # noqa: B008
        ..., "--source-config", help="Path to source connection YAML config"
    ),
    target_config: Path = typer.Option(  # noqa: B008
        ..., "--target-config", help="Path to target connection YAML config"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing migration"),
) -> None:
    """Run a cloud-to-cloud migration (plan + convert)."""
    if not source_config.exists():
        typer.echo(f"Error: source config not found: {source_config}", err=True)
        raise typer.Exit(code=1)
    if not target_config.exists():
        typer.echo(f"Error: target config not found: {target_config}", err=True)
        raise typer.Exit(code=1)

    source = _load_cloud_config(source_config)
    target = _load_cloud_config(target_config)

    planner = CloudMigrationPlanner()
    migration_plan = planner.plan(source, target)

    console.print(f"[bold]Cloud Migration[/bold] ({migration_plan.direction.upper()})")
    console.print(
        f"  {source.provider.value}/{source.service.value} -> "
        f"{target.provider.value}/{target.service.value}"
    )

    if migration_plan.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in migration_plan.warnings:
            console.print(f"  - {w}")

    if dry_run:
        console.print("\n[cyan]Dry run — no changes made.[/cyan]")
        raise typer.Exit(code=0)

    # Full migration requires live database connectivity (future implementation).
    console.print(
        "\n[yellow]Live cloud migration is not yet implemented.[/yellow]\n"
        "Use 'stein convert' with DDL files exported from the source database."
    )
