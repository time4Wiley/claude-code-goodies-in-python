"""Status command using rich for beautiful terminal output."""

import os
import platform
import shutil
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich import box

console = Console()


def status_command():
    """Display system and environment status with rich formatting."""
    
    # Create main title
    console.print(Panel.fit(
        "[bold blue]Claude Code Goodies Status[/bold blue]",
        border_style="bright_blue"
    ))
    
    # System info table
    sys_table = Table(title="System Information", box=box.ROUNDED)
    sys_table.add_column("Property", style="cyan", no_wrap=True)
    sys_table.add_column("Value", style="green")
    
    sys_table.add_row("Platform", platform.system())
    sys_table.add_row("Python Version", platform.python_version())
    sys_table.add_row("User", os.environ.get("USER", "Unknown"))
    sys_table.add_row("Current Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Terminal info table
    term_table = Table(title="Terminal Information", box=box.ROUNDED)
    term_table.add_column("Property", style="cyan", no_wrap=True)
    term_table.add_column("Value", style="yellow")
    
    term_size = shutil.get_terminal_size()
    term_table.add_row("Terminal Width", str(term_size.columns))
    term_table.add_row("Terminal Height", str(term_size.lines))
    term_table.add_row("Shell", os.environ.get("SHELL", "Unknown"))
    
    # Display tables side by side
    console.print(Columns([sys_table, term_table], padding=1))
    
    # Show a fancy progress example
    console.print("\n[bold magenta]Rich Features Demo:[/bold magenta]")
    
    # Create a sample progress bar
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Loading awesome features...", total=None)
        import time
        time.sleep(1)
        progress.update(task, description="[green]✓ Features loaded!")
    
    # Success message
    console.print(Panel(
        "[bold green]✨ Rich is working perfectly![/bold green]\n"
        "[dim]Try other cc-goodies commands for more tools.[/dim]",
        border_style="green",
        box=box.DOUBLE
    ))


if __name__ == "__main__":
    status_command()