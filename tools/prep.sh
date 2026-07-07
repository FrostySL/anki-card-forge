#!/usr/bin/env bash
# One-shot source preparation: PDF -> Markdown (+ figure index) AND figure crops.
# Bundles extract.sh (extract.py -> .md, then figindex.py -> .figures.md) and
# figextract.sh (-> figures/<name>_p*.png + <name>.figures.json).
#
#   ./tools/prep.sh sources/SWT/                        # prepare a whole topic folder
#   ./tools/prep.sh sources/SWT/04_UML.pdf              # single file
#   ./tools/prep.sh sources/Histoire/ --lang eng+fra    # OCR languages (extract step)
#   ./tools/prep.sh sources/SWT/ --zoom 2.5             # crop tuning (figextract step)
#
# The two steps have DISJOINT options, so prep.sh routes each to the right one
# (--lang/-j/--jobs -> extract.sh; --zoom/--min-area/--max-area/--min-side ->
# figextract.sh) instead of passing everything to both — which would crash
# whichever step does not know the option.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUTS=()
EXTRACT_ARGS=()
FIG_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --lang|-j|--jobs)
      [ $# -ge 2 ] || { echo "prep.sh: $1 needs a value" >&2; exit 1; }
      EXTRACT_ARGS+=("$1" "$2"); shift 2 ;;
    --lang=*|--jobs=*)
      EXTRACT_ARGS+=("$1"); shift ;;
    --zoom|--min-area|--max-area|--min-side)
      [ $# -ge 2 ] || { echo "prep.sh: $1 needs a value" >&2; exit 1; }
      FIG_ARGS+=("$1" "$2"); shift 2 ;;
    --zoom=*|--min-area=*|--max-area=*|--min-side=*)
      FIG_ARGS+=("$1"); shift ;;
    -*)
      echo "prep.sh: unknown option $1 (extract: --lang, -j/--jobs; figextract: --zoom, --min-area, --max-area, --min-side)" >&2
      exit 1 ;;
    *)
      INPUTS+=("$1"); shift ;;
  esac
done
if [ ${#INPUTS[@]} -eq 0 ]; then
  echo "Usage: tools/prep.sh <sources/<topic>/ | file.pdf> [--lang L] [-j N] [--zoom Z] [--min-area A] [--max-area A] [--min-side S]" >&2
  exit 1
fi

echo "== 1/2 Text extract + figure index =="
for input in "${INPUTS[@]}"; do
  "$DIR/extract.sh" "$input" ${EXTRACT_ARGS[@]+"${EXTRACT_ARGS[@]}"}
done
echo "== 2/2 Cropping figures =="
for input in "${INPUTS[@]}"; do
  "$DIR/figextract.sh" "$input" ${FIG_ARGS[@]+"${FIG_ARGS[@]}"}
done
echo "Done. Read: extracted/<topic>/<name>.md  (figures: <name>.figures.md / figures/)"
