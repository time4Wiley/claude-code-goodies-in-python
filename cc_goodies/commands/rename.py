"""Rename Claude Code managed projects and their remote repositories."""

import os
import re
import shutil
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from configparser import ConfigParser

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
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    project_name = path_to_claude_project_name(root_path)
    project_path = os.path.join(claude_projects_dir, project_name)
    
    if os.path.isdir(project_path):
        found_projects.append({
            'path': root_path,
            'project_name': project_name,
            'relative_path': '.'
        })
    
    # Recursively check all subdirectories
    try:
        for dirpath, dirnames, _ in os.walk(root_path):
            # Skip the root directory (already checked above)
            if dirpath == root_path:
                continue
                
            project_name = path_to_claude_project_name(dirpath)
            project_path = os.path.join(claude_projects_dir, project_name)
            
            if os.path.isdir(project_path):
                relative_path = os.path.relpath(dirpath, root_path)
                found_projects.append({
                    'path': dirpath,
                    'project_name': project_name,
                    'relative_path': relative_path
                })
    except (PermissionError, OSError) as e:
        console.print(f"[yellow]Warning: Could not scan some directories: {e}[/yellow]")
    
    return found_projects


def validate_all_project_renames(projects: list[dict], old_root: str, new_root: str, new_name: str = None) -> tuple[bool, list[str]]:
    """Validate that all project renames can be performed safely.
    
    Args:
        projects: List of project dicts from find_all_claude_projects()
        old_root: Original root path
        new_root: New root path (for rename in place) 
        new_name: New project name (for rename with name change)
        
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
            # Root project - use new_root and new_name if provided
            if new_name:
                new_path = os.path.join(os.path.dirname(old_root), new_name)
            else:
                new_path = new_root
        else:
            # Nested project - maintain relative structure
            if new_name and old_root in old_path:
                # Replace old root name with new name in the path
                old_root_name = os.path.basename(old_root)
                new_path = old_path.replace(old_root_name, new_name if new_name else old_root_name, 1)
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


def rename_all_claude_projects(old_root: str, new_root: str, new_name: str = None, dry_run: bool = False) -> bool:
    """Rename all Claude-managed projects within a directory tree.
    
    Args:
        old_root: Original root directory path
        new_root: New root directory path  
        new_name: New project name (if renaming root project)
        dry_run: If True, only preview changes
        
    Returns:
        True if all renames successful, False otherwise
    """
    # Find all Claude projects
    console.print(f"[cyan]Scanning for Claude-managed projects in: {old_root}[/cyan]")
    
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
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
    
    from rich.table import Table
    from rich import box
    
    table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    table.add_column("Relative Path")
    table.add_column("Claude Project Name")
    table.add_column("Action")
    
    for project in projects:
        relative_path = project['relative_path']
        old_path = project['path']
        
        # Calculate new path 
        if relative_path == '.':
            # Root project
            if new_name:
                new_path = os.path.join(os.path.dirname(old_root), new_name)
            else:
                new_path = new_root
        else:
            # Nested project - maintain relative structure
            if new_name and old_root in old_path:
                old_root_name = os.path.basename(old_root)
                new_path = old_path.replace(old_root_name, new_name if new_name else old_root_name, 1)
            else:
                new_path = os.path.join(new_root, relative_path)
            
        new_project_name = path_to_claude_project_name(new_path)
        
        if dry_run:
            action = f"Would rename: {project['project_name']} → {new_project_name}"
        else:
            action = f"Rename: {project['project_name']} → {new_project_name}"
            
        table.add_row(relative_path, project['project_name'], action)
    
    console.print(table)
    
    if dry_run:
        return True
    
    # Validate all renames before proceeding  
    valid, errors = validate_all_project_renames(projects, old_root, new_root, new_name)
    if not valid:
        console.print("[red]Cannot proceed with renames due to conflicts:[/red]")
        for error in errors:
            console.print(f"  • {error}")
        return False
    
    # Perform all renames
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    successful_renames = []
    failed_renames = []
    
    for project in projects:
        old_path = project['path']
        relative_path = project['relative_path']
        
        # Calculate new path
        if relative_path == '.':
            if new_name:
                new_path = os.path.join(os.path.dirname(old_root), new_name)
            else:
                new_path = new_root
        else:
            if new_name and old_root in old_path:
                old_root_name = os.path.basename(old_root)
                new_path = old_path.replace(old_root_name, new_name if new_name else old_root_name, 1)
            else:
                new_path = os.path.join(new_root, relative_path)
        
        old_project_name = path_to_claude_project_name(old_path)
        new_project_name = path_to_claude_project_name(new_path)
        
        old_project_path = os.path.join(claude_projects_dir, old_project_name)
        new_project_path = os.path.join(claude_projects_dir, new_project_name)
        
        try:
            shutil.move(old_project_path, new_project_path)
            successful_renames.append(project)
            console.print(f"[green]✓[/green] Renamed: {relative_path}")
        except Exception as e:
            failed_renames.append((project, str(e)))
            console.print(f"[red]✗[/red] Failed: {relative_path} - {e}")
    
    # Summary
    if successful_renames and not failed_renames:
        console.print(f"[green]✓ Successfully renamed {len(successful_renames)} Claude project(s)[/green]")
        return True
    elif failed_renames:
        console.print(f"[red]✗ {len(failed_renames)} rename(s) failed[/red]")
        if successful_renames:
            console.print(f"[yellow]⚠ {len(successful_renames)} rename(s) succeeded (partial success)[/yellow]")
        return False
    
    return True


def load_gogs_config(config_path: str = "~/.gogs-rc") -> Dict[str, str]:
    """Load Gogs configuration from shell script."""
    config_path = os.path.expanduser(config_path)
    config = {}
    
    if not os.path.exists(config_path):
        return config
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line.startswith('#') or not line:
                    continue
                # Parse export statements
                if line.startswith('export '):
                    line = line[7:]
                # Parse KEY=VALUE pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    config[key] = value
    except Exception as e:
        console.print(f"[yellow]Warning: Could not parse Gogs config: {e}[/yellow]")
    
    return config


def check_gh_auth() -> bool:
    """Check if gh CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_git_remotes() -> Dict[str, str]:
    """Get all git remotes and their URLs."""
    remotes = {}
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.strip().split('\n'):
            if line and '\t' in line:
                name, url = line.split('\t')
                url = url.split(' ')[0]  # Remove (fetch) or (push)
                remotes[name] = url
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return remotes


def get_current_repo_name() -> Optional[str]:
    """Get the current repository name from git remotes."""
    remotes = get_git_remotes()
    
    # Try to extract from origin or github remote
    for remote_name in ['origin', 'github', 'gogs']:
        if remote_name in remotes:
            url = remotes[remote_name]
            # Extract repo name from various URL formats
            # SSH: git@github.com:user/repo.git
            # HTTPS: https://github.com/user/repo.git
            # Gogs HTTP: http://user@host:port/user/repo.git
            # Gogs SSH: ssh://git@host:port/user/repo.git
            
            # Remove .git suffix
            if url.endswith('.git'):
                url = url[:-4]
            
            # Extract the last part after the last /
            repo_name = url.split('/')[-1]
            
            # For SSH format like git@github.com:user/repo
            if ':' in repo_name and '@' not in repo_name:
                repo_name = repo_name.split(':')[-1]
            
            return repo_name
    
    return None


def rename_filesystem_directory(old_path: str, new_path: str, dry_run: bool = False) -> bool:
    """Rename the actual filesystem directory.
    
    Args:
        old_path: Current directory path
        new_path: New directory path
        dry_run: If True, only preview changes
    
    Returns:
        True if successful, False otherwise
    """
    # Check if source exists
    if not os.path.exists(old_path):
        console.print(f"[red]Directory does not exist: {old_path}[/red]")
        return False
    
    # Check if target already exists
    if os.path.exists(new_path):
        if os.path.samefile(old_path, new_path):
            console.print(f"[yellow]Directory already at target location[/yellow]")
            return True
        console.print(f"[red]Target directory already exists: {new_path}[/red]")
        return False
    
    if dry_run:
        console.print(f"[cyan]Would rename directory:[/cyan] {old_path} → {new_path}")
        return True
    
    try:
        # Use shutil.move for cross-device compatibility
        shutil.move(old_path, new_path)
        console.print(f"[green]✓[/green] Directory renamed successfully")
        return True
    except Exception as e:
        console.print(f"[red]Failed to rename directory: {e}[/red]")
        return False


def rename_claude_project(old_path: str, new_path: str, dry_run: bool = False, check_reverse: bool = True) -> bool:
    """Rename Claude Code project directory.
    
    Args:
        old_path: Original project path
        new_path: New project path
        dry_run: If True, only preview changes
        check_reverse: If True, check if project was already renamed (for recovery)
    
    Returns:
        True if successful or already renamed, False otherwise
    """
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    
    old_project_name = path_to_claude_project_name(old_path)
    new_project_name = path_to_claude_project_name(new_path)
    
    old_project_path = os.path.join(claude_projects_dir, old_project_name)
    new_project_path = os.path.join(claude_projects_dir, new_project_name)
    
    # Check if already renamed (for recovery from partial rename)
    if check_reverse and not os.path.exists(old_project_path) and os.path.exists(new_project_path):
        console.print(f"[yellow]Claude project appears to be already renamed[/yellow]")
        return True
    
    # Check if source exists
    if not os.path.exists(old_project_path):
        console.print(f"[yellow]Claude project not found: {old_project_name}[/yellow]")
        # Could be already renamed or doesn't exist
        if check_reverse and os.path.exists(new_project_path):
            console.print(f"[green]But target project exists, assuming already renamed[/green]")
            return True
        return False
    
    # Check if target already exists
    if os.path.exists(new_project_path):
        console.print(f"[red]Target Claude project already exists: {new_project_name}[/red]")
        return False
    
    if dry_run:
        console.print(f"[cyan]Would rename:[/cyan] {old_project_name} → {new_project_name}")
        return True
    
    try:
        shutil.move(old_project_path, new_project_path)
        console.print(f"[green]✓[/green] Claude project renamed successfully")
        return True
    except Exception as e:
        console.print(f"[red]Failed to rename Claude project: {e}[/red]")
        return False


def rename_github_repo(old_name: str, new_name: str, dry_run: bool = False, skip_ownership_check: bool = False) -> bool:
    """Rename repository on GitHub using gh CLI."""
    if not check_gh_auth():
        console.print("[yellow]GitHub CLI not authenticated. Run 'gh auth login' first.[/yellow]")
        return False
    
    # Check if repo exists on GitHub and get owner info
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "name,owner,viewerCanAdminister"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            console.print("[yellow]Repository not found on GitHub or no access[/yellow]")
            return False
        
        # Parse the repo info
        try:
            repo_info = json.loads(result.stdout)
            owner_login = repo_info.get('owner', {}).get('login', '')
            can_administer = repo_info.get('viewerCanAdminister', False)
            
            # Check if we can rename (must be owner or have admin rights)
            # But allow skipping this check with a flag
            if not skip_ownership_check:
                current_user_result = subprocess.run(
                    ["gh", "api", "user", "--jq", ".login"],
                    capture_output=True,
                    text=True
                )
                current_user = current_user_result.stdout.strip() if current_user_result.returncode == 0 else ""
                
                if owner_login != current_user:
                    console.print(f"[yellow]Cannot rename: Repository is owned by '{owner_login}', not you[/yellow]")
                    console.print(f"[dim]You can only rename repositories under your account[/dim]")
                    console.print(f"[dim]Use --no-github to skip GitHub rename, or --skip-github-check to try anyway[/dim]")
                    return False
                
                if not can_administer:
                    console.print(f"[yellow]Cannot rename: You don't have admin permissions[/yellow]")
                    console.print(f"[dim]Use --no-github to skip GitHub rename[/dim]")
                    return False
                
        except (json.JSONDecodeError, KeyError):
            # If we can't parse, try to rename anyway (gh will give proper error)
            pass
        
        if dry_run:
            console.print(f"[cyan]Would rename GitHub repo:[/cyan] {old_name} → {new_name}")
            return True
        
        # Rename the repository
        result = subprocess.run(
            ["gh", "repo", "rename", new_name, "--confirm"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print(f"[green]✓[/green] GitHub repository renamed successfully")
            return True
        else:
            error_msg = result.stderr or result.stdout
            if "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                console.print(f"[yellow]Cannot rename: No permission to rename this repository[/yellow]")
            elif "organization" in error_msg.lower():
                console.print(f"[yellow]Cannot rename: Repository belongs to an organization[/yellow]")
            else:
                console.print(f"[red]Failed to rename GitHub repo: {error_msg}[/red]")
            return False
            
    except FileNotFoundError:
        console.print("[yellow]gh CLI not found. Install with: brew install gh[/yellow]")
        return False


def rename_gogs_repo(old_name: str, new_name: str, dry_run: bool = False) -> bool:
    """Rename repository on Gogs using API."""
    config = load_gogs_config()
    
    if not config.get('GOGS_API_TOKEN'):
        console.print("[yellow]Gogs API token not found in ~/.gogs-rc[/yellow]")
        return False
    
    if not config.get('GOGS_API_URL'):
        # Construct API URL from other config values
        host = config.get('GOGS_HOSTNAME', config.get('GOGS_HOST', 'localhost'))
        port = config.get('GOGS_PORT', '3000')
        config['GOGS_API_URL'] = f"http://{host}:{port}/api/v1"
    
    user = config.get('GOGS_USER', 'git')
    api_url = config['GOGS_API_URL']
    token = config['GOGS_API_TOKEN']
    
    # Check if repo exists on Gogs
    import requests
    try:
        response = requests.get(
            f"{api_url}/repos/{user}/{old_name}",
            headers={"Authorization": f"token {token}"}
        )
        
        if response.status_code != 200:
            console.print("[yellow]Repository not found on Gogs or no access[/yellow]")
            return False
        
        if dry_run:
            console.print(f"[cyan]Would rename Gogs repo:[/cyan] {old_name} → {new_name}")
            return True
        
        # Rename the repository
        response = requests.patch(
            f"{api_url}/repos/{user}/{old_name}",
            headers={"Authorization": f"token {token}"},
            json={"name": new_name}
        )
        
        if response.status_code in [200, 204]:
            console.print(f"[green]✓[/green] Gogs repository renamed successfully")
            return True
        else:
            console.print(f"[red]Failed to rename Gogs repo: {response.text}[/red]")
            return False
            
    except requests.RequestException as e:
        console.print(f"[red]Failed to connect to Gogs: {e}[/red]")
        return False


def update_git_remotes(old_name: str, new_name: str, dry_run: bool = False) -> bool:
    """Update git remote URLs to reflect new repository name."""
    remotes = get_git_remotes()
    updated = False
    
    for remote_name, url in remotes.items():
        new_url = None
        
        # Check if this remote contains the old repo name
        if f"/{old_name}.git" in url:
            new_url = url.replace(f"/{old_name}.git", f"/{new_name}.git")
        elif f"/{old_name}" in url and url.endswith(old_name):
            new_url = url.replace(f"/{old_name}", f"/{new_name}")
        elif f":{old_name}.git" in url:  # SSH format
            new_url = url.replace(f":{old_name}.git", f":{new_name}.git")
        elif f":{old_name}" in url and url.endswith(old_name):
            new_url = url.replace(f":{old_name}", f"/{new_name}")
        
        if new_url and new_url != url:
            if dry_run:
                console.print(f"[cyan]Would update remote '{remote_name}':[/cyan]")
                console.print(f"  {url} → {new_url}")
            else:
                try:
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, new_url],
                        check=True,
                        capture_output=True
                    )
                    console.print(f"[green]✓[/green] Updated remote '{remote_name}'")
                    updated = True
                except subprocess.CalledProcessError as e:
                    console.print(f"[red]Failed to update remote '{remote_name}': {e}[/red]")
    
    return updated


def rename_command(
    old_name: Optional[str] = typer.Argument(
        None,
        help="Project to rename (path or name). If not provided, uses current directory"
    ),
    new_name: Optional[str] = typer.Argument(
        None,
        help="New project/repository name"
    ),
    new_path: Optional[Path] = typer.Option(
        None,
        "--new-path",
        help="New full path for the project (for moving projects)"
    ),
    rename_remotes: bool = typer.Option(
        True,
        "--rename-remotes/--no-rename-remotes",
        help="Also rename remote repositories"
    ),
    github: bool = typer.Option(
        True,
        "--github/--no-github",
        help="Rename GitHub repository (if you have permission)"
    ),
    gogs: bool = typer.Option(
        True,
        "--gogs/--no-gogs",
        help="Rename Gogs repository"
    ),
    skip_github_check: bool = typer.Option(
        False,
        "--skip-github-check",
        help="Skip GitHub ownership check and try to rename anyway"
    ),
    only_claude: bool = typer.Option(
        False,
        "--only-claude",
        help="Only rename Claude project, skip remotes"
    ),
    only_remotes: bool = typer.Option(
        False,
        "--only-remotes",
        help="Only rename remotes, skip Claude project"
    ),
    recover: bool = typer.Option(
        False,
        "--recover",
        help="Recover from a partially completed rename operation"
    ),
    fix_mismatch: bool = typer.Option(
        False,
        "--fix",
        help="Fix mismatched Claude project mapping (rename Claude project back to match current directory)"
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
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        help="Rename all nested Claude projects (default: True)"
    ),
):
    """
    Rename a Claude Code managed project and optionally its remote repositories.
    
    This command can:
    - Rename the Claude Code project directory (preserving history)
    - Rename the repository on GitHub
    - Rename the repository on Gogs
    - Update local git remote URLs
    - By default, recursively handle all nested Claude-managed projects
    
    Examples:
        # From outside: rename specific project
        cc-goodies rename old-project new-project
        cc-goodies rename /path/to/old-project new-project
        
        # From inside: rename current project
        cd my-project && cc-goodies rename new-name
        
        # Move project to new path
        cc-goodies rename old-project --new-path /Users/wei/NewProjects/my-project
        
        # Rename only the main project, skip nested ones
        cc-goodies rename --no-recursive old-project new-name
        
        # Preview changes without making them
        cc-goodies rename --dry-run old-project new-name
        
        # Only rename Claude project
        cc-goodies rename old-project new-name --only-claude
        
        # Only rename remotes
        cc-goodies rename old-project new-name --only-remotes
        
        # Recover from interrupted rename
        cc-goodies rename --recover old-project new-name --force
        
        # Fix mismatched Claude project
        cc-goodies rename --fix --force
    """
    
    import typer
    from pathlib import Path
    from typing import Optional
    
    # Early validation and argument processing
    if fix_mismatch and (old_name or new_name or new_path):
        console.print("[red]Error: --fix cannot be used with other positional arguments[/red]")
        raise typer.Exit(1)
    
    # Parse arguments for different usage patterns
    if not fix_mismatch:
        # Standard rename flow
        cwd = Path.cwd()
        
        # Argument parsing - same complex logic as before
        if old_name and new_name:
            # External usage: cc-goodies rename old new
            current_path = old_name if os.path.isabs(old_name) else os.path.abspath(old_name)
            final_new_name = new_name
            new_full_path = os.path.join(os.path.dirname(current_path), final_new_name) if not new_path else str(new_path)
            is_sync_operation = False
        elif old_name and not new_name:
            # Internal usage: cc-goodies rename new (only one arg provided)
            if os.path.exists(old_name):
                console.print("[yellow]Ambiguous: Is this a source path or new name?[/yellow]")
                console.print("[dim]  Interpreting as source path. Use quoted names for clarity.[/dim]")
                current_path = os.path.abspath(old_name)
                final_new_name = os.path.basename(current_path)
                new_full_path = current_path
            else:
                # Assume it's a new name for current directory
                final_new_name = old_name
                current_path = str(cwd)
                new_full_path = os.path.join(os.path.dirname(current_path), final_new_name) if not new_path else str(new_path)
            is_sync_operation = False
        elif not old_name and not new_name:
            # No arguments provided - requires --fix
            console.print("[red]Error: Must provide project name(s) or use --fix[/red]")
            console.print("[dim]Usage: cc-goodies rename old-name new-name   (from anywhere)[/dim]")
            console.print("[dim]   Or: cc-goodies rename new-name          (from inside project)[/dim]")
            console.print("[dim]   Or: cc-goodies rename --fix --force     (fix mismatched mapping)[/dim]")
            raise typer.Exit(1)
        else:
            # new_name provided but no old_name - internal usage
            final_new_name = new_name
            current_path = str(cwd)
            new_full_path = os.path.join(os.path.dirname(current_path), final_new_name) if not new_path else str(new_path)
            is_sync_operation = False

        # Handle new_path override
        if new_path:
            new_full_path = str(new_path)
            final_new_name = os.path.basename(new_full_path)
            
        # Sync detection logic
        current_dir_name = os.path.basename(current_path)
        current_repo_name = get_current_repo_name()
        new_claude_name = path_to_claude_project_name(new_full_path)
        
        # Check for sync situations
        if current_repo_name and current_repo_name != current_dir_name and not only_claude:
            console.print(f"[yellow]Detection: Directory name '{current_dir_name}' != Repository name '{current_repo_name}'[/yellow]")
            if not new_name:
                console.print(f"[cyan]Sync mode: Will align directory name with repository name[/cyan]")
                final_new_name = current_repo_name
                new_full_path = os.path.join(os.path.dirname(current_path), current_repo_name) if not new_path else str(new_path)
                is_sync_operation = True
            
        # Auto-fix directory vs remote mismatch
        if current_path != new_full_path and os.path.exists(new_full_path):
            console.print(f"[cyan]Auto-detection: Directory might be renamed, remotes might not be[/cyan]")
            
            if dry_run:
                console.print("[cyan]Would rename (dry-run mode)[/cyan]")
                return
                
            # This handles cases where directory was already renamed but git remotes weren't
            # Check if we're already in the renamed directory and just need to sync remotes
            claude_projects_dir = os.path.expanduser("~/.claude/projects")
            
            # Check if Claude project exists for new path
            if os.path.isdir(os.path.join(claude_projects_dir, path_to_claude_project_name(new_full_path))):
                console.print(f"[green]Found existing Claude project for target path[/green]")
                current_path = new_full_path
                is_sync_operation = True
            
        # Normal rename operation
        old_assumed_path = current_path
        
        # Check if the current directory exists - it might have been renamed already
        if not os.path.exists(current_path):
            # Directory might have already been renamed but we're still in old location
            new_full_path = os.path.join(os.path.dirname(current_path), final_new_name) if not new_path else str(new_path)
            
    # Recovery mode: Check if we're in a partially renamed state
    if recover:
        console.print("[cyan]🔄 Recovery mode: Checking for partial rename...[/cyan]")
        
        # Check if directory was already renamed but we're still in old location
        if not os.path.exists(current_path) and os.path.exists(new_full_path):
            console.print(f"[yellow]Directory appears to be already renamed to: {new_full_path}[/yellow]")
            console.print(f"[cyan]Switching to renamed directory for remote operations...[/cyan]")
            current_path = new_full_path
            is_sync_operation = True
            
        # Check if Claude project was already renamed
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        old_project_name = path_to_claude_project_name(old_assumed_path)
        new_project_name = path_to_claude_project_name(new_full_path)
        old_project_path = os.path.join(claude_projects_dir, old_project_name)
        new_project_path = os.path.join(claude_projects_dir, new_project_name)
        
        if not os.path.exists(old_project_path) and os.path.exists(new_project_path):
            console.print("[green]✓ Claude project already renamed[/green]")
            rename_claude = False
        
    # Fix mismatch mode
    if fix_mismatch:
        rename_remotes = False
        rename_claude = False
        
    if only_remotes:
        rename_claude = True
        
    if only_claude:
        rename_claude = False
        
    # In sync mode, we never rename the directory (it's already correct)
    if is_sync_operation:
        rename_directory = False
    
    # Check if it's a partial rename scenario even without --recover flag
    if not recover and not fix_mismatch:
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        old_project_name = path_to_claude_project_name(old_assumed_path if 'old_assumed_path' in locals() else current_path)
        
        if current_path != new_full_path:
            new_project_name = path_to_claude_project_name(new_full_path)
            old_project_path = os.path.join(claude_projects_dir, old_project_name)
            new_project_path = os.path.join(claude_projects_dir, new_project_name)
            
            # If new project already exists, it might be a partial rename
            if os.path.exists(new_project_path) and not os.path.exists(old_project_path):
                console.print(f"[cyan]Auto-detection: Claude project appears already renamed[/cyan]")
                console.print(f"  • Claude project: renamed to {new_claude_name}")
                
                # Check if the actual directory was renamed
                if not os.path.exists(new_full_path):
                    console.print("[cyan]The directory was NOT renamed. This might be intentional or from an interrupted operation.[/cyan]")
                    if not force and not typer.confirm("Continue with directory rename only?"):
                        console.print("[yellow]Operation cancelled[/yellow]")
                        raise typer.Exit(0)
                else:
                    current_path = new_full_path  # Use this for the rename operation
                    is_sync_operation = True
                    rename_claude = False
        
    # Pre-scan for Claude projects if recursive mode is enabled
    projects_to_update = []
    if recursive and not only_remotes and not fix_mismatch:
        console.print(f"[cyan]Scanning for Claude-managed projects...[/cyan]")
        projects_to_update = find_all_claude_projects(current_path)
        
        if not projects_to_update:
            console.print(f"[yellow]Warning: No Claude-managed projects found in directory tree[/yellow]")
            if not force and not only_remotes:
                console.print(f"[dim]Use --force to proceed anyway, or --no-recursive for single project mode[/dim]")
                raise typer.Exit(1)
            else:
                console.print(f"[yellow]Proceeding anyway (--force used or --only-remotes)[/yellow]")
                recursive = False
    elif not recursive or only_remotes or fix_mismatch:
        # Single project mode or remote-only mode
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        project_name = path_to_claude_project_name(current_path)
        project_path = os.path.join(claude_projects_dir, project_name)
        
        if os.path.isdir(project_path) and not only_remotes and not fix_mismatch:
            projects_to_update = [{
                'path': current_path,
                'project_name': project_name,
                'relative_path': '.'
            }]
    
    # Determine if we need to rename the filesystem directory
    rename_directory = not is_sync_operation and not only_remotes and not only_claude and current_path != new_full_path
    
    # Show directory rename first (most important)
    if rename_directory:
        console.print(f"[cyan]Directory:[/cyan] {current_path} → {new_full_path}")
        
        # Check for moving into subdirectory of itself
        if new_full_path.startswith(current_path + os.sep):
            console.print(f"[red]Error: Cannot rename directory into its own subdirectory[/red]")
            raise typer.Exit(1)
        
        # Check if target already exists
        if os.path.exists(new_full_path) and current_path != new_full_path:
            console.print(f"[red]Error: Target directory already exists: {new_full_path}[/red]")
            raise typer.Exit(1)
    
    # Show Claude project rename details
    if not only_remotes and projects_to_update:
        if len(projects_to_update) == 1 and projects_to_update[0]['relative_path'] == '.':
            # Single main project
            if rename_directory or new_full_path != current_path:
                console.print(f"[cyan]Claude Project:[/cyan] {projects_to_update[0]['project_name']} → {path_to_claude_project_name(new_full_path)}")
            else:
                # Check if already renamed
                claude_projects_dir = os.path.expanduser("~/.claude/projects")
                current_project_name = projects_to_update[0]['project_name']
                new_project_name = path_to_claude_project_name(new_full_path)
                
                if current_project_name == new_project_name:
                    console.print(f"[cyan]Claude Project:[/cyan] {current_project_name} [green](no change needed)[/green]")
                else:
                    console.print(
                        f"[cyan]Claude Project:[/cyan] {current_project_name} → "
                        f"{path_to_claude_project_name(new_full_path)} [green](already renamed)[/green]"
                    )
        elif len(projects_to_update) > 1:
            # Multiple projects
            console.print(f"[cyan]Claude Projects:[/cyan] {len(projects_to_update)} project(s) will be renamed recursively")
    elif not only_remotes and not fix_mismatch:
        console.print("[yellow]Claude Project: Not managed by Claude Code[/yellow]")
    
    # Show remote rename info
    if rename_remotes and not only_claude:
        current_repo_name = get_current_repo_name()
        if current_repo_name and current_repo_name != final_new_name:
            git_remotes = get_git_remotes()
            
            # Show remote info
            from rich.table import Table
            from rich import box
            
            table = Table(title="Remote Repository Renames", box=box.ROUNDED)
            table.add_column("Remote", style="cyan")
            table.add_column("Type", style="blue")
            table.add_column("Current Name", style="yellow")
            table.add_column("New Name", style="green")
            
            for remote, url in git_remotes.items():
                if 'github.com' in url:
                    table.add_row(remote, "GitHub", current_repo_name, final_new_name)
                elif 'gogs' in url.lower():
                    table.add_row(remote, "Gogs", current_repo_name, final_new_name)
                else:
                    table.add_row(remote, "Other", current_repo_name, f"{final_new_name} [yellow](may need manual rename)[/yellow]")
            
            console.print(table)
        elif not current_repo_name:
            console.print("[yellow]Remote Repositories: No git repository detected[/yellow]")
    
    # Show detailed project list if multiple projects found
    if recursive and len(projects_to_update) > 1:
        console.print(f"\n[green]Found {len(projects_to_update)} Claude-managed project(s):[/green]")
        
        from rich.table import Table
        from rich import box
        
        detail_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        detail_table.add_column("Relative Path")
        detail_table.add_column("Current Project Name", overflow="fold")
        detail_table.add_column("New Project Name", overflow="fold")
        
        for project in projects_to_update:
            relative_path = project['relative_path']
            old_path = project['path']
            
            # Calculate new path for this project
            if relative_path == '.':
                new_path_for_project = new_full_path
            else:
                # For nested projects, we need to update their paths based on the rename
                if rename_directory and final_new_name != os.path.basename(current_path):
                    # Directory name is changing - update nested project paths
                    old_root_name = os.path.basename(current_path)
                    new_path_for_project = old_path.replace(old_root_name, final_new_name, 1)
                else:
                    # Directory path is changing but name might be same
                    new_path_for_project = os.path.join(new_full_path, relative_path)
                
            new_project_name = path_to_claude_project_name(new_path_for_project)
            detail_table.add_row(relative_path, project['project_name'], new_project_name)
        
        console.print(detail_table)
    
    # Dry run indicator
    if dry_run:
        console.print("\n[cyan]DRY RUN MODE - No changes will be made[/cyan]")
    
    # Confirmation prompt
    if not dry_run and not force and (rename_directory or projects_to_update or rename_remotes):
        confirmation_msg = "\nProceed with rename operation?"
        if len(projects_to_update) > 1:
            confirmation_msg = f"\nProceed with rename operation (will rename {len(projects_to_update)} Claude projects)?"
        
        if not typer.confirm(confirmation_msg):
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit(0)
    
    # === EXECUTION PHASE ===
    
    console.print()
    overall_success = True
    
    # Determine if we need to rename the filesystem directory
    rename_directory = not is_sync_operation and not only_remotes and not only_claude and current_path != new_full_path
    
    # Important: Change to parent directory before renaming the current directory
    # to avoid issues with the current directory being renamed
    if rename_directory and not dry_run and not new_path:
        parent_dir = os.path.dirname(current_path)
        try:
            os.chdir(parent_dir)
            console.print(f"[dim]Changed to parent directory: {parent_dir}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not change to parent directory: {e}[/yellow]")
    
    # Execute operations in order
    
    # 1. Rename filesystem directory first
    if rename_directory:
        console.print("[cyan]📁 Renaming directory...[/cyan]")
        result = rename_filesystem_directory(current_path, new_full_path, dry_run)
        if not result:
            overall_success = False
            console.print("[red]Failed to rename directory. Stopping operation.[/red]")
            raise typer.Exit(1)
            # Don't continue if directory rename failed
    
    # 2. Rename Claude projects (recursive or single)
    if not only_remotes and projects_to_update:
        console.print("[cyan]🧠 Renaming Claude projects...[/cyan]")
        
        if recursive and len(projects_to_update) > 1:
            # Use recursive rename function
            result = rename_all_claude_projects(
                current_path, 
                new_full_path, 
                final_new_name if rename_directory else None,
                dry_run
            )
        elif len(projects_to_update) == 1:
            # Use single project rename function
            # Pass check_reverse=True to handle already-renamed cases
            result = rename_claude_project(current_path, new_full_path, dry_run, check_reverse=True)
        else:
            result = True
            
        if not result:
            overall_success = False
            console.print("[yellow]Warning: Claude project rename failed[/yellow]")
    
    # 3. Rename remote repositories
    if rename_remotes and current_repo_name != final_new_name and not only_claude:
        # Get remotes before potential directory rename
        git_remotes = get_git_remotes()
        
        if git_remotes:
            console.print("[cyan]🌐 Renaming remote repositories...[/cyan]")
            
            # Determine working directory for git operations
            git_work_dir = new_full_path if (rename_directory and not dry_run and os.path.exists(new_full_path)) else current_path
            
            # GitHub rename
            if github and any('github.com' in url for url in git_remotes.values()):
                console.print("[dim]  Renaming GitHub repository...[/dim]")
                
                # Change to the correct directory for git operations
                original_cwd = os.getcwd()
                if os.path.exists(git_work_dir):
                    os.chdir(git_work_dir)
                
                try:
                    if not rename_github_repo(current_repo_name, final_new_name, dry_run, skip_github_check):
                        overall_success = False
                        console.print("[yellow]Warning: GitHub repository rename failed[/yellow]")
                finally:
                    os.chdir(original_cwd)
            
            # Gogs rename  
            if gogs and any('gogs' in url.lower() for url in git_remotes.values()):
                console.print("[dim]  Renaming Gogs repository...[/dim]")
                if not rename_gogs_repo(current_repo_name, final_new_name, dry_run):
                    overall_success = False
                    console.print("[yellow]Warning: Gogs repository rename failed[/yellow]")
            
            # Update git remote URLs
            console.print("[dim]  Updating git remote URLs...[/dim]")
            
            # Change to the correct directory for git operations
            original_cwd = os.getcwd()
            if os.path.exists(git_work_dir):
                os.chdir(git_work_dir)
            
            try:
                update_git_remotes(current_repo_name, final_new_name, dry_run)
            finally:
                os.chdir(original_cwd)
    
    # Note about directory change - only if the directory actually exists and was renamed
    if rename_directory and os.path.exists(new_full_path):
        console.print(f"\n[cyan]ℹ️  Note: Your project directory has been renamed. To enter the renamed directory:[/cyan]")
        console.print(f'[cyan]   cd "{new_full_path}"[/cyan]')
    elif not rename_directory and current_path != new_full_path:
        # Directory wasn't actually renamed (maybe only Claude project was)
        console.print(f"\n[yellow]⚠️  Note: The directory was not renamed (still at current location).[/yellow]")
        if projects_to_update:
            console.print(f"[dim]Claude project mappings have been updated to reflect the new structure.[/dim]")
    
    # Final status
    console.print()
    
    if dry_run:
        from rich.panel import Panel
        from rich import box
        
        console.print(Panel(
            "[cyan]Dry run completed. Review the changes above.[/cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
    elif overall_success:
        from rich.panel import Panel
        from rich import box
        
        success_msg = f"[bold green]✨ Successfully renamed project![/bold green]\n"
        if len(projects_to_update) > 1:
            success_msg += f"[dim]Renamed {len(projects_to_update)} Claude project(s)[/dim]\n"
        success_msg += f"[dim]New name: {final_new_name}[/dim]"
        if rename_directory:
            success_msg += f"\n[dim]New location: {new_full_path}[/dim]"
            
        console.print(Panel(
            success_msg,
            border_style="green",
            box=box.DOUBLE
        ))
    else:
        from rich.panel import Panel
        from rich import box
        
        console.print(Panel(
            "[yellow]⚠️  Rename completed with some failures[/yellow]\n"
            "[dim]Check the messages above for details.[/dim]",
            border_style="yellow",
            box=box.DOUBLE
        ))


if __name__ == "__main__":
    # For testing
    typer.run(rename_command)