#!/bin/bash
# Development helper script
UV_PYTHON="$HOME/.ai-wiley-uv/bin/python"

case "$1" in
  add)
    shift
    uv pip install --python "$UV_PYTHON" "$@"
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
  *)
    echo "Usage: ./dev.sh {add|install|list|run}"
    echo "  add <package>    - Add a new package"
    echo "  install          - Reinstall this package"
    echo "  list             - List installed packages"
    echo "  run <script>     - Run a Python script"
    ;;
esac