# claude-progress

A lightweight progress tracker for `claude -p` command that shows thinking time, turn counts, and content previews.

## Features

- 🔄 Animated progress spinner
- ⏱️ Elapsed time tracking  
- 🔢 Turn counter
- 👀 Content preview during thinking
- 🎯 Clean output
- 🚀 Zero dependencies - uses only Python standard library

## Installation

### Direct Usage (Recommended)

Clone the repository and use the script directly:

```bash
git clone https://github.com/time4wiley/claude-progress.git
cd claude-progress
./claude_progress.py "Your question here"
```

### Via pip/uv

```bash
# Using pip
pip install claude-progress

# Using uv
uv pip install claude-progress
```

## Usage

```bash
# Default usage (uses opus model)
./claude_progress.py "What is the meaning of life?"

# No quotes needed for multi-word queries
./claude_progress.py explain how git rebase works

# Override model (default is opus)
./claude_progress.py --model sonnet "Complex mathematical proof"

# All arguments after flags are joined as the query
./claude_progress.py tell me about quantum computing in simple terms
```

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

## Integration with Shell

If you're using the App.configs setup, this tool integrates seamlessly with existing `cl` and `cls` aliases when the `-p` flag is used.

## Requirements

- Python 3.9 or higher
- `claude` CLI installed and accessible

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Author

Created by Wei ([time4wiley](https://github.com/time4wiley))