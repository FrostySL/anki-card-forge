#!/usr/bin/env python3
"""Builds an Anki .apkg package from one or more card JSON files.

Usage:
    python build_deck.py <cards.json> [more.cards.json ...] [output.apkg]

Multiple input files end up as separate decks inside ONE .apkg (e.g. text cards
plus a figures deck together). The output is the (single) *.apkg argument; if
omitted, the name is derived from the first input.

Usually invoked via tools/build.sh inside the Docker container, e.g.:
    ./tools/build.sh decks/script.cards.json
    ./tools/build.sh decks/text.cards.json decks/images.cards.json decks/full.apkg

Card types: "basic", "cloze", "typein", "occlusion" (image with hidden regions).
JSON format: see CLAUDE.md.
"""
import hashlib
import html
import json
import os
import re
import sys

import genanki


def stable_id(text: str) -> int:
    """Deterministic ID in the 32-bit range Anki expects (1 .. 2^31-1).

    Same name -> same ID, so rebuilding updates the deck/model instead of
    duplicating it.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1) + 1


_CSS = """
.card {
  /* Deliberately NO fixed color/background: Anki colors text+background per
     theme itself (dark in night mode, light otherwise). We only set theme-neutral
     accents -> translucent grays plus a blue that is readable on light AND dark.
     That way night mode just works, without relying on a .nightMode class. */
  --muted: #8a8a8a;
  --line: rgba(128, 128, 128, .5);
  --link: #4c8dff;
  --th: rgba(128, 128, 128, .18);
  --box: rgba(128, 128, 128, .16);
  font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  font-size: 20px;
  line-height: 1.5;
  text-align: left;
  max-width: 700px;
  margin: 0 auto;
  padding: 1em;
}
hr#answer { margin: 1em 0; border: none; border-top: 1px solid var(--line); }
.cloze { font-weight: bold; color: var(--link); }
ul, ol { text-align: left; display: inline-block; }

/* Tables for structuring card content (mappings, comparisons) */
table { border-collapse: collapse; margin: .5em auto; }
th, td { border: 1px solid var(--line); padding: .3em .6em; text-align: left; vertical-align: top; }
th { background: var(--th); }

/* --- Image occlusion (image with hidden regions) --- */
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

/* --- Collapsed box on the back: deep dive & source (elaborative feedback) --- */
.more { margin-top: .9em; border-top: 1px solid var(--line); padding-top: .4em; font-size: .92em; }
.more > summary { cursor: pointer; color: var(--link); font-weight: bold; list-style: none; }
.more > summary::before { content: "▸ "; }
.more[open] > summary::before { content: "▾ "; }
.more-expl { margin: .5em 0; }
.more-src { color: var(--muted); font-style: italic; }

/* type-in: Anki's answer comparison */
.typed-bad { color: #c62828; }
.typed-good { color: #2e7d32; }

/* --- Code & keys (source code, syntax, shortcuts) --- */
code, kbd, pre, samp { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
:not(pre) > code { background: var(--box); padding: .08em .35em; border-radius: 3px; font-size: .9em; }
pre { background: var(--box); padding: .7em .9em; border-radius: 6px; overflow-x: auto; text-align: left; margin: .6em 0; }
pre code { background: none; padding: 0; font-size: .92em; line-height: 1.4; }
kbd { background: var(--box); border: 1px solid var(--line); border-bottom-width: 2px;
      border-radius: 4px; padding: .05em .4em; font-size: .85em; white-space: nowrap; }

/* --- Learning callouts: ONLY on the back/explanation, never on the question
   (hint leak). rgba backgrounds look good in light AND night mode.
   The German class names (merke/achtung/beispiel/eselsbruecke/kontrast) are
   legacy aliases kept for existing decks — use the English names. --- */
.note, .pitfall, .example, .mnemonic,
.merke, .achtung, .beispiel, .eselsbruecke {
  text-align: left; margin: .6em 0; padding: .5em .7em .5em 2.1em;
  border-radius: 6px; border-left: 4px solid; position: relative;
}
.note, .merke               { background: rgba( 67,160, 71,.14); border-color: #43a047; }
.pitfall, .achtung          { background: rgba(251,140,  0,.14); border-color: #fb8c00; }
.example, .beispiel         { background: rgba( 30,136,229,.14); border-color: #1e88e5; }
.mnemonic, .eselsbruecke    { background: rgba(142, 36,170,.16); border-color: #8e24aa; }
.note::before, .pitfall::before, .example::before, .mnemonic::before,
.merke::before, .achtung::before, .beispiel::before, .eselsbruecke::before {
  position: absolute; left: .55em; top: .5em; font-weight: bold;
}
.note::before, .merke::before             { content: "\2605"; color: #43a047; }  /* ★ */
.pitfall::before, .achtung::before        { content: "\26A0"; color: #fb8c00; }  /* ⚠ */
.example::before, .beispiel::before       { content: "\276F"; color: #1e88e5; }  /* ❯ */
.mnemonic::before, .eselsbruecke::before  { content: "\1F9E0"; }                 /* 🧠 */
/* Contrast marker: on sister cards, highlight the DISTINGUISHING feature */
.contrast, .kontrast { background: rgba(255,193,7,.4); border-radius: 3px; padding: 0 .2em; font-weight: bold; }

/* --- Retrieval helpers --- */
/* Graded hint (ok on the FRONT too): minimal cue, collapsed -> retrieval stays intact. */
.hint { margin: .5em 0; font-size: .92em; }
.hint > summary { cursor: pointer; color: var(--link); font-weight: bold; list-style: none; }
.hint > summary::before { content: "\1F4A1 "; }  /* 💡 */
/* Process/flow chain: <div class="flow"><span class="step">A</span>
   <span class="arrow">\2192</span><span class="step">B</span></div> */
.flow { display: flex; flex-wrap: wrap; gap: .3em; align-items: center;
        justify-content: center; text-align: center; margin: .6em 0; }
.flow .step { background: var(--box); border: 1px solid var(--line);
              border-radius: 6px; padding: .2em .55em; }
.flow .arrow { color: var(--muted); padding: 0 .1em; }
"""

# NOTE: The stable_id seeds and the note type display names ("Anki-Karten ...")
# are deliberately kept unchanged: they determine the model IDs/names inside
# users' existing Anki collections. Renaming them would make re-imports create
# duplicate note types and disconnect already learned decks.

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

# Typed answers: you type the answer on the front, Anki compares ({{type:Back}}).
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

# Bidirectional: one note -> two cards (forward and reverse direction).
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

# Self-contained image occlusion card: front/back are pre-rendered HTML
# (image + overlay rectangles). Independent of Anki's internal IO format
# -> works in every Anki version.
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


# A bit of air around each box so mask/outline don't squeeze the (often small)
# text skin-tight -> much easier to recognize and read.
_BOX_PAD = 0.01


def _box_style(r):
    x = max(0.0, r["x"] - _BOX_PAD)
    y = max(0.0, r["y"] - _BOX_PAD)
    w = min(1.0 - x, r["w"] + 2 * _BOX_PAD)
    h = min(1.0 - y, r["h"] + 2 * _BOX_PAD)
    return f"left:{_pct(x)};top:{_pct(y)};width:{_pct(w)};height:{_pct(h)}"


def _occlusion_html(img_src, regions, target, mode, reveal, header, extra):
    """Renders one side of an occlusion card.

    reveal=False -> front (question), reveal=True -> back (answer).
    mode: "hide-one" (only the target region is masked) or
          "hide-all"  (all masked, only the target gets revealed).
    """
    parts = []
    if header:
        parts.append(f'<div class="io-head">{html.escape(header)}</div>')
    parts.append('<div class="io-wrap">')
    parts.append(f'<img src="{html.escape(img_src, quote=True)}">')

    for i, r in enumerate(regions):
        pos = _box_style(r)
        if not reveal:  # front
            masked = True if mode == "hide-all" else (i == target)
        else:  # back
            masked = (i != target) if mode == "hide-all" else False

        if masked:
            parts.append(f'<div class="io-mask" style="{pos}"></div>')
        elif reveal and i == target:
            # Outline only – NO text over the image (it would overlap the label
            # already printed in the image). The answer goes below as a caption.
            parts.append(f'<div class="io-answer" style="{pos}"></div>')

    parts.append("</div>")
    if reveal:
        answer = regions[target].get("label", "")
        if answer:
            parts.append(f'<div class="io-answer-label">{html.escape(answer)}</div>')
        if extra:
            parts.append(f'<div class="io-extra">{extra}</div>')
    return "".join(parts)


# --- Render helpers: produce the final front/back HTML of a card. ---
# Occlusion shares this HTML 1:1 with the .apkg (its template is just {{Front}}/
# {{Back}}). For basic/cloze, genanki stores RAW fields and applies the template
# itself; render_basic/render_cloze mirror that template so the preview
# (tools/preview.py) looks exactly like the Anki card. Changes to the model
# templates above must be mirrored here.


def _more_html(card):
    """Collapsed 'deep dive & source' box (or '' if nothing to show).

    Appears ONLY on the back, collapsed by default -> elaborative feedback after
    retrieval without making the question easier. 'explanation' may contain HTML,
    'source' is escaped as text.
    """
    expl = (card.get("explanation") or "").strip()
    src = (card.get("source") or "").strip()
    if not expl and not src:
        return ""
    parts = []
    if expl:
        parts.append(f'<div class="more-expl">{expl}</div>')
    if src:
        parts.append(f'<div class="more-src">Source: {html.escape(src)}</div>')
    if expl and src:
        label = "Details &amp; source"
    elif expl:
        label = "Details"
    else:
        label = "Source"
    return f'<details class="more"><summary>{label}</summary>{"".join(parts)}</details>'


def render_basic(card):
    """(front, back) — mirrors the afmt of BASIC_MODEL (+ collapsed box)."""
    front = card["front"]
    back = f'{front}<hr id="answer">{card["back"]}{_more_html(card)}'
    return front, back


def render_reversed(card):
    """List [(front, back), ...] for both directions (REVERSED_MODEL)."""
    f, b, more = card["front"], card["back"], _more_html(card)
    return [
        (f, f'{f}<hr id="answer">{b}{more}'),
        (b, f'{b}<hr id="answer">{f}{more}'),
    ]


def render_typein(card):
    """(front, back) for TYPEIN_MODEL. The preview only hints at the input field
    (Anki's {{type:}} comparison does not exist in the browser)."""
    front = card["front"]
    front_preview = f'{front}<br><br><i style="color:#888">[type the answer]</i>'
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
        return answer  # inactive cloze: show content normally

    return _CLOZE_RE.sub(repl, text)


def render_cloze(card):
    """List of (front, back) — one per cN, mirrors Anki's cloze behavior."""
    text = card["text"]
    tail = card.get("extra", "") + _more_html(card)  # corresponds to the Extra field
    out = []
    for num in _cloze_numbers(text):
        front = _render_cloze_side(text, num, reveal=False)
        back = _render_cloze_side(text, num, reveal=True)
        if tail:
            back = f"{back}<br>{tail}"
        out.append((front, back))
    return out


def render_occlusion(card, img_src):
    """List of (front, back) — one per region. img_src = image source (file name
    for the .apkg or a data: URI for the self-contained preview)."""
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
    """Creates one card per region and collects the image for the package."""
    image_path = card["image"]
    media.add(image_path)
    img_src = os.path.basename(image_path)
    mode = card.get("mode", "hide-one")
    tags = card.get("tags", [])
    regions = card["regions"]

    for target, (front, back) in enumerate(render_occlusion(card, img_src)):
        # Stable GUID per (image, region) so re-imports update instead of duplicate.
        guid = genanki.guid_for(img_src, mode, target, regions[target].get("label", ""))
        deck.add_note(
            genanki.Note(model=OCCLUSION_MODEL, fields=[front, back], tags=tags, guid=guid)
        )
    return len(regions)


def _deck_from_data(data, media):
    """Builds a genanki.Deck from a parsed cards.json (+ counts notes)."""
    deck_name = data["deck"]
    deck = genanki.Deck(stable_id("deck:" + deck_name), deck_name)
    note_count = 0
    for i, card in enumerate(data["cards"]):
        ctype = card.get("type", "basic")
        tags = card.get("tags", [])
        more = _more_html(card)
        # Optional stable GUID: allows a rebuild that UPDATES a note already
        # learned in Anki (same GUID) instead of duplicating it -> the learning
        # progress survives. Without 'guid', genanki derives one from the fields
        # as usual.
        guid = card.get("guid") or None
        if ctype == "cloze":
            # The collapsed box rides on the Extra field (afmt shows it after the gap).
            deck.add_note(
                genanki.Note(model=CLOZE_MODEL, fields=[card["text"], card.get("extra", "") + more], tags=tags, guid=guid)
            )
            note_count += 1
        elif ctype == "basic":
            if card.get("reverse"):
                deck.add_note(
                    genanki.Note(model=REVERSED_MODEL, fields=[card["front"], card["back"], more], tags=tags, guid=guid)
                )
            else:
                # The collapsed box is appended to the Back field (model unchanged -> compatible).
                deck.add_note(
                    genanki.Note(model=BASIC_MODEL, fields=[card["front"], card["back"] + more], tags=tags, guid=guid)
                )
            note_count += 1
        elif ctype == "typein":
            deck.add_note(
                genanki.Note(model=TYPEIN_MODEL, fields=[card["front"], card["back"], more], tags=tags, guid=guid)
            )
            note_count += 1
        elif ctype == "occlusion":
            note_count += _add_occlusion_notes(deck, card, media)
        else:
            raise ValueError(
                f"{deck_name}, card {i}: unknown type '{ctype}' "
                "(allowed: basic, cloze, typein, occlusion)"
            )
    return deck, deck_name, note_count


def _default_out(first_input):
    base = os.path.basename(first_input)
    for suffix in (".cards.json", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    # Put the .apkg next to the cards.json (e.g. decks/Biology/x.cards.json -> decks/Biology/x.apkg)
    return os.path.join(os.path.dirname(first_input) or "decks", base + ".apkg")


def build(inputs, out_path: str | None = None) -> str:
    """Builds ONE .apkg from one OR SEVERAL cards.json files.

    Each file becomes its own deck; '::' in the deck name creates subdecks.
    This allows bundling e.g. text cards and a figures deck into one file.
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
            raise FileNotFoundError("Image(s) not found: " + ", ".join(missing))
        package.media_files = sorted(media)

    package.write_to_file(out_path)
    if len(decks) == 1:
        print(f"OK: {total} cards -> {out_path}  (deck: {decks[0][1]})")
    else:
        print(f"OK: {total} cards in {len(decks)} decks -> {out_path}")
        for _, name, count in decks:
            print(f"     - {name}: {count}")
    return out_path


if __name__ == "__main__":
    # Positional arguments: any number of *.json (inputs) + optionally one *.apkg (output)
    args = sys.argv[1:]
    inputs = [a for a in args if a.endswith(".json")]
    outs = [a for a in args if a.endswith(".apkg")]
    if not inputs or len(outs) > 1:
        print(__doc__)
        sys.exit(1)
    build(inputs, outs[0] if outs else None)
