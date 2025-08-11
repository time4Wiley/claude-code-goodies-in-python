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
):
    """
    Rename a Claude Code managed project and optionally its remote repositories.
    
    This command can:
    - Rename the Claude Code project directory (preserving history)
    - Rename the repository on GitHub
    - Rename the repository on Gogs
    - Update local git remote URLs
    
    Examples:
        # Rename to new name in same directory
        cc-goodies rename my-new-project
        
        # Move project to new path
        cc-goodies rename --new-path /Users/wei/NewProjects/my-project
        
        # Preview changes without making them
        cc-goodies rename --dry-run new-name
        
        # Only rename Claude project
        cc-goodies rename new-name --only-claude
    """
    
    # Get current directory
    current_path = os.getcwd()
    current_dir_name = os.path.basename(current_path)
    current_parent = os.path.dirname(current_path)
    
    # Fix mismatch mode: Correct Claude project to match current directory name
    if fix_mismatch:
        console.print("[cyan]🔧 Fix mode: Resetting Claude project to match current directory...[/cyan]")
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        
        # What the Claude project SHOULD be based on current directory
        correct_claude_name = path_to_claude_project_name(current_path)
        correct_claude_path = os.path.join(claude_projects_dir, correct_claude_name)
        
        # Look for any Claude project that might be a mismatch
        # (ends with a variation of the current directory name)
        base_name = current_dir_name.replace('-', '.')  # Handle variations
        found_mismatch = False
        
        for entry in os.listdir(claude_projects_dir):
            # Check if this might be our project but with wrong name
            if current_dir_name in entry or base_name in entry:
                if entry != correct_claude_name:
                    wrong_path = os.path.join(claude_projects_dir, entry)
                    console.print(f"[yellow]Found potentially mismatched project:[/yellow]")
                    console.print(f"  Current: {entry}")
                    console.print(f"  Should be: {correct_claude_name}")
                    
                    if not force and not typer.confirm("\nRename this Claude project to match current directory?"):
                        continue
                    
                    if not dry_run:
                        try:
                            if os.path.exists(correct_claude_path):
                                console.print(f"[red]Target already exists: {correct_claude_name}[/red]")
                            else:
                                shutil.move(wrong_path, correct_claude_path)
                                console.print("[green]✓ Fixed Claude project mapping![/green]")
                                found_mismatch = True
                                break
                        except Exception as e:
                            console.print(f"[red]Failed to fix: {e}[/red]")
                    else:
                        console.print("[cyan]Would rename (dry-run mode)[/cyan]")
                        found_mismatch = True
                        break
        
        if not found_mismatch:
            console.print(f"[yellow]No mismatched Claude project found for: {current_dir_name}[/yellow]")
            console.print(f"[cyan]Expected Claude project name: {correct_claude_name}[/cyan]")
        
        raise typer.Exit(0)
    
    # Determine new path and name
    if new_path:
        # Full new path provided
        new_full_path = str(new_path.absolute())
        final_new_name = os.path.basename(new_full_path)
    elif new_name:
        # Just new name provided - stay in same parent directory
        new_full_path = os.path.join(current_parent, new_name)
        final_new_name = new_name
    else:
        console.print("[red]Error: Must provide either new_name or --new-path[/red]")
        raise typer.Exit(1)
    
    # Smart detection: Figure out what the "old" name really is
    # This handles cases where directory was already renamed but git remotes weren't
    git_repo_name = get_current_repo_name()
    
    # Detect sync scenario: directory already has target name
    is_sync_operation = (current_dir_name == final_new_name)
    
    if is_sync_operation:
        console.print("[cyan]📍 Sync mode: Directory already has target name, checking other components...[/cyan]")
        # In sync mode, the "current" name for repos should come from git remotes
        if git_repo_name and git_repo_name != final_new_name:
            current_repo_name = git_repo_name
            console.print(f"  • Git remotes still use old name: {git_repo_name}")
            console.print(f"  • Will update to match directory: {final_new_name}")
        else:
            current_repo_name = current_dir_name
    else:
        # Normal rename operation
        current_repo_name = git_repo_name or current_dir_name
        
        # If the repo name from git already matches the target name, 
        # it might have been renamed already
        if current_repo_name == final_new_name:
            console.print(f"[yellow]Note: Git remotes already use target name: {final_new_name}[/yellow]")
            current_repo_name = current_dir_name
    
    # Recovery mode: Check if we're in a partially renamed state
    if recover:
        console.print("[cyan]🔄 Recovery mode: Checking for partial rename...[/cyan]")
        
        # Check if directory was already renamed but we're still in old location
        if os.path.exists(new_full_path) and not os.path.exists(current_path):
            console.print(f"[yellow]Directory appears to be already renamed to: {new_full_path}[/yellow]")
            console.print(f"[cyan]Switching to renamed directory for remote operations...[/cyan]")
            current_path = new_full_path
            os.chdir(new_full_path)
        
        # Check Claude project status
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        old_claude_name = path_to_claude_project_name(current_path)
        new_claude_name = path_to_claude_project_name(new_full_path)
        old_claude_path = os.path.join(claude_projects_dir, old_claude_name)
        new_claude_path = os.path.join(claude_projects_dir, new_claude_name)
        
        if os.path.exists(new_claude_path) and not os.path.exists(old_claude_path):
            console.print("[green]✓ Claude project already renamed[/green]")
            only_remotes = True  # Only need to handle remotes
            rename_claude = False
    
    # Override flags if only_claude or only_remotes is set
    if only_claude:
        rename_remotes = False
    if only_remotes:
        rename_claude = False
    else:
        rename_claude = True
    
    # In sync mode, we never rename the directory (it's already correct)
    # We only sync Claude project and remotes to match
    if is_sync_operation:
        # Check if Claude project needs syncing
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        expected_claude_name = path_to_claude_project_name(new_full_path)
        expected_claude_path = os.path.join(claude_projects_dir, expected_claude_name)
        
        if os.path.exists(expected_claude_path):
            console.print(f"  • Claude project already correct")
            rename_claude = False
        else:
            console.print(f"  • Claude project needs syncing")
            # Try to find the old Claude project based on git repo name or variations
            if git_repo_name and git_repo_name != final_new_name:
                # Build the old path using the git repo name
                old_assumed_path = os.path.join(current_parent, git_repo_name)
                old_claude_name = path_to_claude_project_name(old_assumed_path)
                old_claude_path = os.path.join(claude_projects_dir, old_claude_name)
                
                if os.path.exists(old_claude_path):
                    console.print(f"    Found old Claude project: {old_claude_name}")
                    current_path = old_assumed_path  # Use this for the rename operation
                else:
                    console.print(f"    [yellow]Warning: Could not find old Claude project[/yellow]")
                    rename_claude = False
    
    # Auto-detect partial rename even without --recover flag
    if not recover and rename_claude:
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        old_claude_name = path_to_claude_project_name(current_path)
        new_claude_name = path_to_claude_project_name(new_full_path)
        old_claude_path = os.path.join(claude_projects_dir, old_claude_name)
        new_claude_path = os.path.join(claude_projects_dir, new_claude_name)
        
        if not os.path.exists(old_claude_path) and os.path.exists(new_claude_path):
            console.print("[yellow]⚠️  Detected inconsistent state:[/yellow]")
            console.print(f"  • Claude project: renamed to {new_claude_name}")
            console.print(f"  • Directory: still at {current_path}")
            
            # Check if the actual directory was renamed
            if not os.path.exists(new_full_path):
                console.print("[cyan]The directory was NOT renamed. This might be intentional or from an interrupted operation.[/cyan]")
                console.print("[cyan]The command will update the Claude project to match the current directory.[/cyan]")
    
    # Create summary table
    table_title = "Sync Operation Summary" if is_sync_operation else "Rename Operation Summary"
    table = Table(title=table_title, box=box.ROUNDED)
    table.add_column("Component", style="cyan")
    table.add_column("Current", style="yellow")
    table.add_column("New", style="green")
    
    # Determine if we need to rename the filesystem directory
    rename_directory = not is_sync_operation and not only_remotes and not only_claude and current_path != new_full_path
    
    # Show directory rename first (most important)
    if rename_directory:
        table.add_row(
            "Directory",
            os.path.basename(current_path),
            os.path.basename(new_full_path)
        )
    elif is_sync_operation:
        table.add_row(
            "Directory",
            os.path.basename(current_path),
            f"{os.path.basename(current_path)} [green](already correct)[/green]"
        )
    
    if rename_claude:
        # Check if already renamed
        claude_projects_dir = os.path.expanduser("~/.claude/projects")
        old_claude_name = path_to_claude_project_name(current_path)
        new_claude_name = path_to_claude_project_name(new_full_path)
        old_claude_path = os.path.join(claude_projects_dir, old_claude_name)
        new_claude_path = os.path.join(claude_projects_dir, new_claude_name)
        
        if not os.path.exists(old_claude_path) and os.path.exists(new_claude_path):
            table.add_row(
                "Claude Project",
                path_to_claude_project_name(current_path),
                f"{path_to_claude_project_name(new_full_path)} [green](already renamed)[/green]"
            )
        else:
            table.add_row(
                "Claude Project",
                path_to_claude_project_name(current_path),
                path_to_claude_project_name(new_full_path)
            )
    
    if rename_remotes:
        remotes = get_git_remotes()
        
        # Only show repos that actually need updating
        show_github = github and any('github.com' in url for url in remotes.values()) and current_repo_name != final_new_name
        show_gogs = False
        
        if show_github:
            # Check if it's an org repo or someone else's
            github_url = next((url for url in remotes.values() if 'github.com' in url), "")
            is_org_repo = False
            if github_url:
                # Extract owner from URL (works for both SSH and HTTPS)
                import re
                match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', github_url)
                if match:
                    owner = match.group(1)
                    # Check if owner is different from user's GitHub username
                    # (we can't easily check this without an API call, so just flag common org patterns)
                    if owner != "time4Wiley" and owner != "time4peter":  # Your known usernames
                        is_org_repo = True
            
            if is_org_repo:
                table.add_row("GitHub Repo", current_repo_name, f"{final_new_name} [yellow](may need manual rename)[/yellow]")
            else:
                table.add_row("GitHub Repo", current_repo_name, final_new_name)
        
        gogs_config = load_gogs_config()
        gogs_host = gogs_config.get('GOGS_HOSTNAME', gogs_config.get('GOGS_HOST', ''))
        if gogs and gogs_host and any(gogs_host in url for url in remotes.values()) and current_repo_name != final_new_name:
            show_gogs = True
            table.add_row("Gogs Repo", current_repo_name, final_new_name)
        
        # Check if git remotes need updating
        needs_remote_update = any(
            current_repo_name in url and current_repo_name != final_new_name
            for url in remotes.values()
        )
        
        if needs_remote_update:
            if is_sync_operation:
                table.add_row("Git Remotes", f"{len(remotes)} remote(s) with '{current_repo_name}'", f"Update to '{final_new_name}'")
            else:
                table.add_row("Git Remotes", f"{len(remotes)} remote(s)", "Will be updated")
    
    console.print(table)
    
    if dry_run:
        console.print("\n[cyan]DRY RUN MODE - No changes will be made[/cyan]")
    
    # Confirmation
    if not dry_run and not force:
        if not typer.confirm("\nProceed with rename operation?"):
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit(0)
    
    # Perform operations
    console.print()
    success = True
    
    # Save original directory for later restoration
    original_cwd = os.getcwd()
    should_change_dir = False
    
    # Determine if we need to rename the filesystem directory
    rename_directory = not is_sync_operation and not only_remotes and not only_claude and current_path != new_full_path
    
    # If we're renaming the directory and not in dry-run mode, we need to change to parent directory
    # to avoid issues with the current directory being renamed
    if rename_directory and not dry_run and not new_path:
        # Only change to parent if we're renaming in the same parent directory
        should_change_dir = True
        try:
            os.chdir(current_parent)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not change to parent directory: {e}[/yellow]")
            should_change_dir = False
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        
        # FIRST: Rename the actual filesystem directory (if needed)
        if rename_directory:
            task = progress.add_task("Renaming directory...", total=None)
            result = rename_filesystem_directory(current_path, new_full_path, dry_run)
            if not result:
                success = False
                console.print("[red]Failed to rename directory. Stopping operation.[/red]")
                progress.update(task, completed=True)
                # Don't continue if directory rename failed
                if not dry_run:
                    raise typer.Exit(1)
            progress.update(task, completed=True)
        
        # SECOND: Rename Claude project to match new directory
        if rename_claude:
            task = progress.add_task("Renaming Claude project...", total=None)
            # Pass check_reverse=True to handle already-renamed cases
            result = rename_claude_project(current_path, new_full_path, dry_run, check_reverse=True)
            if not result:
                success = False
            progress.update(task, completed=True)
        
        # THIRD: Rename remote repositories and update git remotes
        if rename_remotes and current_repo_name != final_new_name:
            # Get remotes before potential directory rename
            remotes = get_git_remotes()
            
            # After renaming directory, we need to work from the new directory location
            git_work_dir = new_full_path if (rename_directory and not dry_run and os.path.exists(new_full_path)) else current_path
            
            # Temporarily change to the git directory for remote operations
            saved_dir = os.getcwd()
            try:
                if os.path.exists(git_work_dir):
                    os.chdir(git_work_dir)
                
                # Rename on GitHub
                if github and any('github.com' in url for url in remotes.values()):
                    task = progress.add_task("Renaming GitHub repository...", total=None)
                    if not rename_github_repo(current_repo_name, final_new_name, dry_run, skip_github_check):
                        success = False
                    progress.update(task, completed=True)
                
                # Rename on Gogs
                if gogs and gogs_host and any(gogs_host in url for url in remotes.values()):
                    task = progress.add_task("Renaming Gogs repository...", total=None)
                    if not rename_gogs_repo(current_repo_name, final_new_name, dry_run):
                        success = False
                    progress.update(task, completed=True)
                
                # Update git remotes
                if remotes:
                    task = progress.add_task("Updating git remotes...", total=None)
                    update_git_remotes(current_repo_name, final_new_name, dry_run)
                    progress.update(task, completed=True)
            finally:
                # Always restore the directory
                os.chdir(saved_dir)
    
    # Note about directory change - only if the directory actually exists and was renamed
    if should_change_dir and success and not dry_run and os.path.exists(new_full_path):
        console.print(f"\n[cyan]ℹ️  Note: Your project directory has been renamed. To enter the renamed directory:[/cyan]")
        console.print(f"[cyan]   cd {new_full_path}[/cyan]")
    elif should_change_dir and success and not dry_run and not os.path.exists(new_full_path):
        # Directory wasn't actually renamed (maybe only Claude project was)
        console.print(f"\n[yellow]⚠️  Note: The directory was not renamed (still at current location).[/yellow]")
        if rename_claude:
            console.print(f"[yellow]   The Claude project mapping was updated but the directory remains: {current_path}[/yellow]")
    elif is_sync_operation and success and not dry_run:
        console.print(f"\n[green]✓ All components synced to: {final_new_name}[/green]")
    
    # Final status
    console.print()
    if dry_run:
        console.print(Panel(
            "[cyan]Dry run completed. Review the changes above.[/cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
    elif success:
        if is_sync_operation:
            console.print(Panel(
                f"[bold green]✨ Successfully synced project![/bold green]\n"
                f"[dim]All components now match: {final_new_name}[/dim]",
                border_style="green",
                box=box.DOUBLE
            ))
        else:
            console.print(Panel(
                f"[bold green]✨ Successfully renamed project![/bold green]\n"
                f"[dim]Claude project and remotes have been updated.[/dim]",
                border_style="green",
                box=box.DOUBLE
            ))
    else:
        console.print(Panel(
            "[yellow]⚠️  Rename completed with some warnings[/yellow]\n"
            "[dim]Check the messages above for details.[/dim]",
            border_style="yellow",
            box=box.DOUBLE
        ))


if __name__ == "__main__":
    # For testing
    typer.run(rename_command)