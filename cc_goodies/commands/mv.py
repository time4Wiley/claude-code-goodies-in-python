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


def find_all_claude_projects(root_path: str) -> list[dict]:
    """Recursively find all Claude-managed projects within root_path.
    
    Args:
        root_path: Root directory to search within
        
    Returns:
        List of dicts with keys: 'path', 'project_name', 'relative_path'
        Example: [{'path': '/full/path', 'project_name': '-full-path', 'relative_path': 'subdir'}]
    """
    found_projects = []
    root_path = os.path.abspath(root_path)
    
    if not os.path.exists(root_path):
        return found_projects
        
    # Check root directory first
    if is_claude_managed(root_path):
        found_projects.append({
            'path': root_path,
            'project_name': path_to_claude_project_name(root_path),
            'relative_path': '.'
        })
    
    # Recursively check all subdirectories
    try:
        for dirpath, dirnames, _ in os.walk(root_path):
            # Skip the root directory (already checked above)
            if dirpath == root_path:
                continue
                
            if is_claude_managed(dirpath):
                relative_path = os.path.relpath(dirpath, root_path)
                found_projects.append({
                    'path': dirpath,
                    'project_name': path_to_claude_project_name(dirpath),
                    'relative_path': relative_path
                })
    except (PermissionError, OSError) as e:
        console.print(f"[yellow]Warning: Could not scan some directories: {e}[/yellow]")
    
    return found_projects


def validate_all_project_updates(projects: list[dict], old_root: str, new_root: str) -> tuple[bool, list[str]]:
    """Validate that all project updates can be performed safely.
    
    Args:
        projects: List of project dicts from find_all_claude_projects()
        old_root: Original root path
        new_root: New root path
        
    Returns:
        Tuple of (success: bool, errors: list[str])
    """
    errors = []
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    
    for project in projects:
        old_path = project['path']
        relative_path = project['relative_path']
        
        # Calculate new path
        if relative_path == '.':
            new_path = new_root
        else:
            new_path = os.path.join(new_root, relative_path)
        
        old_project_name = path_to_claude_project_name(old_path)
        new_project_name = path_to_claude_project_name(new_path)
        
        old_project_path = os.path.join(claude_projects_dir, old_project_name)
        new_project_path = os.path.join(claude_projects_dir, new_project_name)
        
        # Validate source exists
        if not os.path.exists(old_project_path):
            errors.append(f"Source project missing: {old_project_name}")
            
        # Validate target doesn't exist (unless it's the same)
        if os.path.exists(new_project_path) and old_project_path != new_project_path:
            errors.append(f"Target project already exists: {new_project_name}")
    
    return len(errors) == 0, errors


def update_all_claude_projects(old_root: str, new_root: str, dry_run: bool = False) -> bool:
    """Update all Claude-managed projects within a directory tree.
    
    Args:
        old_root: Original root directory path
        new_root: New root directory path  
        dry_run: If True, only preview changes
        
    Returns:
        True if all updates successful, False otherwise
    """
    # Find all Claude projects
    console.print(f"[cyan]Scanning for Claude-managed projects in: {old_root}[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Scanning directories...", total=None)
        projects = find_all_claude_projects(old_root)
        progress.stop()
    
    if not projects:
        console.print("[yellow]No Claude-managed projects found in directory tree[/yellow]")
        return True
    
    # Show what was found
    console.print(f"[green]Found {len(projects)} Claude-managed project(s):[/green]")
    
    table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    table.add_column("Relative Path")
    table.add_column("Claude Project Name")
    table.add_column("Action")
    
    for project in projects:
        relative_path = project['relative_path']
        old_path = project['path']
        
        # Calculate new path
        if relative_path == '.':
            new_path = new_root
        else:
            new_path = os.path.join(new_root, relative_path)
            
        new_project_name = path_to_claude_project_name(new_path)
        
        if dry_run:
            action = f"Would update: {project['project_name']} → {new_project_name}"
        else:
            action = f"Update: {project['project_name']} → {new_project_name}"
            
        table.add_row(relative_path, project['project_name'], action)
    
    console.print(table)
    
    if dry_run:
        return True
    
    # Validate all updates before proceeding  
    valid, errors = validate_all_project_updates(projects, old_root, new_root)
    if not valid:
        console.print("[red]Cannot proceed with updates due to conflicts:[/red]")
        for error in errors:
            console.print(f"  • {error}")
        return False
    
    # Perform all updates
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    successful_updates = []
    failed_updates = []
    
    for project in projects:
        old_path = project['path']
        relative_path = project['relative_path']
        
        # Calculate new path
        if relative_path == '.':
            new_path = new_root
        else:
            new_path = os.path.join(new_root, relative_path)
        
        old_project_name = path_to_claude_project_name(old_path)
        new_project_name = path_to_claude_project_name(new_path)
        
        old_project_path = os.path.join(claude_projects_dir, old_project_name)
        new_project_path = os.path.join(claude_projects_dir, new_project_name)
        
        try:
            shutil.move(old_project_path, new_project_path)
            successful_updates.append(project)
            console.print(f"[green]✓[/green] Updated: {relative_path}")
        except Exception as e:
            failed_updates.append((project, str(e)))
            console.print(f"[red]✗[/red] Failed: {relative_path} - {e}")
    
    # Summary
    if successful_updates and not failed_updates:
        console.print(f"[green]✓ Successfully updated {len(successful_updates)} Claude project(s)[/green]")
        return True
    elif failed_updates:
        console.print(f"[red]✗ {len(failed_updates)} update(s) failed[/red]")
        if successful_updates:
            console.print(f"[yellow]⚠ {len(successful_updates)} update(s) succeeded (partial success)[/yellow]")
        return False
    
    return True

class TransactionManager:
    """Manages transaction state and rollback operations for mv/rename commands."""
    
    def __init__(self):
        self.operations = []
        self.completed_operations = []
        self.rollback_info = []
        
    def add_operation(self, operation_type: str, source: str, target: str, metadata: dict = None):
        """Add an operation to the transaction.
        
        Args:
            operation_type: Type of operation ('move_directory', 'rename_claude_project')
            source: Source path/name
            target: Target path/name
            metadata: Additional operation metadata
        """
        operation = {
            'type': operation_type,
            'source': source,
            'target': target,
            'metadata': metadata or {},
            'completed': False,
            'rollback_data': None
        }
        self.operations.append(operation)
        
    def validate_all_operations(self) -> tuple[bool, list[str]]:
        """Validate that all operations can be performed safely.
        
        Returns:
            Tuple of (success: bool, errors: list[str])
        """
        errors = []
        
        # Check for conflicts between operations
        targets = set()
        for op in self.operations:
            if op['target'] in targets:
                errors.append(f"Conflict: Multiple operations target {op['target']}")
            targets.add(op['target'])
            
            # Validate specific operation types
            if op['type'] == 'move_directory':
                if not os.path.exists(op['source']):
                    errors.append(f"Source directory missing: {op['source']}")
                if os.path.exists(op['target']) and op['source'] != op['target']:
                    errors.append(f"Target directory already exists: {op['target']}")
                    
            elif op['type'] == 'rename_claude_project':
                claude_projects_dir = os.path.expanduser("~/.claude/projects")
                source_path = os.path.join(claude_projects_dir, op['source'])
                target_path = os.path.join(claude_projects_dir, op['target'])
                
                if not os.path.exists(source_path):
                    errors.append(f"Claude project missing: {op['source']}")
                if os.path.exists(target_path) and source_path != target_path:
                    errors.append(f"Target Claude project already exists: {op['target']}")
        
        return len(errors) == 0, errors
        
    def execute_operation(self, operation: dict, dry_run: bool = False) -> bool:
        """Execute a single operation and prepare rollback data.
        
        Args:
            operation: Operation dictionary
            dry_run: If True, only simulate the operation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if operation['type'] == 'move_directory':
                return self._execute_move_directory(operation, dry_run)
            elif operation['type'] == 'rename_claude_project':
                return self._execute_rename_claude_project(operation, dry_run)
            else:
                console.print(f"[red]Unknown operation type: {operation['type']}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Operation failed: {e}[/red]")
            return False
            
    def _execute_move_directory(self, operation: dict, dry_run: bool = False) -> bool:
        """Execute directory move operation."""
        source = operation['source']
        target = operation['target']
        
        if dry_run:
            console.print(f"[cyan]Would move directory:[/cyan] {source} → {target}")
            operation['completed'] = True
            return True
            
        # Check if already at target location
        if os.path.exists(target):
            try:
                if os.path.samefile(source, target):
                    console.print(f"[yellow]Directory already at target location[/yellow]")
                    operation['completed'] = True
                    operation['rollback_data'] = {'action': 'none'}
                    return True
            except FileNotFoundError:
                pass
                
        # Prepare rollback data before operation
        operation['rollback_data'] = {
            'action': 'move_back',
            'original_source': source,
            'original_target': target
        }
        
        # Create parent directory if needed
        parent_dir = os.path.dirname(target)
        created_parent = False
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            created_parent = True
            operation['rollback_data']['created_parent'] = parent_dir
            console.print(f"[green]✓[/green] Created parent directory: {parent_dir}")
        
        # Perform the move
        shutil.move(source, target)
        operation['completed'] = True
        console.print(f"[green]✓[/green] Directory moved successfully")
        
        return True
        
    def _execute_rename_claude_project(self, operation: dict, dry_run: bool = False) -> bool:
        """Execute Claude project rename operation."""
        source_name = operation['source']
        target_name = operation['target']
        
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        source_path = os.path.join(claude_projects_dir, source_name)
        target_path = os.path.join(claude_projects_dir, target_name)
        
        if dry_run:
            console.print(f"[cyan]Would rename Claude project:[/cyan] {source_name} → {target_name}")
            operation['completed'] = True
            return True
            
        # Check if already renamed
        if not os.path.exists(source_path) and os.path.exists(target_path):
            console.print(f"[yellow]Claude project appears to be already renamed[/yellow]")
            operation['completed'] = True
            operation['rollback_data'] = {'action': 'none'}
            return True
            
        # Prepare rollback data
        operation['rollback_data'] = {
            'action': 'move_back',
            'original_source': source_path,
            'original_target': target_path
        }
        
        # Perform the rename
        shutil.move(source_path, target_path)
        operation['completed'] = True
        console.print(f"[green]✓[/green] Claude project renamed: {source_name} → {target_name}")
        
        return True
        
    def execute_all_operations(self, dry_run: bool = False) -> bool:
        """Execute all operations in transaction.
        
        Args:
            dry_run: If True, only simulate operations
            
        Returns:
            True if all operations successful, False otherwise
        """
        if dry_run:
            console.print("[cyan]DRY RUN: Executing all operations...[/cyan]")
            for operation in self.operations:
                if not self.execute_operation(operation, dry_run=True):
                    return False
            return True
            
        # Validate all operations first
        valid, errors = self.validate_all_operations()
        if not valid:
            console.print("[red]Transaction validation failed:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            return False
            
        # Execute operations
        for i, operation in enumerate(self.operations):
            console.print(f"[cyan]Executing operation {i+1}/{len(self.operations)}...[/cyan]")
            
            if not self.execute_operation(operation, dry_run=False):
                console.print(f"[red]Operation {i+1} failed. Rolling back...[/red]")
                self.rollback()
                return False
                
            self.completed_operations.append(operation)
            
        return True
        
    def rollback(self):
        """Rollback all completed operations in reverse order."""
        console.print("[yellow]🔄 Rolling back operations...[/yellow]")
        
        # Rollback in reverse order
        for operation in reversed(self.completed_operations):
            try:
                self._rollback_operation(operation)
            except Exception as e:
                console.print(f"[red]Failed to rollback operation: {e}[/red]")
                console.print(f"[yellow]Manual cleanup may be required for: {operation}[/yellow]")
                
        self.completed_operations.clear()
        console.print("[yellow]Rollback completed[/yellow]")
        
    def _rollback_operation(self, operation: dict):
        """Rollback a single operation."""
        rollback_data = operation.get('rollback_data', {})
        action = rollback_data.get('action')
        
        if action == 'none':
            return
            
        elif action == 'move_back':
            # Move back from target to source
            original_source = rollback_data['original_source']
            original_target = rollback_data['original_target']
            
            if os.path.exists(original_target):
                shutil.move(original_target, original_source)
                console.print(f"[green]✓[/green] Rolled back: {original_target} → {original_source}")
                
            # Remove created parent directory if it's empty
            if 'created_parent' in rollback_data:
                created_parent = rollback_data['created_parent']
                try:
                    if os.path.exists(created_parent) and not os.listdir(created_parent):
                        os.rmdir(created_parent)
                        console.print(f"[green]✓[/green] Removed empty parent directory: {created_parent}")
                except OSError:
                    pass  # Directory not empty, leave it
                    
        operation['completed'] = False
        
    def get_summary(self) -> dict:
        """Get transaction summary."""
        return {
            'total_operations': len(self.operations),
            'completed_operations': len(self.completed_operations),
            'pending_operations': len(self.operations) - len(self.completed_operations),
            'operations': self.operations
        }


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
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        help="Update all nested Claude projects (default: True)"
    ),
):
    """
    Move a Claude Code managed project to a new location.
    
    This command moves a project directory and updates its Claude Code project mapping.
    By default, it recursively handles all nested Claude-managed projects within the source.
    
    Behavior based on destination:
    - If destination exists as a directory: moves source into it
    - If destination doesn't exist: moves source to that path
    - If destination exists as a file: aborts with warning
    
    Examples:
        # Move project to different parent directory (with nested projects)
        cc-goodies mv my-project /Users/wei/NewProjects/
        
        # Move and rename in one operation
        cc-goodies mv old-project /Users/wei/Projects/new-project
        
        # Move only the main project, skip nested ones
        cc-goodies mv --no-recursive my-project ../other-location/
        
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
    
    # Check if main source is Claude managed
    source_is_claude_managed = is_claude_managed(source_path)
    
    if not source_is_claude_managed and not recursive:
        console.print(f"[red]Error: Source is not a Claude Code managed project[/red]")
        console.print(f"[dim]No project entry found in ~/.claude/projects/ for: {source_path}[/dim]")
        if not force:
            console.print(f"[dim]Use --force to move anyway (Claude project mapping won't be updated)[/dim]")
            console.print(f"[dim]Or use --recursive to check for nested Claude projects[/dim]")
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
    
    # Pre-scan for Claude projects if recursive mode is enabled
    projects_to_update = []
    if not no_claude_update and recursive:
        console.print(f"[cyan]Scanning for Claude-managed projects...[/cyan]")
        projects_to_update = find_all_claude_projects(source_path)
        
        if not projects_to_update and not source_is_claude_managed:
            console.print(f"[yellow]Warning: No Claude-managed projects found in directory tree[/yellow]")
            if not force:
                console.print(f"[dim]Use --force to move anyway, or --no-recursive for single project mode[/dim]")
                raise typer.Exit(1)
            else:
                console.print(f"[yellow]Proceeding anyway (--force used)[/yellow]")
                no_claude_update = True
    elif not no_claude_update and source_is_claude_managed:
        # Single project mode - create a single project entry
        projects_to_update = [{
            'path': source_path,
            'project_name': path_to_claude_project_name(source_path),
            'relative_path': '.'
        }]
    
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
    
    # Claude project updates
    if not no_claude_update and projects_to_update:
        if len(projects_to_update) == 1 and projects_to_update[0]['relative_path'] == '.':
            # Single main project
            table.add_row(
                "Claude Project",
                projects_to_update[0]['project_name'],
                path_to_claude_project_name(final_path)
            )
        else:
            # Multiple or nested projects
            table.add_row(
                "Claude Projects",
                f"{len(projects_to_update)} project(s) found",
                "All will be updated recursively"
            )
    elif no_claude_update:
        table.add_row(
            "Claude Projects",
            "[yellow]Skipped[/yellow]",
            "[dim]--no-claude-update specified[/dim]"
        )
    
    console.print(table)
    
    # Show detailed project list if multiple projects
    if not no_claude_update and len(projects_to_update) > 1:
        console.print(f"\n[green]Found {len(projects_to_update)} Claude-managed project(s):[/green]")
        
        detail_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        detail_table.add_column("Relative Path")
        detail_table.add_column("Current Project Name", overflow="fold")
        detail_table.add_column("New Project Name", overflow="fold")
        
        for project in projects_to_update:
            relative_path = project['relative_path']
            old_path = project['path']
            
            # Calculate new path
            if relative_path == '.':
                new_path = final_path
            else:
                new_path = os.path.join(final_path, relative_path)
                
            new_project_name = path_to_claude_project_name(new_path)
            detail_table.add_row(relative_path, project['project_name'], new_project_name)
        
        console.print(detail_table)
    
    if dry_run:
        console.print("\n[cyan]DRY RUN MODE - No changes will be made[/cyan]")
    
    # Confirmation
    if not dry_run and not force:
        confirmation_msg = "\nProceed with move operation?"
        if len(projects_to_update) > 1:
            confirmation_msg = f"\nProceed with move operation (will update {len(projects_to_update)} Claude projects)?"
        
        if not typer.confirm(confirmation_msg):
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
        
        # Update Claude project mappings (recursive or single)
        if not no_claude_update and projects_to_update:
            task = progress.add_task("Updating Claude projects...", total=None)
            
            if recursive and len(projects_to_update) > 1:
                # Use recursive update function
                result = update_all_claude_projects(source_path, final_path, dry_run)
            elif len(projects_to_update) == 1:
                # Use single project update function
                result = update_claude_project(source_path, final_path, dry_run)
            else:
                result = True
            
            if not result:
                success = False
                console.print("[yellow]Warning: Some Claude project mappings not updated[/yellow]")
                console.print("[dim]You may need to manually update or recreate affected Claude projects[/dim]")
            
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
        success_msg = f"[bold green]✨ Successfully moved project![/bold green]\n[dim]New location: {final_path}[/dim]"
        if len(projects_to_update) > 1:
            success_msg = f"[bold green]✨ Successfully moved project tree![/bold green]\n[dim]New location: {final_path}[/dim]\n[dim]Updated {len(projects_to_update)} Claude project(s)[/dim]"
        
        console.print(Panel(
            success_msg,
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