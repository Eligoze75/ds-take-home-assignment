#!/usr/bin/env bash
# Resolves a Python 3.12+ interpreter and prints its path on stdout.
#
# xgboost==3.4.1 and shap==0.52.0 in requirements.txt both require Python
# >=3.12, so `make venv` needs one even if the active `python3` on PATH
# (conda, pyenv, system) is older.
#
# This always uses a standalone, project-local CPython 3.12 managed by uv
# under .tools/python/ (same no-sudo approach as the Quarto/TinyTeX installs
# in install_tools.sh) -- it deliberately does NOT rely on uv's system/PATH
# discovery (--managed-python; see `uv python find --help`): on real
# machines, uv's system/conda discovery has handed back an active conda env
# interpreter that was NOT actually Python 3.12+, silently breaking the venv.
# Using only the interpreter uv manages itself removes that whole class of
# mismatch. (Note: `--python-preference only-managed` looks like it should do
# the same thing and is accepted without error by some uv versions, but does
# NOT reliably exclude system interpreters -- that's exactly what broke this
# the first time. `--managed-python` is the documented, stable flag.)
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

# Downloads into $PY_INSTALL_DIR if not already there; no-op (fast) otherwise.
# Never touches the system/conda Python. --managed-python forces uv to only
# consider interpreters it manages itself, never a system/conda one.
echo "resolving a project-local Python $REQUIRED (downloading into .tools/python/ if needed)" >&2
"$UV_BIN" python install "$REQUIRED" --managed-python >&2

PYTHON_BIN="$("$UV_BIN" python find "$REQUIRED" --managed-python)"

# Defense in depth: verify the resolved interpreter really is >=3.12 before
# handing it back, instead of trusting path/version-string discovery blindly.
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)'; then
  echo "error: resolved interpreter '$PYTHON_BIN' is not Python 3.12+" >&2
  "$PYTHON_BIN" --version >&2 || true
  exit 1
fi

printf '%s\n' "$PYTHON_BIN"
