"""SteinDB CLI entry point — Typer app with all subcommands."""

import typer
from rich.console import Console

app = typer.Typer(
    name="stein",
    help="SteinDB — AI-powered Oracle-to-PostgreSQL migration",
    no_args_is_help=True,
)
console = Console()

# Register sub-Typer groups (auth, config, cloud)
from steindb.cli.commands import auth, cloud, config  # noqa: E402

app.add_typer(auth.app, name="auth", help="Authentication (login/logout/status)")
app.add_typer(config.app, name="config", help="Configuration (set/get/list)")
app.add_typer(cloud.app, name="cloud", help="Cloud provider integration (plan/connect/migrate)")

# Register top-level commands
from steindb.cli.commands import convert, report, scan, verify  # noqa: E402

app.command("scan")(scan.scan_command)
app.command("convert")(convert.convert_command)
app.command("verify")(verify.verify_command)
app.command("report")(report.report_command)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    """SteinDB — AI-powered Oracle-to-PostgreSQL migration."""
    if version:
        from steindb.cli import __version__

        console.print(f"SteinDB CLI v{__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
