#!/usr/bin/env bash
# Renders the cards of a cards.json as PNG previews — inside the preview container.
#
#   ./tools/preview.sh decks/script.cards.json
#   -> decks/preview/script/*.png + index.html
#
# The first run builds the (larger) preview image automatically.
set -euo pipefail

IMAGE="anki-cards-preview"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=tools/_dockerlib.sh
. "$PROJECT_DIR/tools/_dockerlib.sh"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' missing – building it (takes a while the first time)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.preview" -t "$IMAGE" "$PROJECT_DIR"
fi

map_paths "$@"
exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" \
  ${MAPPED[@]+"${MAPPED[@]}"}
