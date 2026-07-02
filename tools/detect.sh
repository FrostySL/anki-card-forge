#!/usr/bin/env bash
# OCR label detection in an image — inside the preview container (has Tesseract).
#
#   ./tools/detect.sh sources/image.png [--lang eng+deu] [--min-conf 40]
#   -> sources/image.labels.json + sources/image.labels.png
set -euo pipefail

IMAGE="anki-cards-preview"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' missing – building it (takes a while the first time)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.preview" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work \
  --entrypoint python "$IMAGE" /work/tools/detect_labels.py "$@"
