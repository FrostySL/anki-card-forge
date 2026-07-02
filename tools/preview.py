#!/usr/bin/env python3
"""Renders the cards of a cards.json as PNG images (front + back).

Usage (normally via tools/preview.sh inside the preview container):
    python preview.py <cards.json> [--theme light|dark|both]

Produces per theme:  decks/preview/<name>/NN-<type>-front[-dark].png  and  -back[-dark].png
                     decks/preview/<name>/index.html  (contact sheet for browsing)

Purpose: feedback loop. Claude (or you) looks at the PNGs and fixes e.g.
misplaced image-occlusion boxes before the final .apkg is built. The same
HTML/CSS as in the .apkg is used (from build_deck.py), so the preview looks
practically identical to the real Anki card.

**Themes:** default is `both` -> every card is rendered light AND in Anki's
night mode (dark background, light text). That shows exactly what the user sees
in both themes (night-mode readability, contrast). `--theme light` is faster.
"""
import base64
import html
import json
import mimetypes
import os
import re
import sys

import build_deck  # same tools/ directory -> sys.path[0]
from playwright.sync_api import sync_playwright

# MathJax like in Anki (\( \) inline, \[ \] display). Only included when the card
# actually contains formulas -> normal cards need no internet/CDN. In the .apkg,
# Anki ships MathJax itself; this is only for preview parity.
_MATHJAX = (
    r"<script>window.MathJax={tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]']]}};</script>"
    '<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>'
)

_DOC = (
    '<!doctype html><html><head><meta charset="utf-8"><style>{css}\n'
    "html,body{{margin:0;padding:0;{frame}}}</style>{mathjax}</head>"
    '<body><div class="card">{body}</div></body></html>'
)

# Themes like in Anki. "dark" sets a dark background + light text on <body>; the
# .card inherits it (it sets no color/background itself) -> exactly like Anki's
# night mode. So the check shows precisely what the user sees in both themes.
_THEMES = {
    "light": "background:#fff;",
    "dark": "background:#2b2b2b;color:#d7d7d7;",
}


def _data_uri(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _short(text, n=60):
    plain = re.sub(r"<[^>]+>", "", text or "").strip()
    plain = re.sub(r"\s+", " ", plain)
    return (plain[:n] + "…") if len(plain) > n else plain


def _collect(data):
    """-> list of (ctype, label, front_html, back_html)."""
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
            raise ValueError(f"Unknown type '{ctype}' (basic, cloze, typein, occlusion)")
    return items


def _png_name(i, ctype, side, theme):
    suffix = "" if theme == "light" else f"-{theme}"
    return f"{i:02d}-{ctype}-{side}{suffix}.png"


def _write_index(outdir, rows, themes=("light",)):
    cap = {"front": "Front", "back": "Back"}
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
        "<!doctype html><html><head><meta charset='utf-8'><title>Card preview</title>"
        "<style>body{font-family:sans-serif;margin:2em;background:#f5f5f5;}"
        ".row{background:#fff;border-radius:8px;padding:1em;margin-bottom:1.5em;"
        "box-shadow:0 1px 4px rgba(0,0,0,.1);}"
        ".pair{display:flex;gap:1em;flex-wrap:wrap;}"
        "figure{margin:0;}figcaption{font-size:.8em;color:#666;margin-bottom:.3em;}"
        "img{max-width:420px;border:1px solid #ddd;}h3{color:#333;}</style></head>"
        f"<body><h1>Card preview</h1>{''.join(cells)}</body></html>"
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
    # Preview next to the cards.json (e.g. decks/Biology/x.cards.json -> decks/Biology/preview/x/)
    src_dir = os.path.dirname(cards_path) or "decks"
    outdir = os.path.join(src_dir, "preview", base)
    os.makedirs(outdir, exist_ok=True)

    items = _collect(data)
    rows = []
    with sync_playwright() as p:
        # --no-sandbox: needed for headless Chromium as non-root in the container
        # (we only render our own, trusted HTML).
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=2)
        for i, (ctype, label, front, back) in enumerate(items, 1):
            for side, body in (("front", front), ("back", back)):
                # Show the collapsed box open in the preview (stays closed in the real deck).
                body = body.replace('<details class="more">', '<details class="more" open>')
                has_math = "\\(" in body or "\\[" in body
                mathjax = _MATHJAX if has_math else ""
                for theme in themes:
                    page.set_content(_DOC.format(
                        css=build_deck._CSS, body=body, mathjax=mathjax, frame=_THEMES[theme]))
                    if has_math:
                        # Best effort: wait for MathJax and typeset. Offline -> timeout,
                        # formulas stay raw text (the .apkg still renders them).
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
    print(f"OK: {len(items)} cards · themes: {'+'.join(themes)} -> {outdir}/  ({n_png} PNGs + index.html)")
    return outdir


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render the cards of a cards.json as PNGs (light/dark).")
    ap.add_argument("cards", help="path to the cards.json")
    ap.add_argument("--theme", choices=["light", "dark", "both"], default="both",
                    help="which theme(s) to render (default: both = light AND Anki night mode).")
    args = ap.parse_args()
    themes = ("light", "dark") if args.theme == "both" else (args.theme,)
    preview(args.cards, themes)
