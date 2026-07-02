#!/usr/bin/env bash
# Karten fertigstellen: Inhalt linten + Grounding pruefen -> bauen -> validieren.
#
#   ./tools/finish.sh decks/SWT/04_UML.cards.json [decks/SWT/04_UML.apkg]
#   ./tools/finish.sh decks/EWP/*.cards.json decks/EWP/EWP-komplett.apkg   # Buendel
#
# Mehrere cards.json ergeben EINE .apkg (je Datei ein Deck, wie build.sh) — dann ist
# die Ziel-.apkg Pflicht und zusaetzlich laeuft coverage.py (Dubletten/Abdeckung ueber
# Dateigrenzen). Lint bricht bei Strukturfehlern ab (Gate). Grounding und Coverage sind
# Hinweise (blockieren nicht, da Paraphrasen Fehlalarme geben koennen) – Ausgabe trotzdem
# lesen. Bei Occlusion-Karten zusaetzlich ./tools/preview.sh laufen lassen, PNGs ansehen.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUTS=()
OUT=""
for arg in "$@"; do
  case "$arg" in
    *.apkg)
      [ -z "$OUT" ] || { echo "Nur EINE Ziel-.apkg erlaubt ('$OUT' und '$arg')." >&2; exit 1; }
      OUT="$arg" ;;
    *.json) INPUTS+=("$arg") ;;
    *) echo "Unbekanntes Argument: $arg (erwartet *.cards.json oder *.apkg)" >&2; exit 1 ;;
  esac
done
if [ ${#INPUTS[@]} -eq 0 ]; then
  echo "Aufruf: tools/finish.sh <name>.cards.json [weitere.cards.json ...] [out.apkg]" >&2
  exit 1
fi
if [ -z "$OUT" ]; then
  if [ ${#INPUTS[@]} -gt 1 ]; then
    echo "Mehrere Eingaben: bitte Ziel-.apkg angeben, z. B. decks/<Thema>/<Thema>-komplett.apkg" >&2
    exit 1
  fi
  OUT="${INPUTS[0]%.cards.json}.apkg"
fi

echo "== Lint (Struktur; Gate) =="
for f in "${INPUTS[@]}"; do
  python3 "$DIR/lint_cards.py" "$f"
done

echo "== Grounding (Quelltext-Deckung; Hinweis) =="
for f in "${INPUTS[@]}"; do
  python3 "$DIR/grounding_check.py" "$f" || true
done

if [ ${#INPUTS[@]} -gt 1 ]; then
  echo "== Coverage (Dubletten/Abdeckung ueber alle Eingaben; Hinweis) =="
  python3 "$DIR/coverage.py" "${INPUTS[@]}" || true
fi

echo "== Build (.apkg) =="
"$DIR/build.sh" "${INPUTS[@]}" "$OUT"

echo "== Validate (echte Anki-Engine) =="
"$DIR/validate.sh" "$OUT"

echo "Fertig: $OUT"
if grep -q '"occlusion"' "${INPUTS[@]}"; then
  echo "Hinweis: Occlusion-Karten enthalten – visuell pruefen: ./tools/preview.sh <cards.json>"
fi
