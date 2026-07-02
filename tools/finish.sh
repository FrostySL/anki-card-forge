#!/usr/bin/env bash
# Finish cards: lint the content + check grounding -> build -> validate.
#
#   ./tools/finish.sh decks/SWT/04_UML.cards.json [decks/SWT/04_UML.apkg]
#   ./tools/finish.sh decks/EWP/*.cards.json decks/EWP/EWP-complete.apkg   # bundle
#   ./tools/finish.sh decks/SWT/04_UML.cards.json --push [--sync]          # + into Anki
#
# Several cards.json produce ONE .apkg (one deck per file, like build.sh) — the
# target .apkg is then mandatory, and coverage.py runs additionally (duplicates/
# coverage across file boundaries). Lint aborts on structural errors (gate).
# Grounding and coverage are hints (non-blocking, since paraphrases can produce
# false alarms) — still read the output. For occlusion cards, also run
# ./tools/preview.sh and look at the PNGs.
#
# --push   imports the finished .apkg straight into a running Anki via the
#          AnkiConnect add-on (see tools/anki_connect.py; optional feature).
# --prune  with --push: also delete notes that were removed from the package
#          (GUID diff; only when the user asked to remove cards).
# --sync   additionally triggers AnkiWeb sync afterwards (requires --push).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUTS=()
OUT=""
PUSH=0
PRUNE=0
SYNC=0
for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    --prune) PRUNE=1 ;;
    --sync) SYNC=1 ;;
    *.apkg)
      [ -z "$OUT" ] || { echo "Only ONE target .apkg allowed ('$OUT' and '$arg')." >&2; exit 1; }
      OUT="$arg" ;;
    *.json) INPUTS+=("$arg") ;;
    *) echo "Unknown argument: $arg (expected *.cards.json, *.apkg, --push, --prune or --sync)" >&2; exit 1 ;;
  esac
done
if [ "$SYNC" -eq 1 ] && [ "$PUSH" -eq 0 ]; then
  echo "--sync requires --push (sync without importing makes no sense here)." >&2
  exit 1
fi
if [ "$PRUNE" -eq 1 ] && [ "$PUSH" -eq 0 ]; then
  echo "--prune requires --push." >&2
  exit 1
fi
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

if [ "$PUSH" -eq 1 ]; then
  echo "== Push into Anki (AnkiConnect) =="
  PUSH_ARGS=()
  [ "$PRUNE" -eq 1 ] && PUSH_ARGS+=(--prune)
  python3 "$DIR/anki_connect.py" push "${PUSH_ARGS[@]}" "$OUT"
  if [ "$SYNC" -eq 1 ]; then
    python3 "$DIR/anki_connect.py" sync
  fi
fi

echo "Done: $OUT"
if grep -q '"occlusion"' "${INPUTS[@]}"; then
  echo "Note: occlusion cards included – check visually: ./tools/preview.sh <cards.json>"
fi
