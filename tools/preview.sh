#!/usr/bin/env bash
# Rendert die Karten einer cards.json als PNG-Vorschau – im Vorschau-Container.
#
#   ./tools/preview.sh decks/skript.cards.json
#   -> decks/preview/skript/*.png + index.html
#
# Erster Aufruf baut das (groessere) Vorschau-Image automatisch.
set -euo pipefail

IMAGE="anki-karten-preview"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es (beim ersten Mal dauert das etwas)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.preview" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"
