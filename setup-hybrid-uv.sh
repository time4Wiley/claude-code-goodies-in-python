#!/bin/bash
# Setup Hybrid UV Environment for Python Projects
# This script sets up a shared UV environment at ~/.ai-wiley-uv for editable development
# Usage: ./setup-hybrid-uv.sh [/path/to/repo]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
UV_VENV="$HOME/.ai-wiley-uv"
PYTHON_VERSION="3.12"
SCRIPTS_DIR="$HOME/.local/bin"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Get the target repository path
if [ -z "$1" ]; then
    REPO_PATH="$(pwd)"
    print_info "No path provided, using current directory: $REPO_PATH"
else
    REPO_PATH="$(cd "$1" && pwd)"
    print_info "Setting up hybrid UV environment for: $REPO_PATH"
fi

# Verify it's a valid Python project
if [ ! -f "$REPO_PATH/pyproject.toml" ]; then
    print_error "No pyproject.toml found in $REPO_PATH"
    echo "This script requires a UV-managed Python project with pyproject.toml"
    exit 1
fi

# Get project name from pyproject.toml
PROJECT_NAME=$(grep -m1 "^name = " "$REPO_PATH/pyproject.toml" | sed 's/name = "\(.*\)"/\1/')
if [ -z "$PROJECT_NAME" ]; then
    print_warning "Could not extract project name from pyproject.toml"
    PROJECT_NAME=$(basename "$REPO_PATH")
    print_info "Using directory name as project name: $PROJECT_NAME"
fi

echo ""
print_info "🚀 Setting up hybrid UV environment for: $PROJECT_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Check for uv
if ! command -v uv &> /dev/null; then
    print_error "uv not found. Installing uv first..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.cargo/env"
    print_success "uv installed successfully"
fi

# Step 2: Create or verify the shared UV environment
if [ ! -d "$UV_VENV" ]; then
    print_info "Creating shared UV environment at $UV_VENV..."
    uv venv "$UV_VENV" --python "$PYTHON_VERSION"
    print_success "Created new shared environment with Python $PYTHON_VERSION"
else
    print_info "Using existing shared environment at $UV_VENV"
    # Verify Python version
    CURRENT_VERSION=$("$UV_VENV/bin/python" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_info "Current Python version: $CURRENT_VERSION"
fi

# Step 3: Install the package in editable mode
print_info "Installing $PROJECT_NAME in editable mode..."
if uv pip install --python "$UV_VENV/bin/python" -e "$REPO_PATH"; then
    print_success "Package installed in editable mode"
else
    print_error "Failed to install package"
    exit 1
fi

# Step 4: Create .python-version file
print_info "Creating .python-version file..."
echo "$UV_VENV/bin/python" > "$REPO_PATH/.python-version"
print_success "Created .python-version pointing to shared environment"

# Step 5: Extract and create wrapper scripts for CLI commands
print_info "Looking for CLI scripts in pyproject.toml..."

# Extract scripts using Python
SCRIPTS=$("$UV_VENV/bin/python" - "$REPO_PATH" << 'EOF'
import toml
import sys
import os

repo_path = sys.argv[1]
pyproject_path = os.path.join(repo_path, 'pyproject.toml')

try:
    config = toml.load(pyproject_path)
    scripts = {}
    
    # Check for project.scripts (standard Python packaging)
    if 'project' in config and 'scripts' in config['project']:
        scripts = config['project']['scripts']
    # Also check for tool.poetry.scripts (Poetry)
    elif 'tool' in config and 'poetry' in config['tool'] and 'scripts' in config['tool']['poetry']:
        scripts = config['tool']['poetry']['scripts']
    
    for script_name in scripts:
        print(script_name)
except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
EOF
)

if [ -n "$SCRIPTS" ]; then
    mkdir -p "$SCRIPTS_DIR"
    print_info "Creating wrapper scripts in $SCRIPTS_DIR..."
    
    for script_name in $SCRIPTS; do
        script_path="$SCRIPTS_DIR/$script_name"
        
        # Remove existing symlink if present
        if [ -L "$script_path" ]; then
            rm "$script_path"
            print_warning "Removed existing symlink: $script_name"
        fi
        
        # Create wrapper script
        cat > "$script_path" << EOF
#!/bin/bash
exec "$UV_VENV/bin/$script_name" "\$@"
EOF
        chmod +x "$script_path"
        print_success "Created wrapper: $script_name"
    done
else
    print_info "No CLI scripts found in pyproject.toml"
fi

# Step 6: Create dev.sh helper script
print_info "Creating dev.sh helper script..."
cat > "$REPO_PATH/dev.sh" << 'EOF'
#!/bin/bash
# Development helper script for hybrid UV environment

UV_PYTHON="$HOME/.ai-wiley-uv/bin/python"

case "$1" in
  add)
    shift
    # Install in the shared environment
    uv pip install --python "$UV_PYTHON" "$@"
    echo ""
    echo "✅ Installed $@ in shared environment"
    echo "⚠️  Remember to manually add to pyproject.toml dependencies if needed"
    ;;
  install)
    # Reinstall this package in editable mode
    uv pip install --python "$UV_PYTHON" -e .
    echo "✅ Reinstalled package in editable mode"
    ;;
  list)
    # List installed packages
    uv pip list --python "$UV_PYTHON"
    ;;
  run)
    # Run a Python script with the shared environment
    shift
    "$UV_PYTHON" "$@"
    ;;
  remove-local-venv)
    # Clean up any local .venv created by accident
    rm -rf .venv uv.lock
    echo "✅ Removed local .venv and uv.lock"
    ;;
  *)
    echo "Usage: ./dev.sh {add|install|list|run|remove-local-venv}"
    echo "  add <package>         - Add a new package to shared environment"
    echo "  install               - Reinstall this package in editable mode"
    echo "  list                  - List installed packages"
    echo "  run <script>          - Run a Python script"
    echo "  remove-local-venv     - Remove local .venv if accidentally created"
    ;;
esac
EOF
chmod +x "$REPO_PATH/dev.sh"
print_success "Created dev.sh helper script"

# Step 7: Create or update .envrc for direnv (optional)
if command -v direnv &> /dev/null; then
    print_info "direnv detected, creating .envrc file..."
    echo "source $UV_VENV/bin/activate" > "$REPO_PATH/.envrc"
    print_success "Created .envrc for automatic environment activation"
    print_info "Run 'direnv allow' in the project directory to enable auto-activation"
fi

# Step 8: Update .gitignore if needed
if [ -f "$REPO_PATH/.gitignore" ]; then
    # Check if .python-version is already unignored
    if ! grep -q "^# \.python-version" "$REPO_PATH/.gitignore"; then
        print_info "Updating .gitignore to keep .python-version..."
        # Comment out any .python-version entry
        sed -i '' 's/^\.python-version$/# .python-version  # Unignored for hybrid UV setup/' "$REPO_PATH/.gitignore"
    fi
fi

# Final summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "✨ Hybrid UV environment setup complete!"
echo ""
echo "📦 Project: $PROJECT_NAME"
echo "📂 Location: $REPO_PATH"
echo "🐍 Python: $UV_VENV/bin/python"
echo ""
echo "🚀 Quick Start:"
echo "   cd $REPO_PATH"
echo "   ./dev.sh add <package>    # Add dependencies"
echo "   ./dev.sh install          # Reinstall after changes"
echo "   ./dev.sh run script.py    # Run Python scripts"
echo ""
echo "💡 Tips:"
echo "   • Code changes take effect immediately (editable mode)"
echo "   • Use ./dev.sh to manage dependencies"
echo "   • VS Code will auto-detect the Python interpreter"

if [ -n "$SCRIPTS" ]; then
    echo ""
    echo "🔧 CLI Commands Available:"
    for script_name in $SCRIPTS; do
        echo "   • $script_name"
    done
fi

if [ ! -d "$HOME/.local/bin" ] || ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    print_warning "Add ~/.local/bin to your PATH for global command access:"
    echo '   export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
print_info "Run 'source $UV_VENV/bin/activate' to activate the environment manually"