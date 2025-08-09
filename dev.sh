#!/bin/bash
# Development helper script
UV_PYTHON="$HOME/.ai-wiley-uv/bin/python"

case "$1" in
  add)
    shift
    # Install in the shared environment and update pyproject.toml
    uv pip install --python "$UV_PYTHON" "$@"
    echo ""
    echo "✅ Installed $@ in shared environment"
    echo "⚠️  Remember to manually add to pyproject.toml dependencies if needed"
    ;;
  install)
    uv pip install --python "$UV_PYTHON" -e .
    ;;
  list)
    "$UV_PYTHON" -m pip list
    ;;
  run)
    shift
    "$UV_PYTHON" "$@"
    ;;
  remove-local-venv)
    # Clean up any local .venv created by uv add
    rm -rf .venv uv.lock
    echo "✅ Removed local .venv and uv.lock"
    ;;
  *)
    echo "Usage: ./dev.sh {add|install|list|run|remove-local-venv}"
    echo "  add <package>         - Add a new package to shared environment"
    echo "  install               - Reinstall this package"
    echo "  list                  - List installed packages"
    echo "  run <script>          - Run a Python script"
    echo "  remove-local-venv     - Remove local .venv if accidentally created"
    ;;
esac