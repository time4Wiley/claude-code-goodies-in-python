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
