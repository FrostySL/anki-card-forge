#!/usr/bin/env bash
# Karten fertigstellen: Inhalt linten + Grounding pruefen (Gates) -> bauen -> validieren.
#
#   ./tools/finish.sh decks/SWT/04_UML.cards.json [decks/SWT/04_UML.apkg]
#
# Lint bricht bei Strukturfehlern ab (Gate). Grounding ist ein Hinweis (blockiert nicht,
# da Paraphrasen Fehlalarme geben koennen) – Ausgabe trotzdem lesen. Bei Occlusion-Karten
# zusaetzlich ./tools/preview.sh laufen lassen und die PNGs ansehen.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CARDS="${1:?Aufruf: tools/finish.sh decks/<Thema>/<name>.cards.json [out.apkg]}"
shift
OUT="${1:-${CARDS%.cards.json}.apkg}"

echo "== 1/4 Lint (Struktur) =="
python3 "$DIR/lint_cards.py" "$CARDS"

echo "== 2/4 Grounding (Quelltext-Deckung) =="
python3 "$DIR/grounding_check.py" "$CARDS" || true

echo "== 3/4 Build (.apkg) =="
"$DIR/build.sh" "$CARDS" "$OUT"

echo "== 4/4 Validate (echte Anki-Engine) =="
"$DIR/validate.sh" "$OUT"

echo "Fertig: $OUT"
if grep -q '"occlusion"' "$CARDS"; then
  echo "Hinweis: Occlusion-Karten enthalten – visuell pruefen: ./tools/preview.sh $CARDS"
fi
