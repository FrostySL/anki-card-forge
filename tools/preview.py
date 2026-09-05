#!/usr/bin/env python3
"""Renders the cards of a cards.json as PNG images (front + back).

Usage (normally via tools/preview.sh inside the preview container):
    python preview.py <cards.json> [--theme light|dark|both]

Produces per theme:  decks/preview/<name>/NN-<type>-front[-dark].png  and  -back[-dark].png
                     decks/preview/<name>/index.html  (contact sheet for browsing)

Purpose: feedback loop. Your AI assistant (or you) looks at the PNGs and fixes e.g.
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
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import build_deck  # same tools/ directory -> sys.path[0]
from playwright.sync_api import sync_playwright

MATHJAX_ORIGIN = "https://anki-card-forge.invalid/mathjax"
# The complete es5 tree is installed once. All component requests are fulfilled
# from local files, including extensions requested by TeX's \\require command.
_MATHJAX = (
    '<script>window.MathJax={loader:{paths:{mathjax:"' + MATHJAX_ORIGIN + '"}},'
    r"startup:{typeset:false},tex:{inlineMath:[['\\(','\\)']],displayMath:[['\\[','\\]']]}};</script>"
    '<script src="' + MATHJAX_ORIGIN + '/tex-svg.js"></script>'
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


def mathjax_directory():
    return Path(os.environ.get("ACF_MATHJAX_DIR", str(
        Path(__file__).resolve().parent.parent / ".forge/assets/mathjax-3.2.2/es5"))).resolve()


def configure_mathjax(page, directory=None, requests=None):
    """Route MathJax's synthetic origin to local files; return loading errors."""
    directory = Path(directory or mathjax_directory()).resolve()
    failures = []

    def serve(route):
        suffix = unquote(urlsplit(route.request.url).path).removeprefix("/mathjax/")
        try:
            path = (directory / suffix).resolve()
            path.relative_to(directory)
            if not path.is_file():
                raise FileNotFoundError(path)
            mime = "application/javascript" if path.suffix == ".js" else mimetypes.guess_type(path.name)[0]
            route.fulfill(path=str(path), content_type=mime or "application/octet-stream")
            if requests is not None:
                requests.append(suffix)
        except (OSError, ValueError) as exc:
            failures.append(f"MathJax component unavailable: {suffix}: {exc}")
            route.abort()

    page.route(MATHJAX_ORIGIN + "/**", serve)
    return failures


def render_math(page, failures):
    """Require SVG for detected math, preserving literal TeX in code/pre blocks."""
    if failures:
        raise RuntimeError("; ".join(failures))
    page.wait_for_function("window.MathJax && window.MathJax.typesetPromise", timeout=15000)
    page.evaluate("""async () => {
        await Promise.race([
            (async () => { await MathJax.startup.promise; await MathJax.typesetPromise(); })(),
            new Promise((_, reject) => setTimeout(() => reject(new Error('MathJax timed out')), 15000))
        ]);
    }""")
    if failures:
        raise RuntimeError("; ".join(failures))
    count = page.locator('mjx-container[jax="SVG"] svg').count()
    expected = page.evaluate("Array.from(MathJax.startup.document.math).length")
    if count < expected or page.locator('[data-mjx-error], mjx-merror, .mjx-merror').count():
        raise RuntimeError("MathJax did not render the formula correctly.")
    return count


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


def _inline_imgs(html_text):
    """Replaces local <img src="path"> with data URIs so the standalone
    preview HTML shows the same embedded images as the built .apkg."""
    return build_deck._IMG_SRC_RE.sub(
        lambda m: m.group(1) + _data_uri(m.group(3)) + m.group(4), html_text
    )


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
    return [(t, label, _inline_imgs(front), _inline_imgs(back)) for t, label, front, back in items]


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


def preview(cards_path, themes=("light", "dark"), offline=False):
    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    base = os.path.basename(cards_path)
    for suffix in (".cards.json", ".json"):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
            break
    # Preview next to the cards.json (e.g. decks/Biology/x.cards.json -> decks/Biology/preview/x/)
    src_dir = os.path.dirname(cards_path) or "decks"
    outdir = os.path.join(src_dir, "preview", base)
    os.makedirs(outdir, exist_ok=True)

    items = _collect(data)
    rows = []
    report = {"offline": offline, "math_renders": [], "mathjax_requests": []}
    with sync_playwright() as p:
        in_container = os.environ.get("ACF_PREVIEW_CONTAINER") == "1" or Path("/.dockerenv").exists()
        browser = p.chromium.launch(chromium_sandbox=not in_container)
        try:
            context = browser.new_context(viewport={"width": 800, "height": 600}, device_scale_factor=2)
            blocked = []
            if offline:
                def block_external(route):
                    blocked.append(route.request.url)
                    route.abort()
                context.route("**/*", block_external)
            page = context.new_page()
            failures = configure_mathjax(page, requests=report["mathjax_requests"])
            for i, (ctype, label, front, back) in enumerate(items, 1):
                for side, body in (("front", front), ("back", back)):
                    body = body.replace('<details class="more">', '<details class="more" open>')
                    has_math = "\\(" in body or "\\[" in body
                    if has_math and not (mathjax_directory() / "tex-svg.js").is_file():
                        raise RuntimeError("Local MathJax is missing. Run forge.cmd setup or rebuild the preview image.")
                    for theme in themes:
                        filename = _png_name(i, ctype, side, theme)
                        page.set_content(_DOC.format(
                            css=build_deck._CSS, body=body,
                            mathjax=_MATHJAX if has_math else "", frame=_THEMES[theme]))
                        if has_math:
                            report["math_renders"].append({
                                "filename": filename, "math_count": render_math(page, failures)})
                        if blocked:
                            raise RuntimeError("Offline preview needs external resources: " + ", ".join(blocked))
                        page.locator(".card").screenshot(path=os.path.join(outdir, filename))
                rows.append((i, ctype, label))
        finally:
            browser.close()

    _write_index(outdir, rows, themes)
    Path(outdir, "render-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    n_png = len(items) * 2 * len(themes)
    print(f"OK: {len(items)} cards · themes: {'+'.join(themes)} -> {outdir}/  ({n_png} PNGs + index.html)")
    return outdir


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render the cards of a cards.json as PNGs (light/dark).")
    ap.add_argument("cards", help="path to the cards.json")
    ap.add_argument("--theme", choices=["light", "dark", "both"], default="both",
                    help="which theme(s) to render (default: both = light AND Anki night mode).")
    ap.add_argument("--offline", action="store_true", help="fail if the preview needs external resources")
    args = ap.parse_args()
    themes = ("light", "dark") if args.theme == "both" else (args.theme,)
    preview(args.cards, themes, offline=args.offline)
