#!/usr/bin/env bash
# Finish cards: lint the content + check grounding -> build -> validate.
#
#   ./tools/finish.sh decks/SWT/04_UML.cards.json [decks/SWT/04_UML.apkg]
#   ./tools/finish.sh decks/EWP/*.cards.json decks/EWP/EWP-complete.apkg   # bundle
#
# Several cards.json produce ONE .apkg (one deck per file, like build.sh) — the
# target .apkg is then mandatory, and coverage.py runs additionally (duplicates/
# coverage across file boundaries). Lint aborts on structural errors (gate).
# Grounding and coverage are hints (non-blocking, since paraphrases can produce
# false alarms) — still read the output. For occlusion cards, also run
# ./tools/preview.sh and look at the PNGs.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUTS=()
OUT=""
for arg in "$@"; do
  case "$arg" in
    *.apkg)
      [ -z "$OUT" ] || { echo "Only ONE target .apkg allowed ('$OUT' and '$arg')." >&2; exit 1; }
      OUT="$arg" ;;
    *.json) INPUTS+=("$arg") ;;
    *) echo "Unknown argument: $arg (expected *.cards.json or *.apkg)" >&2; exit 1 ;;
  esac
done
if [ ${#INPUTS[@]} -eq 0 ]; then
  echo "Usage: tools/finish.sh <name>.cards.json [more.cards.json ...] [out.apkg]" >&2
  exit 1
fi
if [ -z "$OUT" ]; then
  if [ ${#INPUTS[@]} -gt 1 ]; then
    echo "Several inputs: please name a target .apkg, e.g. decks/<topic>/<topic>-complete.apkg" >&2
    exit 1
  fi
  OUT="${INPUTS[0]%.cards.json}.apkg"
fi

echo "== Lint (structure; gate) =="
for f in "${INPUTS[@]}"; do
  python3 "$DIR/lint_cards.py" "$f"
done

echo "== Grounding (source-text coverage; hint) =="
for f in "${INPUTS[@]}"; do
  python3 "$DIR/grounding_check.py" "$f" || true
done

if [ ${#INPUTS[@]} -gt 1 ]; then
  echo "== Coverage (duplicates/coverage across all inputs; hint) =="
  python3 "$DIR/coverage.py" "${INPUTS[@]}" || true
fi

echo "== Build (.apkg) =="
"$DIR/build.sh" "${INPUTS[@]}" "$OUT"

echo "== Validate (real Anki engine) =="
"$DIR/validate.sh" "$OUT"

echo "Done: $OUT"
if grep -q '"occlusion"' "${INPUTS[@]}"; then
  echo "Note: occlusion cards included – check visually: ./tools/preview.sh <cards.json>"
fi
