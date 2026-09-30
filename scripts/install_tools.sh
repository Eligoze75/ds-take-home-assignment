#!/usr/bin/env bash
# Quarto, TinyTeX (xelatex + pdflatex), and the MiniLM weights.
# make setup runs this so make all does not need the network.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
QUARTO_VERSION="1.7.33"
TINYTEX_VERSION="2026.09"
mkdir -p "$TOOLS"

os="$(uname -s)"
arch="$(uname -m)"
case "$os-$arch" in
  Darwin-*)
    quarto_asset="quarto-${QUARTO_VERSION}-macos.tar.gz"
    tinytex_asset="TinyTeX-1-darwin-v${TINYTEX_VERSION}.tar.xz"
    ;;
  Linux-x86_64)
    quarto_asset="quarto-${QUARTO_VERSION}-linux-amd64.tar.gz"
    tinytex_asset="TinyTeX-1-linux-x86_64-v${TINYTEX_VERSION}.tar.xz"
    ;;
  Linux-aarch64|Linux-arm64)
    quarto_asset="quarto-${QUARTO_VERSION}-linux-arm64.tar.gz"
    tinytex_asset="TinyTeX-1-linux-arm64-v${TINYTEX_VERSION}.tar.xz"
    ;;
  *)
    echo "unsupported platform: $os $arch" >&2
    exit 1
    ;;
esac

if [[ ! -x "$TOOLS/quarto/bin/quarto" ]]; then
  echo "installing Quarto ${QUARTO_VERSION}"
  stage="$(mktemp -d)"
  curl -fsSL \
    "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/${quarto_asset}" \
    -o "$stage/quarto.tar.gz"
  rm -rf "$stage/extract"
  mkdir -p "$stage/extract"
  tar -xzf "$stage/quarto.tar.gz" -C "$stage/extract"
  rm -rf "$TOOLS/quarto"
  if [[ -x "$stage/extract/bin/quarto" ]]; then
    mkdir -p "$TOOLS/quarto"
    mv "$stage/extract"/* "$TOOLS/quarto/"
  else
    mv "$stage/extract"/quarto-* "$TOOLS/quarto"
  fi
  rm -rf "$stage"
fi

texbin() {
  local dir
  dir="$(ls -d "$TOOLS"/TinyTeX/bin/*/ 2>/dev/null | head -1 || true)"
  if [[ -z "$dir" ]]; then
    return 1
  fi
  printf '%s' "${dir%/}"
}

if ! texbin >/dev/null 2>&1 || [[ ! -x "$(texbin)/xelatex" ]] || [[ ! -x "$(texbin)/pdflatex" ]]; then
  echo "installing TinyTeX ${TINYTEX_VERSION}"
  stage="$(mktemp -d)"
  curl -fsSL \
    "https://github.com/rstudio/tinytex-releases/releases/download/v${TINYTEX_VERSION}/${tinytex_asset}" \
    -o "$stage/tinytex.tar.xz"
  mkdir -p "$stage/extract"
  tar -xJf "$stage/tinytex.tar.xz" -C "$stage/extract"
  rm -rf "$TOOLS/TinyTeX"
  tops=()
  while IFS= read -r line; do
    tops+=("$line")
  done < <(find "$stage/extract" -mindepth 1 -maxdepth 1)
  if [[ "${#tops[@]}" -eq 1 && -d "${tops[0]}" ]]; then
    mv "${tops[0]}" "$TOOLS/TinyTeX"
  else
    mv "$stage/extract" "$TOOLS/TinyTeX"
  fi
  rm -rf "$stage"
fi

TEXBIN="$(texbin)"
export PATH="$TEXBIN:$TOOLS/quarto/bin:$PATH"

# Helvetica ships with macOS. On a machine without it, alias the TeX Gyre
# Helvetica clone so xelatex can still resolve mainfont: Helvetica.
if ! fc-list Helvetica 2>/dev/null | grep -q .; then
  "$TEXBIN/tlmgr" install tex-gyre
  font_dir="$(find "$TOOLS/TinyTeX" -type d -path '*/tex-gyre' | head -1)"
  cat > "$TOOLS/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>${font_dir}</dir>
  <alias>
    <family>Helvetica</family>
    <prefer><family>TeX Gyre Heros</family></prefer>
  </alias>
</fontconfig>
EOF
fi

if [[ ! -f "$TOOLS/.latex-ready" ]]; then
  echo "installing the LaTeX packages the reports use"
  probe="$(mktemp -d)"
  cat > "$probe/xelatex.qmd" <<'EOF'
---
format:
  pdf:
    pdf-engine: xelatex
    mainfont: Helvetica
    include-in-header:
      text: |
        \usepackage{float}
        \usepackage{parskip}
        \usepackage{caption}
        \usepackage{enumitem}
        \usepackage{booktabs}
---

A plot is not required to load these packages.
EOF
  cat > "$probe/pdflatex.qmd" <<'EOF'
---
format:
  pdf:
    pdf-engine: pdflatex
    include-in-header:
      text: |
        \usepackage{parskip}
        \usepackage{caption}
        \usepackage{enumitem}
---

Probe.
EOF
  if [[ -f "$TOOLS/fonts.conf" ]]; then
    export FONTCONFIG_FILE="$TOOLS/fonts.conf"
  fi
  QUARTO_PYTHON="$ROOT/.venv/bin/python" quarto render "$probe/xelatex.qmd" --output-dir "$probe/out"
  QUARTO_PYTHON="$ROOT/.venv/bin/python" quarto render "$probe/pdflatex.qmd" --output-dir "$probe/out"
  rm -rf "$probe"
  touch "$TOOLS/.latex-ready"
fi

echo "downloading ${ROOT} embedding model"
PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -c "
from sentence_transformers import SentenceTransformer
from src.item_search.config import EMBEDDING_MODEL
SentenceTransformer(EMBEDDING_MODEL)
"
echo "tools ready"
