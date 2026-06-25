#!/usr/bin/env python3
"""Rendert die Karten einer cards.json als PNG-Bilder (Vorder- + Rueckseite).

Aufruf (i. d. R. ueber tools/preview.sh im Vorschau-Container):
    python preview.py <cards.json> [--theme light|dark|both]

Erzeugt je Theme:  decks/preview/<name>/NN-<typ>-front[-dark].png  und  -back[-dark].png
                   decks/preview/<name>/index.html  (Kontaktbogen zum Durchschauen)

Zweck: Feedbackloop. Claude (oder du) sieht sich die PNGs an und korrigiert z. B.
verrutschte Image-Occlusion-Boxen, bevor die .apkg final gebaut wird. Es wird das
gleiche HTML/CSS wie im .apkg verwendet (aus build_deck.py), daher sieht die Vorschau
praktisch wie die echte Anki-Karte aus.

**Themes:** Default ist `both` -> jede Karte wird hell UND im Anki-Nachtmodus
(dunkler Grund, helle Schrift) gerendert. So sehe ich genau, was der Nutzer in beiden
Themes sieht (Nachtmodus-Lesbarkeit, Kontrast). `--theme light` ist schneller.
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

# MathJax wie in Anki (\( \) inline, \[ \] display). Nur eingebunden, wenn die Karte
# wirklich Formeln enthaelt -> normale Karten brauchen kein Internet/CDN. Im .apkg
# bringt Anki MathJax selbst mit; das hier ist nur fuer die Vorschau-Parität.
_MATHJAX = (
    r"<script>window.MathJax={tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]']]}};</script>"
    '<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>'
)

_DOC = (
    '<!doctype html><html><head><meta charset="utf-8"><style>{css}\n'
    "html,body{{margin:0;padding:0;{frame}}}</style>{mathjax}</head>"
    '<body><div class="card">{body}</div></body></html>'
)

# Themes wie in Anki. "dark" setzt dunklen Grund + helle Schrift auf <body>; die
# .card erbt das (sie setzt selbst keine color/background) -> exakt wie Ankis
# Nachtmodus. So sehe ich beim Pruefen genau, was der Nutzer in beiden Themes sieht.
_THEMES = {
    "light": "background:#fff;",
    "dark": "background:#2b2b2b;color:#d7d7d7;",
}


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
        if ctype == "basic" and card.get("reverse"):
            fwd, rev = build_deck.render_reversed(card)
            items.append(("reversed", "→ " + _short(card.get("front", "")), *fwd))
            items.append(("reversed", "← " + _short(card.get("back", "")), *rev))
        elif ctype == "basic":
            front, back = build_deck.render_basic(card)
            items.append((ctype, _short(card.get("front", "")), front, back))
        elif ctype == "typein":
            front, back = build_deck.render_typein(card)
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
            raise ValueError(f"Unbekannter type '{ctype}' (basic, cloze, typein, occlusion)")
    return items


def _png_name(i, ctype, side, theme):
    suffix = "" if theme == "light" else f"-{theme}"
    return f"{i:02d}-{ctype}-{side}{suffix}.png"


def _write_index(outdir, rows, themes=("light",)):
    cap = {"front": "Vorderseite", "back": "Rückseite"}
    cells = []
    for i, ctype, label in rows:
        figs = ""
        for theme in themes:
            tlabel = "" if theme == "light" else f" · {theme}"
            for side in ("front", "back"):
                figs += (f'<figure><figcaption>{cap[side]}{tlabel}</figcaption>'
                         f'<img src="{_png_name(i, ctype, side, theme)}"></figure>')
        cells.append(
            f'<div class="row"><h3>{i:02d} · {ctype} · {html.escape(label)}</h3>'
            f'<div class="pair">{figs}</div></div>'
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


def preview(cards_path, themes=("light", "dark")):
    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    base = os.path.basename(cards_path)
    for suffix in (".cards.json", ".json"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    # Vorschau neben die cards.json (z. B. decks/Biologie/x.cards.json -> decks/Biologie/preview/x/)
    src_dir = os.path.dirname(cards_path) or "decks"
    outdir = os.path.join(src_dir, "preview", base)
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
                # Klappbox in der Vorschau aufgeklappt zeigen (im echten Deck bleibt sie zu).
                body = body.replace('<details class="more">', '<details class="more" open>')
                has_math = "\\(" in body or "\\[" in body
                mathjax = _MATHJAX if has_math else ""
                for theme in themes:
                    page.set_content(_DOC.format(
                        css=build_deck._CSS, body=body, mathjax=mathjax, frame=_THEMES[theme]))
                    if has_math:
                        # Best effort: auf MathJax warten und setzen. Offline -> Timeout,
                        # Formeln bleiben Rohtext (das .apkg rendert sie trotzdem).
                        try:
                            page.wait_for_function("window.MathJax && window.MathJax.typesetPromise", timeout=4000)
                            page.evaluate("() => window.MathJax.typesetPromise()")
                        except Exception:
                            pass
                    page.locator(".card").screenshot(path=os.path.join(outdir, _png_name(i, ctype, side, theme)))
            rows.append((i, ctype, label))
        browser.close()

    _write_index(outdir, rows, themes)
    n_png = len(items) * 2 * len(themes)
    print(f"OK: {len(items)} Karten · Themes: {'+'.join(themes)} -> {outdir}/  ({n_png} PNGs + index.html)")
    return outdir


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Karten einer cards.json als PNG rendern (hell/dunkel).")
    ap.add_argument("cards", help="Pfad zur cards.json")
    ap.add_argument("--theme", choices=["light", "dark", "both"], default="both",
                    help="Welche(s) Theme(s) rendern (Default: both = hell UND Anki-Nachtmodus).")
    args = ap.parse_args()
    themes = ("light", "dark") if args.theme == "both" else (args.theme,)
    preview(args.cards, themes)
