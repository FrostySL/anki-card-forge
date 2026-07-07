#!/usr/bin/env bash
# Crops figures out of source PDFs as PNGs — inside the extract container (PyMuPDF).
#
#   ./tools/figextract.sh sources/SWT/04_UML.pdf
#   ./tools/figextract.sh sources/SWT/            # whole topic folder
#   -> extracted/SWT/figures/<name>_p<page>_<i>.png + extracted/SWT/<name>.figures.json
#
# Uses the same image as tools/extract.sh (built automatically on first use).
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
exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work \
  --entrypoint python "$IMAGE" /work/tools/figextract.py ${MAPPED[@]+"${MAPPED[@]}"}
