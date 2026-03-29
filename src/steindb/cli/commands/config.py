"""stein config — configuration management (set/get/list)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from steindb.cli.config_manager import ConfigManager

app = typer.Typer(no_args_is_help=True)
console = Console()


def _get_config_manager() -> ConfigManager:
    """Return the default ConfigManager. Patched in tests."""
    return ConfigManager()


@app.command("set")
def config_set(
    key: str = typer.Argument(help="Configuration key"),
    value: str = typer.Argument(help="Configuration value"),
) -> None:
    """Set a configuration value."""
    mgr = _get_config_manager()
    mgr.set(key, value)
    console.print(f"Set [bold]{key}[/bold] = {value}")


@app.command("get")
def config_get(
    key: str = typer.Argument(help="Configuration key"),
) -> None:
    """Get a configuration value."""
    mgr = _get_config_manager()
    value = mgr.get(key)
    if value is None:
        console.print(f"[yellow]{key}[/yellow] is not set.")
    else:
        console.print(f"{key} = {value}")


@app.command("list")
def config_list() -> None:
    """List all configuration values."""
    mgr = _get_config_manager()
    all_config = mgr.list_all()
    table = Table(title="SteinDB Configuration")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    for k, v in sorted(all_config.items()):
        display = str(v) if v is not None else "[dim]<not set>[/dim]"
        table.add_row(k, display)
    console.print(table)
