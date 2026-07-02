#!/usr/bin/env bash
# One-shot source preparation: PDF -> Markdown (+ figure index) AND figure crops.
# Bundles extract.sh (extract.py -> .md, then figindex.py -> .figures.md) and
# figextract.sh (-> figures/<name>_p*.png + <name>.figures.json).
#
#   ./tools/prep.sh sources/SWT/            # prepare a whole topic folder
#   ./tools/prep.sh sources/SWT/04_UML.pdf  # single file
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== 1/2 Text extract + figure index =="
"$DIR/extract.sh" "$@"
echo "== 2/2 Cropping figures =="
"$DIR/figextract.sh" "$@"
echo "Done. Read: extracted/<topic>/<name>.md  (figures: <name>.figures.md / figures/)"
