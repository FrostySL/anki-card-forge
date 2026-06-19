#!/usr/bin/env python3
"""Baut aus einer Karten-JSON-Datei ein Anki-.apkg-Paket.

Aufruf:
    python build_deck.py <cards.json> [output.apkg]

Wird i. d. R. ueber tools/build.sh im Docker-Container aufgerufen, z. B.:
    ./tools/build.sh decks/skript.cards.json

Karten-Typen: "basic", "cloze", "occlusion" (Bild mit verdeckten Bereichen).
JSON-Format siehe CLAUDE.md.
"""
import hashlib
import html
import json
import os
import sys

import genanki


def stable_id(text: str) -> int:
    """Deterministische ID im von Anki erwarteten 32-bit-Bereich (1 .. 2^31-1).

    Gleicher Name -> gleiche ID, damit erneutes Bauen das Deck/Model
    aktualisiert statt zu duplizieren.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1) + 1


_CSS = """
.card {
  font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  font-size: 20px;
  line-height: 1.5;
  text-align: left;
  color: #222;
  background: #fff;
  max-width: 700px;
  margin: 0 auto;
  padding: 1em;
}
hr#answer { margin: 1em 0; border: none; border-top: 1px solid #ccc; }
.cloze { font-weight: bold; color: #2962ff; }
ul, ol { text-align: left; display: inline-block; }

/* --- Image Occlusion (Bild mit verdeckten Bereichen) --- */
.io-head { text-align: center; font-weight: bold; margin-bottom: .5em; }
.io-extra { margin-top: .75em; }
.io-wrap { position: relative; display: inline-block; max-width: 100%; }
.io-wrap img { max-width: 100%; display: block; }
.io-mask {
  position: absolute; box-sizing: border-box;
  background: #ffd54f; border: 1px solid #c8a415;
}
.io-answer {
  position: absolute; box-sizing: border-box;
  border: 2px solid #e53935; background: rgba(229,57,53,.08);
}
.io-label {
  position: absolute; box-sizing: border-box; padding: 2px;
  display: flex; align-items: center; justify-content: center;
  color: #c62828; font-weight: bold; font-size: .8em; text-align: center;
  text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff;
}
"""

BASIC_MODEL = genanki.Model(
    stable_id("anki-karten:basic-model:v1"),
    "Anki-Karten Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Karte 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        }
    ],
    css=_CSS,
)

CLOZE_MODEL = genanki.Model(
    stable_id("anki-karten:cloze-model:v1"),
    "Anki-Karten Cloze",
    model_type=genanki.Model.CLOZE,
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}",
            "afmt": "{{cloze:Text}}<br>{{Extra}}",
        }
    ],
    css=_CSS,
)

# Eigenstaendige Image-Occlusion-Karte: Vorder-/Rueckseite sind bereits
# fertig gerendertes HTML (Bild + Overlay-Rechtecke). Unabhaengig von Ankis
# internem IO-Format -> laeuft in jeder Anki-Version.
OCCLUSION_MODEL = genanki.Model(
    stable_id("anki-karten:occlusion-model:v1"),
    "Anki-Karten Image Occlusion",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Occlusion",
            "qfmt": "{{Front}}",
            "afmt": "{{Back}}",
        }
    ],
    css=_CSS,
)


def _pct(value: float) -> str:
    return f"{float(value) * 100:.4f}%"


def _occlusion_html(img_src, regions, target, mode, reveal, header, extra):
    """Rendert eine Seite einer Occlusion-Karte.

    reveal=False -> Vorderseite (Frage), reveal=True -> Rueckseite (Antwort).
    mode: "hide-one" (nur Zielbereich verdeckt) oder
          "hide-all"  (alle verdeckt, nur Zielbereich wird aufgedeckt).
    """
    parts = []
    if header:
        parts.append(f'<div class="io-head">{html.escape(header)}</div>')
    parts.append('<div class="io-wrap">')
    parts.append(f'<img src="{html.escape(img_src, quote=True)}">')

    for i, r in enumerate(regions):
        pos = (
            f'left:{_pct(r["x"])};top:{_pct(r["y"])};'
            f'width:{_pct(r["w"])};height:{_pct(r["h"])}'
        )
        if not reveal:  # Vorderseite
            masked = True if mode == "hide-all" else (i == target)
        else:  # Rueckseite
            masked = (i != target) if mode == "hide-all" else False

        if masked:
            parts.append(f'<div class="io-mask" style="{pos}"></div>')
        elif reveal and i == target:
            parts.append(f'<div class="io-answer" style="{pos}"></div>')
            label = r.get("label", "")
            if label:
                parts.append(
                    f'<div class="io-label" style="{pos}">{html.escape(label)}</div>'
                )

    parts.append("</div>")
    if reveal and extra:
        parts.append(f'<div class="io-extra">{extra}</div>')
    return "".join(parts)


def _add_occlusion_notes(deck, card, media):
    """Erzeugt pro Bereich eine Karte und sammelt das Bild fuer das Paket."""
    image_path = card["image"]
    media.add(image_path)
    img_src = os.path.basename(image_path)
    regions = card["regions"]
    mode = card.get("mode", "hide-one")
    header = card.get("header", "")
    extra = card.get("extra", "")
    tags = card.get("tags", [])

    for target in range(len(regions)):
        front = _occlusion_html(img_src, regions, target, mode, False, header, extra)
        back = _occlusion_html(img_src, regions, target, mode, True, header, extra)
        # Stabile GUID je (Bild, Bereich), damit Re-Import aktualisiert statt dupliziert.
        guid = genanki.guid_for(img_src, mode, target, regions[target].get("label", ""))
        deck.add_note(
            genanki.Note(model=OCCLUSION_MODEL, fields=[front, back], tags=tags, guid=guid)
        )
    return len(regions)


def build(cards_path: str, out_path: str | None = None) -> str:
    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    deck_name = data["deck"]
    deck = genanki.Deck(stable_id("deck:" + deck_name), deck_name)
    media: set[str] = set()
    note_count = 0

    for i, card in enumerate(data["cards"]):
        ctype = card.get("type", "basic")
        tags = card.get("tags", [])
        if ctype == "cloze":
            deck.add_note(
                genanki.Note(
                    model=CLOZE_MODEL,
                    fields=[card["text"], card.get("extra", "")],
                    tags=tags,
                )
            )
            note_count += 1
        elif ctype == "basic":
            deck.add_note(
                genanki.Note(
                    model=BASIC_MODEL,
                    fields=[card["front"], card["back"]],
                    tags=tags,
                )
            )
            note_count += 1
        elif ctype == "occlusion":
            note_count += _add_occlusion_notes(deck, card, media)
        else:
            raise ValueError(
                f"Karte {i}: unbekannter type '{ctype}' (erlaubt: basic, cloze, occlusion)"
            )

    if out_path is None:
        base = os.path.basename(cards_path)
        for suffix in (".cards.json", ".json"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        out_path = os.path.join("decks", base + ".apkg")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    package = genanki.Package(deck)
    if media:
        missing = [p for p in media if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError("Bild(er) nicht gefunden: " + ", ".join(missing))
        package.media_files = sorted(media)

    package.write_to_file(out_path)
    print(f"OK: {note_count} Karten -> {out_path}  (Deck: {deck_name})")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
