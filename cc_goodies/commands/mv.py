"""Move Claude Code managed projects to new locations."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()


def path_to_claude_project_name(path: str) -> str:
    """Convert filesystem path to Claude Code project name format.
    
    All non-alphanumeric characters are replaced with hyphens.
    Example: /Users/wei/Projects/my-app -> -Users-wei-Projects-my-app
    """
    return re.sub(r'[^a-zA-Z0-9]', '-', path)


def is_claude_managed(path: str) -> bool:
    """Check if a directory is managed by Claude Code.
    
    A directory is considered Claude-managed if it has a corresponding
    entry in ~/.claude/projects/.
    """
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    project_name = path_to_claude_project_name(path)
    project_path = os.path.join(claude_projects_dir, project_name)
    return os.path.isdir(project_path)


def check_destination(destination: str) -> str:
    """Check destination status and return its type.
    
    Returns:
        'file' if destination exists as a file
        'directory' if destination exists as a directory
        'none' if destination doesn't exist
    """
    if os.path.exists(destination):
        if os.path.isfile(destination):
            return 'file'
        elif os.path.isdir(destination):
            return 'directory'
    return 'none'


def determine_final_path(source: str, destination: str, dest_type: str) -> str:
    """Determine the final path based on destination type.
    
    Args:
        source: Source directory path
        destination: Destination path
        dest_type: Type of destination ('file', 'directory', 'none')
    
    Returns:
        Final path where the source will end up
    """
    source_name = os.path.basename(source)
    
    if dest_type == 'directory':
        # Move source into destination directory
        return os.path.join(destination, source_name)
    else:
        # Destination doesn't exist - use as-is
        return destination


def move_filesystem_directory(source: str, destination: str, dry_run: bool = False) -> bool:
    """Move the actual filesystem directory.
    
    Args:
        source: Source directory path
        destination: Destination directory path
        dry_run: If True, only preview changes
    
    Returns:
        True if successful, False otherwise
    """
    # Check if source exists
    if not os.path.exists(source):
        console.print(f"[red]Source directory does not exist: {source}[/red]")
        return False
    
    # Check if already at destination
    if os.path.exists(destination):
        try:
            if os.path.samefile(source, destination):
                console.print(f"[yellow]Directory already at target location[/yellow]")
                return True
        except FileNotFoundError:
            pass
    
    # Check if destination already exists
    if os.path.exists(destination):
        console.print(f"[red]Target path already exists: {destination}[/red]")
        return False
    
    if dry_run:
        console.print(f"[cyan]Would move directory:[/cyan]")
        console.print(f"  From: {source}")
        console.print(f"  To:   {destination}")
        return True
    
    try:
        # Create parent directory if needed
        parent_dir = os.path.dirname(destination)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            console.print(f"[green]✓[/green] Created parent directory: {parent_dir}")
        
        # Use shutil.move for cross-device compatibility
        shutil.move(source, destination)
        console.print(f"[green]✓[/green] Directory moved successfully")
        return True
    except Exception as e:
        console.print(f"[red]Failed to move directory: {e}[/red]")
        return False


def update_claude_project(old_path: str, new_path: str, dry_run: bool = False) -> bool:
    """Update Claude Code project mapping to reflect new location.
    
    Args:
        old_path: Original project path
        new_path: New project path
        dry_run: If True, only preview changes
    
    Returns:
        True if successful, False otherwise
    """
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    
    old_project_name = path_to_claude_project_name(old_path)
    new_project_name = path_to_claude_project_name(new_path)
    
    old_project_path = os.path.join(claude_projects_dir, old_project_name)
    new_project_path = os.path.join(claude_projects_dir, new_project_name)
    
    # Check if source project exists
    if not os.path.exists(old_project_path):
        console.print(f"[yellow]Claude project not found: {old_project_name}[/yellow]")
        console.print(f"[dim]This project may not have been managed by Claude Code[/dim]")
        return False
    
    # Check if target already exists
    if os.path.exists(new_project_path):
        if old_project_path == new_project_path:
            console.print(f"[yellow]Claude project already has correct mapping[/yellow]")
            return True
        console.print(f"[red]Target Claude project already exists: {new_project_name}[/red]")
        return False
    
    if dry_run:
        console.print(f"[cyan]Would update Claude project mapping:[/cyan]")
        console.print(f"  From: {old_project_name}")
        console.print(f"  To:   {new_project_name}")
        return True
    
    try:
        shutil.move(old_project_path, new_project_path)
        console.print(f"[green]✓[/green] Claude project mapping updated")
        return True
    except Exception as e:
        console.print(f"[red]Failed to update Claude project: {e}[/red]")
        return False


def mv_command(
    source: Path = typer.Argument(
        ...,
        help="Source directory (must be Claude Code managed)"
    ),
    destination: Path = typer.Argument(
        ...,
        help="Destination path"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without making them"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts"
    ),
    no_claude_update: bool = typer.Option(
        False,
        "--no-claude-update",
        help="Skip updating Claude project mapping"
    ),
):
    """
    Move a Claude Code managed project to a new location.
    
    This command moves a project directory and updates its Claude Code project mapping.
    
    Behavior based on destination:
    - If destination exists as a directory: moves source into it
    - If destination doesn't exist: moves source to that path
    - If destination exists as a file: aborts with warning
    
    Examples:
        # Move project to different parent directory
        cc-goodies mv my-project /Users/wei/NewProjects/
        
        # Move and rename in one operation
        cc-goodies mv old-project /Users/wei/Projects/new-project
        
        # Preview changes without making them
        cc-goodies mv --dry-run my-project ../other-location/
    """
    
    # Resolve paths
    source_path = os.path.abspath(source)
    destination_path = os.path.abspath(destination)
    
    # Validate source
    if not os.path.exists(source_path):
        console.print(f"[red]Error: Source path does not exist: {source_path}[/red]")
        raise typer.Exit(1)
    
    if not os.path.isdir(source_path):
        console.print(f"[red]Error: Source must be a directory, not a file: {source_path}[/red]")
        raise typer.Exit(1)
    
    if not is_claude_managed(source_path):
        console.print(f"[red]Error: Source is not a Claude Code managed project[/red]")
        console.print(f"[dim]No project entry found in ~/.claude/projects/ for: {source_path}[/dim]")
        if not force:
            console.print(f"[dim]Use --force to move anyway (Claude project mapping won't be updated)[/dim]")
            raise typer.Exit(1)
        else:
            console.print(f"[yellow]Warning: Proceeding without Claude project update (--force used)[/yellow]")
            no_claude_update = True
    
    # Check destination
    dest_type = check_destination(destination_path)
    
    if dest_type == 'file':
        console.print(f"[red]Error: Destination exists as a file: {destination_path}[/red]")
        console.print(f"[dim]Cannot move directory to a file location[/dim]")
        raise typer.Exit(1)
    
    # Determine final path
    final_path = determine_final_path(source_path, destination_path, dest_type)
    
    # Check if final path already exists
    if os.path.exists(final_path) and final_path != source_path:
        console.print(f"[red]Error: Target location already exists: {final_path}[/red]")
        raise typer.Exit(1)
    
    # Check for moving into subdirectory of itself
    if final_path.startswith(source_path + os.sep):
        console.print(f"[red]Error: Cannot move directory into its own subdirectory[/red]")
        raise typer.Exit(1)
    
    # Create summary table
    table = Table(title="Move Operation Summary", box=box.ROUNDED)
    table.add_column("Component", style="cyan")
    table.add_column("Current", style="yellow")
    table.add_column("New", style="green")
    
    # Directory move
    table.add_row(
        "Directory",
        source_path,
        final_path
    )
    
    # Claude project update
    if not no_claude_update:
        table.add_row(
            "Claude Project",
            path_to_claude_project_name(source_path),
            path_to_claude_project_name(final_path)
        )
    
    console.print(table)
    
    if dry_run:
        console.print("\n[cyan]DRY RUN MODE - No changes will be made[/cyan]")
    
    # Confirmation
    if not dry_run and not force:
        if not typer.confirm("\nProceed with move operation?"):
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit(0)
    
    # Perform operations
    console.print()
    success = True
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        
        # Move the filesystem directory
        task = progress.add_task("Moving directory...", total=None)
        result = move_filesystem_directory(source_path, final_path, dry_run)
        if not result:
            success = False
            console.print("[red]Failed to move directory. Stopping operation.[/red]")
            progress.update(task, completed=True)
            raise typer.Exit(1)
        progress.update(task, completed=True)
        
        # Update Claude project mapping
        if not no_claude_update:
            task = progress.add_task("Updating Claude project...", total=None)
            result = update_claude_project(source_path, final_path, dry_run)
            if not result:
                success = False
                console.print("[yellow]Warning: Claude project mapping not updated[/yellow]")
                console.print("[dim]You may need to manually update or recreate the Claude project[/dim]")
            progress.update(task, completed=True)
    
    # Final status
    console.print()
    if dry_run:
        console.print(Panel(
            "[cyan]Dry run completed. Review the changes above.[/cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
    elif success:
        console.print(Panel(
            f"[bold green]✨ Successfully moved project![/bold green]\n"
            f"[dim]New location: {final_path}[/dim]",
            border_style="green",
            box=box.DOUBLE
        ))
        
        # Show helpful cd command
        console.print(f"\n[cyan]To enter the moved project:[/cyan]")
        # Always quote the path for shell safety
        console.print(f'[cyan]   cd "{final_path}"[/cyan]')
    else:
        console.print(Panel(
            "[yellow]⚠️  Move completed with warnings[/yellow]\n"
            "[dim]Check the messages above for details.[/dim]",
            border_style="yellow",
            box=box.DOUBLE
        ))


if __name__ == "__main__":
    # For testing
    typer.run(mv_command)