#!/usr/bin/env bash
# Konvertiert Quell-PDFs in maschinenlesbares Markdown – im Extract-Container
# (PyMuPDF + Tesseract-OCR-Fallback fuer gescannte Seiten).
#
#   ./tools/extract.sh quellen/Biologie/kapitel3.pdf
#   ./tools/extract.sh quellen/Biologie/       # ganzen Themenordner
#   -> aufbereitet/Biologie/<name>.md
#
# Erster Aufruf baut das Image automatisch.
set -euo pipefail

IMAGE="anki-karten-extract"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt – baue es (beim ersten Mal dauert das etwas)..." >&2
  docker build -f "$PROJECT_DIR/Dockerfile.extract" -t "$IMAGE" "$PROJECT_DIR"
fi

docker run --rm --user "$(id -u):$(id -g)" -v "$PROJECT_DIR":/work "$IMAGE" "$@"

# Abbildungs-Index aktualisieren (stdlib-Python, kein Docker) – ueber die erzeugten .md.
# Ergaenzt aufbereitet/<Thema>/<name>.figures.md + Per-Seite-Marker "· N Abb.".
if [ -d "$PROJECT_DIR/aufbereitet" ]; then
  python3 "$PROJECT_DIR/tools/figindex.py" "$PROJECT_DIR/aufbereitet" \
    || echo "Hinweis: Abbildungs-Index konnte nicht erstellt werden (figindex.py)." >&2
fi
