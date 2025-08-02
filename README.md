# Claude Code Goodies

A collection of useful tools for Claude AI, featuring a Typer-based CLI with auto-completion support.

## Features

### Progress Tracker
A lightweight progress tracker for `claude -p` command that shows thinking time, turn counts, and content previews.

- 🔄 Animated progress spinner
- ⏱️ Elapsed time tracking  
- 🔢 Turn counter
- 👀 Content preview during thinking
- 🎯 Clean output
- 🚀 Built with Typer for modern CLI experience

## Installation

### Using pip/uv (Recommended)

```bash
# Using pip
pip install claude-code-goodies

# Using uv (faster)
uv pip install claude-code-goodies
```

### Development Installation

```bash
git clone https://github.com/time4wiley/claude-code-goodies-in-python.git
cd claude-code-goodies-in-python
uv pip install -e .
```

## Usage

### Progress Tracker

```bash
# Using the full command
cc-goodies progress "What is the meaning of life?"

# Using the alias (after shell restart)
cg progress explain how git rebase works

# Override model (default is opus)
cg progress --model sonnet "Complex mathematical proof"

# No quotes needed for multi-word queries
cg progress tell me about quantum computing in simple terms
```

### Auto-completion

Enable shell auto-completion:

```bash
# Install completion for your shell (run in terminal, not through uv)
cc-goodies --install-completion

# Or using the alias
cg --install-completion
```

Note: The shell completion feature requires running from an actual terminal session, not through `uv run`.

## Configuration

### Claude Binary Location

The tool automatically searches for the `claude` binary in:
1. `$CLAUDE_PATH` environment variable (if set)
2. System PATH
3. Common locations (`/usr/local/bin/claude`, `~/bin/claude`, etc.)

To specify a custom location:
```bash
export CLAUDE_PATH=/path/to/your/claude
```

## How It Works

`claude-progress` wraps the `claude -p` command and:
1. Automatically adds required flags: `--output-format stream-json --verbose`
2. Parses the streaming JSON output
3. Displays an animated progress indicator with:
   - Elapsed time
   - Turn counter
   - Preview of Claude's current thinking
4. Shows clean final output
5. Reports completion statistics

## Shell Alias

After installation, you can use the `cg` alias (if you've added it to your shell config) for quick access:

```bash
# Equivalent commands
cc-goodies progress "your query"
cg progress "your query"
```

## Requirements

- Python 3.9 or higher
- `claude` CLI installed and accessible

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Author

Created by Wei ([time4wiley](https://github.com/time4wiley))