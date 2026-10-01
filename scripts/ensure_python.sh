#!/usr/bin/env bash
# Resolves a Python 3.12+ interpreter and prints its path on stdout.
#
# xgboost==3.4.1 and shap==0.52.0 in requirements.txt both require Python
# >=3.12, so `make venv` needs one even if the active `python3` on PATH
# (conda, pyenv, system) is older. This never touches system Python:
#   1. Ask uv to resolve Python 3.12 -- it reuses a system/already-installed
#      3.12+ interpreter if one is findable.
#   2. Otherwise uv downloads a standalone, project-local CPython 3.12 build
#      into .tools/python/ (same no-sudo approach as the Quarto/TinyTeX
#      installs in install_tools.sh) and uses that instead.
# uv itself is installed into .tools/uv/ if it isn't already on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
UV_DIR="$TOOLS/uv"
UV_BIN="$UV_DIR/uv"
PY_INSTALL_DIR="$TOOLS/python"
REQUIRED="3.12"

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
  else
    mkdir -p "$UV_DIR"
    echo "installing uv (to find or fetch Python $REQUIRED+, no sudo required)" >&2
    curl -fsSL https://astral.sh/uv/install.sh \
      | env UV_INSTALL_DIR="$UV_DIR" UV_NO_MODIFY_PATH=1 sh >&2
  fi
fi

mkdir -p "$PY_INSTALL_DIR"
export UV_PYTHON_INSTALL_DIR="$PY_INSTALL_DIR"

# No-op if a usable 3.12+ is already findable; otherwise downloads one into
# $PY_INSTALL_DIR instead of touching the system/conda Python.
echo "resolving Python $REQUIRED+ (via system install or a project-local download)" >&2
"$UV_BIN" python install "$REQUIRED" >&2

"$UV_BIN" python find "$REQUIRED"
