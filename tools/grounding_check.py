#!/usr/bin/env python3
"""Checks whether every card is backed by the source text (anti-hallucination).

    python3 tools/grounding_check.py decks/SWT/04_UML.cards.json
    python3 tools/grounding_check.py decks/SWT/04_UML.cards.json --source extracted/SWT/04_UML.md

Pure Python, no deps. For each card, the **content words of the answer**
(back / cloze deletions / occlusion labels) are checked against the extracted
source text: do they appear there? If `source` cites a page ("p. N" or "S. N"),
it additionally checks whether the answer is **on that page**. That way invented
facts and wrong page citations surface *before* the build.

Source: without --source, the sibling .md is used automatically
(decks/<topic>/<name>.cards.json -> extracted/<topic>/<name>.md); if missing, the
whole topic folder extracted/<topic>/ is used (then only the global check runs).

Heuristic — no substitute for thinking: low coverage means "please verify against
the source", not necessarily wrong (paraphrases/synonyms may fail to match).
"""
import argparse
import glob
import json
import os
import re
import sys

_CLOZE_RE = re.compile(r"\{\{c\d+::(.+?)(?:::.+?)?\}\}", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
# Page citations/markers: English "p. N" and legacy German "S. N" both accepted.
# \b so that e.g. "Kap. 8" (chapter) is not misread as a page citation.
_PAGE_CITE_RE = re.compile(r"\b(?:p|S)\.\s*(\d+)")
_MARKER_RE = re.compile(r"<!--\s*(?:p|S)\.\s*(\d+)[^>]*-->")
_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+")


def _norm(token):
    t = token.lower()
    return (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))


# Function words are everywhere and say nothing about coverage. German + English;
# other languages simply have no stopword filtering (slightly noisier, still works).
_STOP = set(_norm(w) for w in """
und oder aber denn weil dass wenn als wie also dann noch nur auch sehr mehr
der die das den dem des ein eine einen einem einer eines kein keine nach durch
ist sind war waren wird werden wurde wurden sein hat haben hatte habe dazu damit
fuer für mit ohne bei beim aus auf vom von zum zur zu im in an am um es er sie wir
ich du ihr man sich nicht so dies diese dieser dieses jede jeder jedes sowie bzw
ueber über sowohl sondern jedoch dabei somit etwa mehrere viele ihre seine deren
the and for with that this from are was were can will not all any one two each
which what when where who whom whose why how than then them they their there
""".split())


def _terms(text):
    """Content words (normalized): length>=4 and not a stopword, plus short
    acronyms (all-caps, e.g. UML, TDD, OOD)."""
    out = set()
    for w in _WORD_RE.findall(text or ""):
        if len(w) >= 2 and w.isupper() and w.isalpha():
            out.add(_norm(w))
        elif len(w) >= 4 and _norm(w) not in _STOP:
            out.add(_norm(w))
    return out


def _strip(text):
    return _TAG_RE.sub(" ", text or "")


def _answer_text(card):
    ctype = card.get("type", "basic")
    # _strip everywhere: HTML inside a cloze deletion ({{c1::<code>x</code>}})
    # or a label would otherwise turn tag names into "missing content words"
    # and produce false hallucination warnings.
    if ctype == "cloze":
        return _strip(" ".join(_CLOZE_RE.findall(card.get("text", ""))))
    if ctype == "occlusion":
        return _strip(" ".join((r.get("label") or "") for r in card.get("regions") or []))
    return _strip(card.get("back", ""))


def _sibling_md(cards_path):
    """The matching extracted/ .md for a cards.json — exact or by prefix (cards
    often named short '08_TST', the .md long '08_TST_Testing_TDD'). -> path or None."""
    exact = cards_path.replace("decks/", "extracted/", 1).replace(".cards.json", ".md")
    if os.path.isfile(exact):
        return exact
    theme = os.path.dirname(cards_path).replace("decks/", "extracted/", 1)
    stem = os.path.basename(cards_path)[:-len(".cards.json")]
    cands = [p for p in sorted(glob.glob(os.path.join(theme, "*.md")))
             if not p.endswith(".figures.md")]
    pref = [p for p in cands if os.path.basename(p)[:-3].startswith(stem)
            or stem.startswith(os.path.basename(p)[:-3])]
    return pref[0] if len(pref) == 1 else None


def _load_source(cards_path, override):
    """-> (whole_text_index, {page: index}, paths). Several sources: whole text only."""
    if override:
        # Filter .figures.md like the default branch does — otherwise a folder
        # with x.md + x.figures.md counts as "several sources" and the
        # page-accurate citation check silently switches off.
        paths = [override] if os.path.isfile(override) else [
            p for p in sorted(glob.glob(os.path.join(override, "**", "*.md"),
                                        recursive=True))
            if not p.endswith(".figures.md")]
    else:
        sibling = _sibling_md(cards_path)
        if sibling:
            paths = [sibling]
        else:
            theme = os.path.dirname(cards_path).replace("decks/", "extracted/", 1)
            paths = [p for p in sorted(glob.glob(os.path.join(theme, "*.md")))
                     if not p.endswith(".figures.md")]
    blob_text, page_text = [], {}
    single = len(paths) == 1
    for p in paths:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        blob_text.append(text)
        if single:  # page-accurate check only with an unambiguous single source
            markers = list(_MARKER_RE.finditer(text))
            for i, m in enumerate(markers):
                end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
                pg = int(m.group(1))
                page_text[pg] = page_text.get(pg, "") + text[m.end():end]
    src_idx = _index(" ".join(blob_text))
    by_page = {pg: _index(t) for pg, t in page_text.items()}
    return src_idx, by_page, paths


def _index(text):
    """(token set, 6-char prefixes) of the source text — for matching with
    morphology tolerance (mitochondria ~ mitochondrium)."""
    toks = {_norm(w) for w in _WORD_RE.findall(text) if len(w) >= 3}
    return toks, {w[:6] for w in toks if len(w) >= 6}


def _found(term, idx):
    toks, prefs = idx
    return term in toks or (len(term) >= 6 and term[:6] in prefs)


def _coverage(terms, idx):
    if not terms:
        return None, []
    missing = [t for t in terms if not _found(t, idx)]
    return (len(terms) - len(missing)) / len(terms), missing


def check(cards_path, source=None, min_cover=0.5, err_cover=0.25):
    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)
    src_idx, by_page, paths = _load_source(cards_path, source)
    cards = data.get("cards") or []

    errors, warnings, infos = [], [], []
    for i, card in enumerate(cards):
        terms = _terms(_answer_text(card))
        cover, missing = _coverage(terms, src_idx)
        if cover is None:
            infos.append(f"  [info]  card {i}: no checkable content words (e.g. only numbers).")
            continue
        sample = ", ".join(sorted(missing)[:6])
        if cover < err_cover:
            errors.append(f"  [ERROR] card {i}: answer barely found in source text "
                          f"({cover:.0%} covered) – possible hallucination. Missing: {sample}")
        elif cover < min_cover:
            warnings.append(f"  [warn]  card {i}: answer only partly in source text "
                            f"({cover:.0%}). Verify. Missing: {sample}")

        # Cross-check page citations (only with a single source that has page markers)
        cited = [int(n) for n in _PAGE_CITE_RE.findall(card.get("source", "") or "")]
        for pg in cited:
            if by_page and pg not in by_page:
                warnings.append(f"  [warn]  card {i}: cites p. {pg}, "
                                f"which does not exist in the source text.")
            elif by_page and terms:
                pcov, _ = _coverage(terms, by_page[pg])
                if pcov is not None and pcov < err_cover and cover >= min_cover:
                    warnings.append(f"  [warn]  card {i}: answer is not on the cited "
                                    f"p. {pg} ({pcov:.0%}) – check the page citation.")

    print(f"== Grounding: {cards_path} ({len(cards)} cards) ==")
    print(f"   Source: {', '.join(paths) if paths else '(none found!)'}")
    if not paths:
        print("  [ERROR] No source text found – nothing checked.")
        return 1
    for line in errors + warnings + infos:
        print(line)
    if not (errors or warnings):
        print("  all grounded ✓")
    print(f"-> {len(errors)} errors, {len(warnings)} warnings, {len(infos)} infos")
    return 1 if errors else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Check cards against the source text.")
    ap.add_argument("cards", help="decks/<topic>/<name>.cards.json")
    ap.add_argument("--source", help="source: .md file OR extracted/<topic>/ folder")
    ap.add_argument("--min-cover", type=float, default=0.5,
                    help="warn below this coverage (default 0.5)")
    ap.add_argument("--err-cover", type=float, default=0.25,
                    help="error below this coverage (default 0.25)")
    args = ap.parse_args(argv)
    return check(args.cards, args.source, args.min_cover, args.err_cover)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
