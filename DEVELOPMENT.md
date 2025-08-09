# Development Guide for Claude Code Goodies

## Environment Setup

This project uses a shared UV environment located at `~/.ai-wiley-uv/`. The project is installed in **editable mode**, meaning code changes take effect immediately without reinstalling.

### Quick Start

```bash
# Option 1: Use the dev helper script (no activation needed)
./dev.sh add some-package    # Add a new dependency
./dev.sh install             # Reinstall the project
./dev.sh list                # List installed packages
./dev.sh run script.py       # Run a Python script

# Option 2: Activate the environment
source ~/.ai-wiley-uv/bin/activate
pip install some-package     # Add dependencies (NOT uv add!)
python -m pytest             # Run tests
deactivate                   # When done
```

### Auto-activation Setup (Optional)

#### Using direnv (Recommended)
```bash
# Install direnv
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# In this directory
echo 'source ~/.ai-wiley-uv/bin/activate' > .envrc
direnv allow
```

Now the environment activates automatically when you enter the directory!

#### Using VS Code
The `.vscode/settings.json` is already configured to use the correct Python interpreter.

## Development Workflow

### Adding Dependencies

**⚠️ IMPORTANT**: Do NOT use `uv add` in this project - it will create a local .venv!

1. **Using dev.sh (Recommended)**
   ```bash
   ./dev.sh add rich
   # Then manually add to pyproject.toml dependencies section
   ```

2. **Using activated environment**
   ```bash
   source ~/.ai-wiley-uv/bin/activate
   pip install rich
   # Then manually add to pyproject.toml dependencies section
   ```

3. **If you accidentally run `uv add`**
   ```bash
   ./dev.sh remove-local-venv  # Cleans up .venv and uv.lock
   ./dev.sh add package-name   # Install in shared environment
   ```

### Testing Changes

Your code changes are immediately available globally because of editable installation:

```bash
# Edit code...
vim cc_goodies/commands/status.py

# Test immediately (no reinstall needed!)
cc-goodies status
```

### Adding New Commands

1. Create a new file in `cc_goodies/commands/`
2. Add the command to `cc_goodies/main.py`
3. Test immediately with `cc-goodies your-command`

### Running Tests

```bash
# If you have tests
source ~/.ai-wiley-uv/bin/activate
python -m pytest

# Or without activation
~/.ai-wiley-uv/bin/python -m pytest
```

## Project Structure

```
claude-code-goodies-in-python/
├── cc_goodies/              # Main package
│   ├── commands/            # CLI commands
│   │   ├── progress.py      # Progress tracking command
│   │   └── status.py        # Status display with rich
│   ├── core/                # Core functionality
│   └── main.py              # CLI entry point
├── claude_progress_pkg/     # Legacy progress module
├── pyproject.toml           # Project configuration
├── dev.sh                   # Development helper script
├── .python-version          # Points to ~/.ai-wiley-uv/bin/python
└── DEVELOPMENT.md           # This file
```

## Important Notes

1. **No .venv needed**: The project uses the shared `~/.ai-wiley-uv/` environment
2. **Editable install**: Code changes take effect immediately
3. **Global commands**: `cc-goodies` and `claude-progress` are available system-wide
4. **Shared environment**: This environment is shared with other projects in the ai-wiley collection

## Troubleshooting

### Command not found
Ensure `~/.local/bin` is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Dependencies not installing
The shared environment might need the full project reinstall:
```bash
cd /Users/wei/Projects/AI-ML/ai-wiley/nx/ai-energy-miracle/packages/apps/python/
./setup_all_packages_uv.sh
```

### Python version issues
Check that `.python-version` points to the correct environment:
```bash
cat .python-version  # Should show: ~/.ai-wiley-uv/bin/python
```

## Tips

- Use `./dev.sh` for quick dependency management without activation
- Changes to code are instant - no rebuild needed
- The rich library is available for beautiful CLI output
- Keep dependencies minimal as this is a shared environment