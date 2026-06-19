#!/usr/bin/env python3
"""Baut aus einer oder mehreren Karten-JSON-Dateien ein Anki-.apkg-Paket.

Aufruf:
    python build_deck.py <cards.json> [weitere.cards.json ...] [output.apkg]

Mehrere Eingabedateien landen als je eigenes Deck in EINER .apkg (z. B. Text-
Karten + Abbildungs-Deck zusammen). Die Ausgabe ist das (einzige) *.apkg-Argument;
fehlt es, wird der Name aus der ersten Eingabe abgeleitet.

Wird i. d. R. ueber tools/build.sh im Docker-Container aufgerufen, z. B.:
    ./tools/build.sh decks/skript.cards.json
    ./tools/build.sh decks/text.cards.json decks/bilder.cards.json decks/komplett.apkg

Karten-Typen: "basic", "cloze", "occlusion" (Bild mit verdeckten Bereichen).
JSON-Format siehe CLAUDE.md.
"""
import hashlib
import html
import json
import os
import re
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
.io-answer-label {
  margin-top: .6em; text-align: center;
  color: #c62828; font-weight: bold; font-size: 1.05em;
}

/* --- Klappbox auf der Rueckseite: Vertiefung & Quelle (elaboratives Feedback) --- */
.more { margin-top: .9em; border-top: 1px solid #e0e0e0; padding-top: .4em; font-size: .92em; }
.more > summary { cursor: pointer; color: #1565c0; font-weight: bold; list-style: none; }
.more > summary::before { content: "▸ "; }
.more[open] > summary::before { content: "▾ "; }
.more-expl { margin: .5em 0; }
.more-src { color: #666; font-style: italic; }

/* type-in: Eingabevergleich von Anki */
.typed-bad { color: #c62828; }
.typed-good { color: #2e7d32; }
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
            "afmt": "{{cloze:Text}}{{#Extra}}<br>{{Extra}}{{/Extra}}",
        }
    ],
    css=_CSS,
)

# Eingabe pruefen: vorne tippt man die Antwort, Anki vergleicht ({{type:Back}}).
TYPEIN_MODEL = genanki.Model(
    stable_id("anki-karten:typein-model:v1"),
    "Anki-Karten Type-in",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "More"}],
    templates=[
        {
            "name": "Type-in",
            "qfmt": "{{Front}}<br><br>{{type:Back}}",
            "afmt": '{{Front}}<hr id="answer">{{type:Back}}{{More}}',
        }
    ],
    css=_CSS,
)

# Bidirektional: eine Notiz -> zwei Karten (Vor- und Rueckrichtung).
REVERSED_MODEL = genanki.Model(
    stable_id("anki-karten:reversed-model:v1"),
    "Anki-Karten Basic+Reversed",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "More"}],
    templates=[
        {
            "name": "Vorwaerts",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}{{More}}',
        },
        {
            "name": "Rueckwaerts",
            "qfmt": "{{Back}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Front}}{{More}}',
        },
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


# Etwas Luft um jede Box, damit Maske/Umrandung den (oft kleinen) Text nicht
# hauteng einklemmen -> deutlich besser erkenn- und lesbar.
_BOX_PAD = 0.01


def _box_style(r):
    x = max(0.0, r["x"] - _BOX_PAD)
    y = max(0.0, r["y"] - _BOX_PAD)
    w = min(1.0 - x, r["w"] + 2 * _BOX_PAD)
    h = min(1.0 - y, r["h"] + 2 * _BOX_PAD)
    return f"left:{_pct(x)};top:{_pct(y)};width:{_pct(w)};height:{_pct(h)}"


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
        pos = _box_style(r)
        if not reveal:  # Vorderseite
            masked = True if mode == "hide-all" else (i == target)
        else:  # Rueckseite
            masked = (i != target) if mode == "hide-all" else False

        if masked:
            parts.append(f'<div class="io-mask" style="{pos}"></div>')
        elif reveal and i == target:
            # Nur umranden – KEIN Text ueber dem Bild (sonst Ueberlagerung mit der
            # Beschriftung, die schon im Bild steht). Antwort kommt als Unterschrift.
            parts.append(f'<div class="io-answer" style="{pos}"></div>')

    parts.append("</div>")
    if reveal:
        answer = regions[target].get("label", "")
        if answer:
            parts.append(f'<div class="io-answer-label">{html.escape(answer)}</div>')
        if extra:
            parts.append(f'<div class="io-extra">{extra}</div>')
    return "".join(parts)


# --- Render-Helfer: erzeugen das fertige Vorder-/Rueckseiten-HTML einer Karte. ---
# Occlusion teilt sich dieses HTML 1:1 mit dem .apkg (Template ist nur {{Front}}/
# {{Back}}). Fuer basic/cloze speichert genanki dagegen ROHE Felder und wendet das
# Template selbst an; render_basic/render_cloze spiegeln dieses Template, damit die
# Vorschau (tools/preview.py) genauso aussieht wie die Anki-Karte. Aenderungen an den
# Model-Templates oben muessen hier mitgezogen werden.


def _more_html(card):
    """Zugeklappte 'Vertiefung & Quelle'-Box (oder '' wenn nichts vorhanden).

    Erscheint NUR auf der Rueckseite, standardmaessig zu -> elaboratives Feedback
    nach dem Abruf, ohne die Frage zu erleichtern. 'explanation' darf HTML enthalten,
    'source' wird als Text escaped.
    """
    expl = (card.get("explanation") or "").strip()
    src = (card.get("source") or "").strip()
    if not expl and not src:
        return ""
    parts = []
    if expl:
        parts.append(f'<div class="more-expl">{expl}</div>')
    if src:
        parts.append(f'<div class="more-src">Quelle: {html.escape(src)}</div>')
    if expl and src:
        label = "Vertiefung &amp; Quelle"
    elif expl:
        label = "Vertiefung"
    else:
        label = "Quelle"
    return f'<details class="more"><summary>{label}</summary>{"".join(parts)}</details>'


def render_basic(card):
    """(front, back) — spiegelt das afmt von BASIC_MODEL (+ Klappbox)."""
    front = card["front"]
    back = f'{front}<hr id="answer">{card["back"]}{_more_html(card)}'
    return front, back


def render_reversed(card):
    """Liste [(front, back), ...] fuer beide Richtungen (REVERSED_MODEL)."""
    f, b, more = card["front"], card["back"], _more_html(card)
    return [
        (f, f'{f}<hr id="answer">{b}{more}'),
        (b, f'{b}<hr id="answer">{f}{more}'),
    ]


def render_typein(card):
    """(front, back) fuer TYPEIN_MODEL. In der Vorschau ist das Eingabefeld nur
    angedeutet (Ankis {{type:}}-Vergleich gibt es im Browser nicht)."""
    front = card["front"]
    front_preview = f'{front}<br><br><i style="color:#888">[Antwort eintippen]</i>'
    back = f'{front}<hr id="answer">{card["back"]}{_more_html(card)}'
    return front_preview, back


_CLOZE_RE = re.compile(r"\{\{c(\d+)::(.+?)\}\}", re.DOTALL)


def _cloze_numbers(text):
    return sorted({int(m.group(1)) for m in _CLOZE_RE.finditer(text)})


def _render_cloze_side(text, active, reveal):
    def repl(m):
        num = int(m.group(1))
        content = m.group(2)
        answer, hint = (content.split("::", 1) + [""])[:2]
        if num == active:
            if reveal:
                return f'<span class="cloze">{answer}</span>'
            return f'<span class="cloze">[{hint or "..."}]</span>'
        return answer  # nicht-aktive Cloze: Inhalt normal zeigen

    return _CLOZE_RE.sub(repl, text)


def render_cloze(card):
    """Liste von (front, back) — eine pro cN, spiegelt Ankis Cloze-Verhalten."""
    text = card["text"]
    tail = card.get("extra", "") + _more_html(card)  # entspricht dem Extra-Feld
    out = []
    for num in _cloze_numbers(text):
        front = _render_cloze_side(text, num, reveal=False)
        back = _render_cloze_side(text, num, reveal=True)
        if tail:
            back = f"{back}<br>{tail}"
        out.append((front, back))
    return out


def render_occlusion(card, img_src):
    """Liste von (front, back) — eine pro Bereich. img_src = Bildquelle (Dateiname
    fuers .apkg oder data:-URI fuer die self-contained Vorschau)."""
    regions = card["regions"]
    mode = card.get("mode", "hide-one")
    header = card.get("header", "")
    extra = card.get("extra", "")
    more = _more_html(card)
    out = []
    for target in range(len(regions)):
        front = _occlusion_html(img_src, regions, target, mode, False, header, extra)
        back = _occlusion_html(img_src, regions, target, mode, True, header, extra) + more
        out.append((front, back))
    return out


def _add_occlusion_notes(deck, card, media):
    """Erzeugt pro Bereich eine Karte und sammelt das Bild fuer das Paket."""
    image_path = card["image"]
    media.add(image_path)
    img_src = os.path.basename(image_path)
    mode = card.get("mode", "hide-one")
    tags = card.get("tags", [])
    regions = card["regions"]

    for target, (front, back) in enumerate(render_occlusion(card, img_src)):
        # Stabile GUID je (Bild, Bereich), damit Re-Import aktualisiert statt dupliziert.
        guid = genanki.guid_for(img_src, mode, target, regions[target].get("label", ""))
        deck.add_note(
            genanki.Note(model=OCCLUSION_MODEL, fields=[front, back], tags=tags, guid=guid)
        )
    return len(regions)


def _deck_from_data(data, media):
    """Baut aus einer geparsten cards.json ein genanki.Deck (+ zaehlt Notizen)."""
    deck_name = data["deck"]
    deck = genanki.Deck(stable_id("deck:" + deck_name), deck_name)
    note_count = 0
    for i, card in enumerate(data["cards"]):
        ctype = card.get("type", "basic")
        tags = card.get("tags", [])
        more = _more_html(card)
        if ctype == "cloze":
            # Klappbox haengt am Extra-Feld (afmt zeigt es nach der Luecke).
            deck.add_note(
                genanki.Note(model=CLOZE_MODEL, fields=[card["text"], card.get("extra", "") + more], tags=tags)
            )
            note_count += 1
        elif ctype == "basic":
            if card.get("reverse"):
                deck.add_note(
                    genanki.Note(model=REVERSED_MODEL, fields=[card["front"], card["back"], more], tags=tags)
                )
            else:
                # Klappbox haengt hinten am Back-Feld (Model unveraendert -> kompatibel).
                deck.add_note(
                    genanki.Note(model=BASIC_MODEL, fields=[card["front"], card["back"] + more], tags=tags)
                )
            note_count += 1
        elif ctype == "typein":
            deck.add_note(
                genanki.Note(model=TYPEIN_MODEL, fields=[card["front"], card["back"], more], tags=tags)
            )
            note_count += 1
        elif ctype == "occlusion":
            note_count += _add_occlusion_notes(deck, card, media)
        else:
            raise ValueError(
                f"{deck_name}, Karte {i}: unbekannter type '{ctype}' "
                "(erlaubt: basic, cloze, typein, occlusion)"
            )
    return deck, deck_name, note_count


def _default_out(first_input):
    base = os.path.basename(first_input)
    for suffix in (".cards.json", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return os.path.join("decks", base + ".apkg")


def build(inputs, out_path: str | None = None) -> str:
    """Baut aus einer ODER MEHREREN cards.json EINE .apkg.

    Jede Datei wird zu einem eigenen Deck; '::' im Decknamen erzeugt Unterdecks.
    So lassen sich z. B. Text-Karten und ein Abbildungs-Deck in einer Datei
    zusammenfassen.
    """
    if isinstance(inputs, str):
        inputs = [inputs]

    media: set[str] = set()
    decks = []
    total = 0
    for cards_path in inputs:
        with open(cards_path, encoding="utf-8") as f:
            data = json.load(f)
        deck, deck_name, count = _deck_from_data(data, media)
        decks.append((deck, deck_name, count))
        total += count

    if out_path is None:
        out_path = _default_out(inputs[0])
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    package = genanki.Package([d for d, _, _ in decks])
    if media:
        missing = [p for p in media if not os.path.exists(p)]
        if missing:
            raise FileNotFoundError("Bild(er) nicht gefunden: " + ", ".join(missing))
        package.media_files = sorted(media)

    package.write_to_file(out_path)
    if len(decks) == 1:
        print(f"OK: {total} Karten -> {out_path}  (Deck: {decks[0][1]})")
    else:
        print(f"OK: {total} Karten in {len(decks)} Decks -> {out_path}")
        for _, name, count in decks:
            print(f"     - {name}: {count}")
    return out_path


if __name__ == "__main__":
    # Positionsargumente: beliebig viele *.json (Eingaben) + optional ein *.apkg (Ausgabe)
    args = sys.argv[1:]
    inputs = [a for a in args if a.endswith(".json")]
    outs = [a for a in args if a.endswith(".apkg")]
    if not inputs or len(outs) > 1:
        print(__doc__)
        sys.exit(1)
    build(inputs, outs[0] if outs else None)
