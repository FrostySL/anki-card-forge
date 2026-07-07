#!/usr/bin/env bash
# Builds an .apkg package from card JSON file(s) — inside the Docker container.
#
#   ./tools/build.sh decks/script.cards.json [decks/script.apkg]
#
# A missing image is built automatically (docker build -t anki-cards .).
set -euo pipefail

IMAGE="anki-cards"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/_dockerlib.sh
. "$PROJECT_DIR/tools/_dockerlib.sh"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' missing – building it..." >&2
  docker build -t "$IMAGE" "$PROJECT_DIR"
fi

map_paths "$@"
exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" \
  ${MAPPED[@]+"${MAPPED[@]}"}
