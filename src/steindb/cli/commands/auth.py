"""stein auth — authentication commands (register/login/logout/status)."""

from __future__ import annotations

import typer
from rich.console import Console

from steindb.cli.config_manager import ConfigManager

app = typer.Typer(no_args_is_help=True)
console = Console()


def _get_config_manager() -> ConfigManager:
    """Return the default ConfigManager. Patched in tests."""
    return ConfigManager()


@app.command()
def register(
    email: str = typer.Option(..., "--email", "-e", prompt="Email address"),
) -> None:
    """Register for a free SteinDB account to unlock AI-assisted conversion."""
    console.print("[bold]Registering...[/]")
    # For now: generate a local token (server-side registration comes later)
    # This is a placeholder that simulates the flow
    from steindb.auth.models import AccountTier, generate_token

    token = generate_token(AccountTier.REGISTERED)
    mgr = _get_config_manager()
    mgr.set("api_key", token)
    mgr.set("email", email)
    console.print("[green]Registered successfully![/]")
    console.print(f"Token: {token[:15]}...{token[-5:]}")
    console.print("Stored in: ~/.steindb/config.yml")
    console.print()
    console.print("You can now use AI-assisted conversion:")
    console.print("  [cyan]stein convert --mode ai myfile.sql[/]")


@app.command()
def login(
    token: str = typer.Option(..., "--token", "-t", prompt="Token"),
) -> None:
    """Login with an existing SteinDB token."""
    from steindb.auth.models import get_tier_from_token

    tier = get_tier_from_token(token)
    mgr = _get_config_manager()
    mgr.set("api_key", token)
    console.print(f"[green]Logged in![/] Tier: {tier.value}")


@app.command()
def logout() -> None:
    """Remove stored token."""
    mgr = _get_config_manager()
    mgr.delete("api_key")
    mgr.delete("email")
    console.print("[yellow]Logged out.[/] Rules-only mode still works without a token.")


@app.command()
def upgrade() -> None:
    """Upgrade your account to a paid tier. Opens browser to checkout."""
    mgr = _get_config_manager()
    token = mgr.get("api_key")
    if not token:
        console.print("[yellow]Register first:[/] stein auth register --email you@company.com")
        raise typer.Exit(code=1)

    from steindb.auth.models import get_tier_from_token

    tier = get_tier_from_token(token)

    console.print(f"[bold]Current tier:[/] {tier.value}")
    console.print()
    console.print("[bold]Available upgrades:[/]")
    console.print("  Solo   — hosted AI inference, dashboard, PDF reports")
    console.print("  Team   — team collaboration, priority support")
    console.print()

    checkout_url = "https://app.steindb.com/upgrade"
    console.print(f"[cyan]Upgrade at:[/] {checkout_url}")

    # Try to open browser
    import webbrowser

    try:
        webbrowser.open(checkout_url)
        console.print("[green]Browser opened![/]")
    except Exception:
        console.print("Copy the URL above to upgrade in your browser.")


@app.command()
def status() -> None:
    """Show current authentication status and tier."""
    mgr = _get_config_manager()
    token = mgr.get("api_key")
    email = mgr.get("email")
    if not token:
        console.print("[yellow]Not authenticated[/]")
        console.print("Rules-only conversion works without registration.")
        console.print("Register for free to unlock AI mode: [cyan]stein auth register[/]")
        return
    from steindb.auth.models import get_tier_from_token

    tier = get_tier_from_token(token)
    console.print("[green]Authenticated[/]")
    console.print(f"  Email: {email or 'N/A'}")
    console.print(f"  Tier:  {tier.value}")
    console.print(f"  Token: {token[:15]}...{token[-5:]}")
