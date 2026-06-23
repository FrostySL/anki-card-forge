#!/usr/bin/env bash
# One-Shot-Quellenaufbereitung: PDF -> Markdown (+ Abbildungs-Index) UND Bild-Crops.
# Bündelt extract.sh (extract.py -> .md, dann figindex.py -> .figures.md) und
# figextract.sh (-> figures/<name>_S*.png + <name>.figures.json).
#
#   ./tools/prep.sh quellen/SWT/            # ganzen Themenordner aufbereiten
#   ./tools/prep.sh quellen/SWT/04_UML.pdf  # einzelne Datei
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== 1/2 Text-Extrakt + Abbildungs-Index =="
"$DIR/extract.sh" "$@"
echo "== 2/2 Abbildungen schneiden =="
"$DIR/figextract.sh" "$@"
echo "Fertig. Lesen: aufbereitet/<Thema>/<name>.md  (Bilder: <name>.figures.md / figures/)"
