#!/usr/bin/env python3
"""Schnelle Inhalts-/Struktur-Pruefung einer cards.json (reines Python, keine Deps).

    python3 tools/lint_cards.py decks/skript.cards.json

Meldet FEHLER (blockierend, Exit-Code 1) und WARNUNGEN (Hinweise). Ergaenzt den
visuellen Vorschau-Loop um eine schnelle Pruefung des Inhalts.
"""
import json
import os
import re
import sys

_CLOZE_RE = re.compile(r"\{\{c(\d+)::.+?\}\}", re.DOTALL)
_LONG_ANSWER = 350  # Zeichen: darueber Warnung "Antwort evtl. zu umfangreich"

# Erlaubte Felder – unbekannte Keys (Tippfehler wie "explaination") werden beim Build
# stillschweigend ignoriert, der Inhalt waere weg. Deshalb hier warnen.
_DECK_KEYS = {"deck", "cards"}
_COMMON_KEYS = {"type", "tags", "guid", "explanation", "source"}
_TYPE_KEYS = {
    "basic": {"front", "back", "reverse"},
    "typein": {"front", "back"},
    "cloze": {"text", "extra"},
    "occlusion": {"image", "mode", "header", "extra", "regions"},
}
_REGION_KEYS = {"label", "x", "y", "w", "h"}


def lint(cards_path):
    errors, warnings = [], []

    def err(i, msg):
        errors.append(f"  [FEHLER] Karte {i}: {msg}")

    def warn(i, msg):
        warnings.append(f"  [warn]  Karte {i}: {msg}")

    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("deck"):
        errors.append("  [FEHLER] 'deck' fehlt oder ist leer.")
    cards = data.get("cards") or []
    if not cards:
        errors.append("  [FEHLER] keine 'cards' vorhanden.")
    for key in sorted(set(data) - _DECK_KEYS):
        warnings.append(f"  [warn]  unbekanntes Feld {key!r} auf Deck-Ebene – wird ignoriert.")

    seen_fronts = {}
    for i, card in enumerate(cards):
        ctype = card.get("type", "basic")
        if ctype in ("basic", "typein"):
            front = (card.get("front") or "").strip()
            back = (card.get("back") or "").strip()
            if not front:
                err(i, f"{ctype} ohne 'front'.")
            if not back:
                err(i, f"{ctype} ohne 'back'.")
            if front:
                seen_fronts.setdefault(front, []).append(i)
            if len(back) > _LONG_ANSWER:
                warn(i, f"Antwort sehr lang ({len(back)} Zeichen) – evtl. aufteilen.")
        elif ctype == "cloze":
            text = (card.get("text") or "").strip()
            if not text:
                err(i, "cloze ohne 'text'.")
            elif not _CLOZE_RE.search(text):
                err(i, "cloze 'text' enthaelt keine Luecke {{c1::...}}.")
        elif ctype == "occlusion":
            img = card.get("image")
            if not img:
                err(i, "occlusion ohne 'image'.")
            elif not os.path.exists(img):
                err(i, f"Bild nicht gefunden: {img}")
            regions = card.get("regions") or []
            if not regions:
                err(i, "occlusion ohne 'regions'.")
            for n, r in enumerate(regions):
                for key in ("x", "y", "w", "h"):
                    v = r.get(key)
                    if not isinstance(v, (int, float)):
                        err(i, f"Bereich {n}: '{key}' fehlt oder ist keine Zahl.")
                    elif not (0 <= v <= 1):
                        warn(i, f"Bereich {n}: '{key}'={v} ausserhalb 0..1 (Bruchteil!).")
                x, y = r.get("x", 0), r.get("y", 0)
                w, h = r.get("w", 0), r.get("h", 0)
                if isinstance(x, (int, float)) and isinstance(w, (int, float)) and x + w > 1.001:
                    warn(i, f"Bereich {n}: x+w={x + w:.3f} > 1 – ragt rechts raus.")
                if isinstance(y, (int, float)) and isinstance(h, (int, float)) and y + h > 1.001:
                    warn(i, f"Bereich {n}: y+h={y + h:.3f} > 1 – ragt unten raus.")
                if not (r.get("label") or "").strip():
                    warn(i, f"Bereich {n}: kein 'label' (Antwort bleibt leer).")
                for key in sorted(set(r) - _REGION_KEYS):
                    warn(i, f"Bereich {n}: unbekanntes Feld '{key}' – wird ignoriert.")
            mode = card.get("mode", "hide-one")
            if mode not in ("hide-one", "hide-all"):
                err(i, f"unbekannter mode '{mode}' (hide-one | hide-all).")
        else:
            err(i, f"unbekannter type '{ctype}' (basic | cloze | typein | occlusion).")

        if ctype in _TYPE_KEYS:
            for key in sorted(set(card) - _COMMON_KEYS - _TYPE_KEYS[ctype]):
                if key == "reverse":
                    warn(i, f"'reverse' wirkt nur bei type 'basic' (hier '{ctype}') – wird ignoriert.")
                else:
                    warn(i, f"unbekanntes Feld '{key}' – wird beim Build ignoriert (Tippfehler?).")

    for front, idxs in seen_fronts.items():
        if len(idxs) > 1:
            warnings.append(f"  [warn]  doppelte Frage in Karten {idxs}: {front[:60]!r}")

    print(f"== Lint: {cards_path} ({len(cards)} Karten) ==")
    for line in errors:
        print(line)
    for line in warnings:
        print(line)
    if not errors and not warnings:
        print("  alles ok ✓")
    print(f"-> {len(errors)} Fehler, {len(warnings)} Warnungen")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(lint(sys.argv[1]))
