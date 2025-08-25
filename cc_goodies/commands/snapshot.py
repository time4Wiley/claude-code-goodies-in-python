"""
Project snapshot generator for AI context.
Creates a comprehensive markdown file containing all git-tracked source code.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
import mimetypes
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console(stderr=True)
app = typer.Typer()

# File extensions that are typically binary or should be excluded
BINARY_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    # Archives
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.xz',
    # Executables
    '.exe', '.dll', '.so', '.dylib', '.bin', '.o',
    # Media
    '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.mkv',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # Database
    '.db', '.sqlite', '.sqlite3',
    # Other
    '.pyc', '.pyo', '.class', '.jar', '.war', '.ear',
    '.woff', '.woff2', '.ttf', '.otf', '.eot',
    '.min.js', '.min.css',  # Minified files
}

# Extensions that should always be included as text
TEXT_EXTENSIONS = {
    '.txt', '.md', '.rst', '.asciidoc',
    '.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte',
    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs',
    '.html', '.htm', '.xml', '.css', '.scss', '.sass', '.less',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.sql', '.graphql', '.proto',
    '.r', '.R', '.m', '.swift', '.kt', '.scala', '.clj',
    '.lua', '.pl', '.rb', '.php', '.ex', '.exs', '.elm',
    '.dockerfile', '.dockerignore', '.gitignore', '.gitattributes',
    '.env', '.env.example', '.editorconfig',
}

def get_language_from_extension(file_path: Path) -> str:
    """Get the language identifier for syntax highlighting based on file extension."""
    ext = file_path.suffix.lower()
    
    # Map extensions to language identifiers
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'jsx',
        '.tsx': 'tsx',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.r': 'r',
        '.m': 'objc',
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'xml',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.conf': 'conf',
        '.cfg': 'cfg',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'zsh',
        '.fish': 'fish',
        '.ps1': 'powershell',
        '.bat': 'batch',
        '.cmd': 'batch',
        '.sql': 'sql',
        '.graphql': 'graphql',
        '.proto': 'protobuf',
        '.lua': 'lua',
        '.pl': 'perl',
        '.ex': 'elixir',
        '.exs': 'elixir',
        '.elm': 'elm',
        '.clj': 'clojure',
        '.dockerfile': 'dockerfile',
        '.md': 'markdown',
        '.rst': 'rst',
        '.tex': 'latex',
        '.vue': 'vue',
        '.svelte': 'svelte',
    }
    
    # Check for special filenames
    if file_path.name.lower() == 'dockerfile':
        return 'dockerfile'
    elif file_path.name.lower() == 'makefile':
        return 'makefile'
    elif file_path.name.lower() == 'rakefile':
        return 'ruby'
    
    return language_map.get(ext, '')

def is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary based on extension and content sampling."""
    # Check extension first
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        return False
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        if mime_type.startswith('text/'):
            return False
        if mime_type.startswith(('image/', 'audio/', 'video/', 'application/octet-stream')):
            return True
    
    # Sample file content to detect binary
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)  # Read first 8KB
            if not chunk:
                return False
            
            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True
            
            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8')
                return False
            except UnicodeDecodeError:
                return True
    except Exception:
        # If we can't read it, assume it's binary
        return True

def get_git_files(repo_path: Path) -> List[Path]:
    """Get all git-tracked files in the repository."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        
        files = []
        for line in result.stdout.strip().split('\n'):
            if line:
                file_path = repo_path / line
                if file_path.exists() and file_path.is_file():
                    files.append(file_path)
        
        return files
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error getting git files: {e}[/red]")
        return []

def get_git_info(repo_path: Path) -> dict:
    """Get git repository information."""
    info = {}
    
    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        info['branch'] = result.stdout.strip()
        
        # Get latest commit
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=format:%H %s'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        commit_info = result.stdout.strip().split(' ', 1)
        info['commit'] = commit_info[0][:7] if commit_info else 'unknown'
        info['commit_message'] = commit_info[1] if len(commit_info) > 1 else ''
        
        # Get remote origin URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False  # Don't fail if no remote
        )
        if result.returncode == 0:
            info['remote'] = result.stdout.strip()
        
    except subprocess.CalledProcessError:
        pass
    
    return info

def read_file_content(file_path: Path, max_size: int = 1024 * 1024) -> Optional[str]:
    """Read file content with size limit (default 1MB)."""
    try:
        if file_path.stat().st_size > max_size:
            return f"[File too large: {file_path.stat().st_size:,} bytes]"
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"[Error reading file: {e}]"

def format_file_tree(files: List[Path], repo_path: Path) -> str:
    """Create a tree-like structure of files."""
    tree_dict = {}
    
    for file in files:
        rel_path = file.relative_to(repo_path)
        parts = rel_path.parts
        
        current = tree_dict
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Add file (use None as marker for files vs directories)
        current[parts[-1]] = None
    
    def build_tree_string(d, prefix="", is_last=True):
        items = list(d.items())
        lines = []
        
        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1
            
            # Determine the prefix characters
            if prefix == "":
                current_prefix = ""
                extension = ""
            else:
                current_prefix = prefix
                extension = "└── " if is_last_item else "├── "
            
            lines.append(f"{current_prefix}{extension}{name}")
            
            # If it's a directory (not None), recurse
            if subtree is not None:
                next_prefix = prefix + ("    " if is_last_item else "│   ")
                lines.extend(build_tree_string(subtree, next_prefix, is_last_item).split('\n')[:-1])
        
        return '\n'.join(lines) + '\n'
    
    return build_tree_string(tree_dict).strip()

@app.command()
def snapshot(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the git repository (defaults to current directory)"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (defaults to [project-name]_[timestamp].md)"
    ),
    include_binary: bool = typer.Option(
        False,
        "--include-binary",
        help="Include binary files as [binary file] markers"
    ),
    max_file_size: int = typer.Option(
        1024 * 1024,  # 1MB
        "--max-size",
        help="Maximum file size in bytes (larger files will be marked as too large)"
    ),
    exclude_patterns: Optional[List[str]] = typer.Option(
        None,
        "--exclude", "-e",
        help="Additional patterns to exclude (can be used multiple times)"
    ),
):
    """Generate a comprehensive project snapshot for AI context."""
    
    # Determine repository path
    repo_path = path or Path.cwd()
    repo_path = repo_path.resolve()
    
    # Check if it's a git repository
    if not (repo_path / '.git').exists():
        console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
        raise typer.Exit(1)
    
    # Get project name and create output filename
    project_name = repo_path.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output:
        output_file = output
    else:
        output_file = repo_path / f"{project_name}_{timestamp}.md"
    
    console.print(f"[cyan]Generating snapshot for:[/cyan] {repo_path}")
    console.print(f"[cyan]Output file:[/cyan] {output_file}")
    
    # Get all git-tracked files
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        # Task 1: Collect files
        task1 = progress.add_task("[yellow]Collecting git-tracked files...", total=None)
        files = get_git_files(repo_path)
        progress.update(task1, completed=100)
        
        console.print(f"[green]Found {len(files)} git-tracked files[/green]")
        
        # Task 2: Filter and process files
        task2 = progress.add_task("[yellow]Processing files...", total=len(files))
        
        text_files = []
        binary_files = []
        large_files = []
        
        for file in files:
            # Check exclusion patterns
            if exclude_patterns:
                skip = False
                for pattern in exclude_patterns:
                    if pattern in str(file.relative_to(repo_path)):
                        skip = True
                        break
                if skip:
                    progress.update(task2, advance=1)
                    continue
            
            # Categorize files
            if is_binary_file(file):
                binary_files.append(file)
            elif file.stat().st_size > max_file_size:
                large_files.append(file)
            else:
                text_files.append(file)
            
            progress.update(task2, advance=1)
        
        console.print(f"[green]Text files: {len(text_files)}[/green]")
        console.print(f"[yellow]Binary files: {len(binary_files)}[/yellow]")
        console.print(f"[yellow]Large files: {len(large_files)}[/yellow]")
        
        # Task 3: Generate markdown
        task3 = progress.add_task("[yellow]Generating markdown...", total=len(text_files))
        
        # Get git info
        git_info = get_git_info(repo_path)
        
        # Build markdown content
        md_lines = []
        
        # Header
        md_lines.append(f"# Project Snapshot: {project_name}")
        md_lines.append("")
        md_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append(f"**Repository:** `{repo_path}`")
        
        if git_info:
            if 'branch' in git_info:
                md_lines.append(f"**Branch:** `{git_info['branch']}`")
            if 'commit' in git_info:
                md_lines.append(f"**Commit:** `{git_info['commit']}` {git_info.get('commit_message', '')}")
            if 'remote' in git_info:
                md_lines.append(f"**Remote:** `{git_info['remote']}`")
        
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
        # File statistics
        md_lines.append("## Statistics")
        md_lines.append("")
        md_lines.append(f"- **Total files tracked:** {len(files)}")
        md_lines.append(f"- **Text files included:** {len(text_files)}")
        md_lines.append(f"- **Binary files:** {len(binary_files)}")
        md_lines.append(f"- **Large files (>{max_file_size:,} bytes):** {len(large_files)}")
        md_lines.append("")
        
        # File tree
        md_lines.append("## Project Structure")
        md_lines.append("")
        md_lines.append("```")
        md_lines.append(format_file_tree(text_files, repo_path))
        md_lines.append("```")
        md_lines.append("")
        
        # File contents
        md_lines.append("## Source Code")
        md_lines.append("")
        md_lines.append("*Note: Files are presented in alphabetical order by path.*")
        md_lines.append("")
        
        # Sort files by relative path
        text_files.sort(key=lambda f: f.relative_to(repo_path))
        
        for file in text_files:
            rel_path = file.relative_to(repo_path)
            
            md_lines.append("---")
            md_lines.append("")
            md_lines.append(f"### `{rel_path}`")
            md_lines.append("")
            
            # Get file size
            file_size = file.stat().st_size
            md_lines.append(f"*Size: {file_size:,} bytes*")
            md_lines.append("")
            
            # Read content
            content = read_file_content(file, max_file_size)
            
            if content:
                # Determine language for syntax highlighting
                language = get_language_from_extension(file)
                
                md_lines.append(f"```{language}")
                md_lines.append(content)
                md_lines.append("```")
            else:
                md_lines.append("*[Unable to read file content]*")
            
            md_lines.append("")
            progress.update(task3, advance=1)
        
        # Add binary files section if requested
        if include_binary and binary_files:
            md_lines.append("---")
            md_lines.append("")
            md_lines.append("## Binary Files")
            md_lines.append("")
            md_lines.append("*These files are binary and not included in the snapshot:*")
            md_lines.append("")
            
            for file in sorted(binary_files, key=lambda f: f.relative_to(repo_path)):
                rel_path = file.relative_to(repo_path)
                file_size = file.stat().st_size
                md_lines.append(f"- `{rel_path}` ({file_size:,} bytes)")
            
            md_lines.append("")
        
        # Add large files section
        if large_files:
            md_lines.append("---")
            md_lines.append("")
            md_lines.append("## Large Files")
            md_lines.append("")
            md_lines.append(f"*These files exceed the size limit of {max_file_size:,} bytes:*")
            md_lines.append("")
            
            for file in sorted(large_files, key=lambda f: f.relative_to(repo_path)):
                rel_path = file.relative_to(repo_path)
                file_size = file.stat().st_size
                md_lines.append(f"- `{rel_path}` ({file_size:,} bytes)")
            
            md_lines.append("")
        
        # Footer
        md_lines.append("---")
        md_lines.append("")
        md_lines.append(f"*Generated by cc-goodies snapshot on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
    # Write to file
    console.print(f"[yellow]Writing snapshot to {output_file}...[/yellow]")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        
        # Get file size
        output_size = output_file.stat().st_size
        
        console.print(f"[green bold]✓ Snapshot generated successfully![/green bold]")
        console.print(f"[green]Output file: {output_file} ({output_size:,} bytes)[/green]")
        console.print(f"[cyan]Contains {len(text_files)} source files from {project_name}[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error writing output file: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()