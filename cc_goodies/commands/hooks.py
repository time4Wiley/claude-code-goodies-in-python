"""Manage Claude global hooks configuration."""

import json
import typer
from pathlib import Path
from typing import Optional
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(stderr=True)

hooks_app = typer.Typer(
    name="hooks",
    help="Manage Claude global hooks in ~/.claude/settings.json",
    no_args_is_help=False,
)


def get_settings_path() -> Path:
    """Get the path to Claude settings file."""
    return Path.home() / ".claude" / "settings.json"


def load_settings() -> dict:
    """Load Claude settings from file."""
    settings_path = get_settings_path()
    
    if not settings_path.exists():
        return {}
    
    try:
        with open(settings_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        console.print(f"[red]Error reading settings: {e}[/red]")
        return {}


def save_settings(settings: dict) -> bool:
    """Save Claude settings to file."""
    settings_path = get_settings_path()
    
    # Ensure directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except IOError as e:
        console.print(f"[red]Error saving settings: {e}[/red]")
        return False


def get_hooks_status() -> tuple[dict, bool]:
    """Get current hooks configuration and enabled status."""
    settings = load_settings()
    hooks = settings.get("hooks", {})
    
    # Check if hooks are enabled (default to True if not specified)
    hooks_enabled = hooks.get("enabled", True) if hooks else True
    
    return hooks, hooks_enabled


@hooks_app.callback(invoke_without_command=True)
def hooks_status(ctx: typer.Context):
    """Show current hooks status (default when no subcommand given)."""
    if ctx.invoked_subcommand is not None:
        return
    
    settings_path = get_settings_path()
    hooks, hooks_enabled = get_hooks_status()
    
    # Create status table
    table = Table(title="Claude Hooks Status", show_header=True)
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    
    # Add status row
    status_str = "[green]✓ Enabled[/green]" if hooks_enabled else "[red]✗ Disabled[/red]"
    table.add_row("Status", status_str)
    
    # Add settings file location
    table.add_row("Config File", str(settings_path))
    
    # Show configured hooks if any
    if hooks:
        hook_types = [k for k in hooks.keys() if k != "enabled"]
        if hook_types:
            hooks_list = ", ".join(hook_types)
            table.add_row("Configured Hooks", hooks_list)
    
    console.print(table)
    
    # Show additional info if hooks are present
    if hooks and any(k != "enabled" for k in hooks.keys()):
        console.print("\n[dim]Use 'cc-goodies hooks --help' to see available commands[/dim]")


@hooks_app.command("enable")
def enable_hooks():
    """Enable Claude global hooks."""
    settings = load_settings()
    
    if "hooks" not in settings:
        settings["hooks"] = {}
    
    settings["hooks"]["enabled"] = True
    
    if save_settings(settings):
        console.print("[green]✓[/green] Hooks enabled successfully")
        
        # Show current hooks if any configured
        hook_types = [k for k in settings["hooks"].keys() if k != "enabled"]
        if hook_types:
            console.print(f"[dim]Active hooks: {', '.join(hook_types)}[/dim]")
    else:
        raise typer.Exit(1)


@hooks_app.command("disable")
def disable_hooks():
    """Disable Claude global hooks."""
    settings = load_settings()
    
    if "hooks" not in settings:
        settings["hooks"] = {}
    
    settings["hooks"]["enabled"] = False
    
    if save_settings(settings):
        console.print("[yellow]✗[/yellow] Hooks disabled successfully")
        console.print("[dim]Hook configurations are preserved but won't be executed[/dim]")
    else:
        raise typer.Exit(1)


@hooks_app.command("toggle")
def toggle_hooks():
    """Toggle Claude global hooks on/off."""
    settings = load_settings()
    hooks, current_enabled = get_hooks_status()
    
    # Toggle the state
    new_enabled = not current_enabled
    
    if "hooks" not in settings:
        settings["hooks"] = {}
    
    settings["hooks"]["enabled"] = new_enabled
    
    if save_settings(settings):
        if new_enabled:
            console.print("[green]✓[/green] Hooks toggled ON")
            hook_types = [k for k in settings["hooks"].keys() if k != "enabled"]
            if hook_types:
                console.print(f"[dim]Active hooks: {', '.join(hook_types)}[/dim]")
        else:
            console.print("[yellow]✗[/yellow] Hooks toggled OFF")
            console.print("[dim]Hook configurations are preserved but won't be executed[/dim]")
    else:
        raise typer.Exit(1)


if __name__ == "__main__":
    hooks_app()