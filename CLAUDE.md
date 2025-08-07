# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code Goodies is a collection of CLI tools for enhancing the Claude AI experience. Currently features a progress tracker for the `claude -p` command, built with Typer for a modern CLI experience.

## Architecture

### Package Structure
- **`cc_goodies/`**: Main package using Typer CLI framework
  - `main.py`: Entry point with Typer app, handles versioning and subcommand registration
  - `commands/progress.py`: Progress tracking subcommand implementation
  - `core/progress_tracker.py`: Core logic for Claude progress tracking (spinner, JSON parsing, subprocess management)
- **`claude_progress_pkg/`**: Legacy package for backward compatibility
- Both packages are included in the distribution to maintain compatibility

### Key Design Patterns
- **Typer-based CLI**: Extensible command structure ready for additional subcommands
- **Subprocess Wrapper**: The progress tracker wraps the `claude` binary, parsing streaming JSON output
- **Thread-based Animation**: Spinner runs in a separate thread to avoid blocking output processing

## Development Commands

### Running the CLI
```bash
# During development (editable mode via pipx - recommended)
cc-goodies progress "your query"
cg progress "your query"  # alias

# Via uv in development
uv run cc-goodies progress "your query"
```

### Installation for Development
```bash
# Recommended: Use pipx for editable installation
~/App.configs/scripts/install-cc-goodies-pipx.sh

# Alternative: Direct pip install
pip install -e . --user
```

### Building and Publishing
```bash
# Build distribution
python -m build

# Publishing is handled via GitHub Actions on release
# Uses OIDC authentication - no PyPI tokens needed
```

### Testing CLI Commands
```bash
# Test version display
cc-goodies --version

# Test help
cc-goodies --help
cc-goodies progress --help

# Test with different models
cc-goodies progress --model sonnet "test query"
```

## Key Implementation Details

### Claude Binary Discovery
The tool searches for the `claude` binary in this order:
1. `$CLAUDE_PATH` environment variable
2. System PATH
3. Common locations: `/Users/wei/bin/claude`, `/usr/local/bin/claude`, `/opt/homebrew/bin/claude`, `~/bin/claude`

### Progress Tracking Flow
1. Constructs claude command with required flags: `--dangerously-skip-permissions`, `-p`, `--output-format stream-json`, `--verbose`
2. Launches claude as subprocess, capturing stdout/stderr
3. Parses streaming JSON for `assistant` messages (turn count) and `result` (final output)
4. Displays spinner with elapsed time, turn count, and content preview on stderr
5. Outputs final result to stdout

### Adding New Subcommands
1. Create new module in `cc_goodies/commands/`
2. Define command function with Typer decorators
3. Register in `main.py` using `app.command()`

## Shell Integration

- Shell alias `cg` is configured in `~/App.configs/zsh/zshrc.sh`
- Auto-completion available via `cc-goodies --install-completion` (requires actual terminal, not `uv run`)

## GitHub Actions

- **Publish to PyPI**: Triggered on releases, uses OIDC authentication
- No manual PyPI token management required