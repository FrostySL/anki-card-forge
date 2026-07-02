#!/usr/bin/env bash
# Validates an .apkg in the real Anki engine (backend, no GUI).
#
#   ./tools/validate.sh decks/script.apkg
#
# The first run builds the validate image automatically.
set -euo pipefail

IMAGE="anki-cards-validate"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' missing – building it..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.validate" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"
