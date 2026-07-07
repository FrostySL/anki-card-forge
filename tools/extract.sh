#!/usr/bin/env bash
# Converts source PDFs into machine-readable Markdown — inside the extract
# container (PyMuPDF + Tesseract OCR fallback for scanned pages).
#
#   ./tools/extract.sh sources/Biology/chapter3.pdf
#   ./tools/extract.sh sources/Biology/       # whole topic folder
#   -> extracted/Biology/<name>.md
#
# The first run builds the image automatically.
set -euo pipefail

IMAGE="anki-cards-extract"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/_dockerlib.sh
. "$PROJECT_DIR/tools/_dockerlib.sh"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' missing – building it (takes a while the first time)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.extract" -t "$IMAGE" "$PROJECT_DIR"
fi

map_paths "$@"
docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" \
  ${MAPPED[@]+"${MAPPED[@]}"}

# Update the figure index (stdlib Python, no Docker) over the generated .md files.
# Adds extracted/<topic>/<name>.figures.md + per-page markers "· N fig.".
if [ -d "$PROJECT_DIR/extracted" ]; then
  python3 "$PROJECT_DIR/tools/figindex.py" "$PROJECT_DIR/extracted" \
    || echo "Note: figure index could not be created (figindex.py)." >&2
fi
