#!/usr/bin/env python3
"""Rendert die Karten einer cards.json als PNG-Bilder (Vorder- + Rueckseite).

Aufruf (i. d. R. ueber tools/preview.sh im Vorschau-Container):
    python preview.py <cards.json>

Erzeugt:  decks/preview/<name>/NN-<typ>-front.png  und  -back.png
          decks/preview/<name>/index.html  (Kontaktbogen zum Durchschauen)

Zweck: Feedbackloop. Claude (oder du) sieht sich die PNGs an und korrigiert z. B.
verrutschte Image-Occlusion-Boxen, bevor die .apkg final gebaut wird. Es wird das
gleiche HTML/CSS wie im .apkg verwendet (aus build_deck.py), daher sieht die Vorschau
praktisch wie die echte Anki-Karte aus.
"""
import base64
import html
import json
import mimetypes
import os
import re
import sys

import build_deck  # gleiche tools/-Verzeichnis -> sys.path[0]
from playwright.sync_api import sync_playwright

_DOC = (
    '<!doctype html><html><head><meta charset="utf-8"><style>{css}\n'
    "html,body{{margin:0;padding:0;background:#fff;}}</style></head>"
    '<body><div class="card">{body}</div></body></html>'
)


def _data_uri(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Bild nicht gefunden: {path}")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _short(text, n=60):
    plain = re.sub(r"<[^>]+>", "", text or "").strip()
    plain = re.sub(r"\s+", " ", plain)
    return (plain[:n] + "…") if len(plain) > n else plain


def _collect(data):
    """-> Liste von (ctype, label, front_html, back_html)."""
    items = []
    for card in data["cards"]:
        ctype = card.get("type", "basic")
        if ctype == "basic":
            front, back = build_deck.render_basic(card)
            items.append((ctype, _short(card.get("front", "")), front, back))
        elif ctype == "cloze":
            for n, (front, back) in enumerate(build_deck.render_cloze(card), 1):
                items.append((ctype, f"c{n}: {_short(card.get('text',''), 40)}", front, back))
        elif ctype == "occlusion":
            uri = _data_uri(card["image"])
            regions = card["regions"]
            for n, (front, back) in enumerate(build_deck.render_occlusion(card, uri)):
                items.append((ctype, regions[n].get("label", f"#{n + 1}"), front, back))
        else:
            raise ValueError(f"Unbekannter type '{ctype}' (basic, cloze, occlusion)")
    return items


def _write_index(outdir, rows):
    cells = []
    for i, ctype, label in rows:
        cells.append(
            f'<div class="row"><h3>{i:02d} · {ctype} · {html.escape(label)}</h3>'
            f'<div class="pair">'
            f'<figure><figcaption>Vorderseite</figcaption>'
            f'<img src="{i:02d}-{ctype}-front.png"></figure>'
            f'<figure><figcaption>Rückseite</figcaption>'
            f'<img src="{i:02d}-{ctype}-back.png"></figure>'
            f"</div></div>"
        )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Karten-Vorschau</title>"
        "<style>body{font-family:sans-serif;margin:2em;background:#f5f5f5;}"
        ".row{background:#fff;border-radius:8px;padding:1em;margin-bottom:1.5em;"
        "box-shadow:0 1px 4px rgba(0,0,0,.1);}"
        ".pair{display:flex;gap:1em;flex-wrap:wrap;}"
        "figure{margin:0;}figcaption{font-size:.8em;color:#666;margin-bottom:.3em;}"
        "img{max-width:420px;border:1px solid #ddd;}h3{color:#333;}</style></head>"
        f"<body><h1>Karten-Vorschau</h1>{''.join(cells)}</body></html>"
    )
    with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(doc)


def preview(cards_path):
    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    base = os.path.basename(cards_path)
    for suffix in (".cards.json", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    outdir = os.path.join("decks", "preview", base)
    os.makedirs(outdir, exist_ok=True)

    items = _collect(data)
    rows = []
    with sync_playwright() as p:
        # --no-sandbox: noetig fuer headless Chromium als Nicht-Root im Container
        # (wir rendern nur eigenes, vertrauenswuerdiges HTML).
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=2)
        for i, (ctype, label, front, back) in enumerate(items, 1):
            for side, body in (("front", front), ("back", back)):
                page.set_content(_DOC.format(css=build_deck._CSS, body=body))
                fname = f"{i:02d}-{ctype}-{side}.png"
                page.locator(".card").screenshot(path=os.path.join(outdir, fname))
            rows.append((i, ctype, label))
        browser.close()

    _write_index(outdir, rows)
    print(f"OK: {len(items)} Karten -> {outdir}/  ({len(items) * 2} PNGs + index.html)")
    return outdir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    preview(sys.argv[1])
