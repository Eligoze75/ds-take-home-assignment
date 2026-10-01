#!/usr/bin/env bash
# Resolves a Python 3.12+ interpreter and prints its path on stdout.
#
# xgboost==3.4.1 and shap==0.52.0 in requirements.txt both require Python
# >=3.12, so `make venv` needs one even if the active `python3` on PATH
# (conda, pyenv, system) is older.
#
# This always uses a standalone, project-local CPython 3.12 managed by uv
# under .tools/python/ (same no-sudo approach as the Quarto/TinyTeX installs
# in install_tools.sh). It deliberately does NOT use `uv python find` to
# resolve the interpreter: on real machines, `uv python find 3.12` -- even
# with `--managed-python` / `--python-preference only-managed` -- has
# returned an active conda env's interpreter that uv's own `uv python list`
# miscategorizes as satisfying "3.12", which is not actually Python 3.12+.
# That's an inconsistency in uv's own discovery/registry, not something a
# flag reliably fixes across versions. So instead: use uv only to download
# the interpreter, then locate the resulting binary ourselves by globbing
# its known, documented install layout (cpython-<ver>-<os>-<arch>-<variant>/
# bin/python<major>.<minor>) -- deterministic, no uv discovery involved.
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

# Locate the binary ourselves instead of trusting `uv python find` (see note
# above). Install dirs look like cpython-3.12.14-macos-aarch64-none/; pick
# the newest if more than one patch version ever ends up installed.
PYTHON_BIN="$(find "$PY_INSTALL_DIR" -maxdepth 3 -type f -name "python${REQUIRED}" -path '*/bin/*' 2>/dev/null \
  | sort -V | tail -1)"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "error: uv reported Python $REQUIRED installed, but no bin/python${REQUIRED} was found under $PY_INSTALL_DIR" >&2
  exit 1
fi

# Defense in depth: verify the resolved interpreter really is >=3.12 before
# handing it back, instead of trusting path/version-string discovery blindly.
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)'; then
  echo "error: resolved interpreter '$PYTHON_BIN' is not Python 3.12+" >&2
  "$PYTHON_BIN" --version >&2 || true
  exit 1
fi

printf '%s\n' "$PYTHON_BIN"
