#!/usr/bin/env bash
# OCR-Label-Erkennung in einem Bild – im Vorschau-Container (enthaelt Tesseract).
#
#   ./tools/detect.sh quellen/bild.png [--lang deu+eng] [--min-conf 40]
#   -> quellen/bild.labels.json + quellen/bild.labels.png
set -euo pipefail

IMAGE="anki-karten-preview"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es (beim ersten Mal dauert das etwas)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.preview" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work \
  --entrypoint python "$IMAGE" /work/tools/detect_labels.py "$@"
