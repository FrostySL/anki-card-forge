#!/usr/bin/env bash
# Validiert eine .apkg in der echten Anki-Engine (Backend, ohne GUI).
#
#   ./tools/validate.sh decks/skript.apkg
#
# Erster Aufruf baut das Validate-Image automatisch.
set -euo pipefail

IMAGE="anki-karten-validate"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.validate" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"
