#!/usr/bin/env bash
# Schneidet Abbildungen aus Quell-PDFs als PNG heraus – im Extract-Container (PyMuPDF).
#
#   ./tools/figextract.sh quellen/SWT/04_UML.pdf
#   ./tools/figextract.sh quellen/SWT/            # ganzen Themenordner
#   -> aufbereitet/SWT/figures/<name>_S<Seite>_<i>.png + aufbereitet/SWT/<name>.figures.json
#
# Nutzt dasselbe Image wie tools/extract.sh (baut es beim ersten Mal automatisch).
set -euo pipefail

IMAGE="anki-karten-extract"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es (beim ersten Mal dauert das etwas)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.extract" -t "$IMAGE" "$PROJECT_DIR"
fi

exec docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work \
  --entrypoint python "$IMAGE" /work/tools/figextract.py "$@"
