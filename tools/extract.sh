#!/usr/bin/env bash
# Konvertiert Quell-PDFs in maschinenlesbares Markdown – im Extract-Container
# (PyMuPDF + Tesseract-OCR-Fallback fuer gescannte Seiten).
#
#   ./tools/extract.sh quellen/EWP/03_Arbeitstechniken.pdf
#   ./tools/extract.sh quellen/EWP/            # ganzen Themenordner
#   -> aufbereitet/EWP/<name>.md
#
# Erster Aufruf baut das Image automatisch.
set -euo pipefail

IMAGE="anki-karten-extract"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es (beim ersten Mal dauert das etwas)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.extract" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"
