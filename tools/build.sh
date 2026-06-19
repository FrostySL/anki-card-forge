#!/usr/bin/env bash
# Baut aus einer Karten-JSON-Datei ein .apkg-Paket – im Docker-Container.
#
#   ./tools/build.sh decks/skript.cards.json [decks/skript.apkg]
#
# Voraussetzung: Image einmalig bauen mit  docker build -t anki-karten .
set -euo pipefail

IMAGE="anki-karten"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es..." >&2
  docker build -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"
