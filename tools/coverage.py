#!/usr/bin/env python3
"""Coverage & near-duplicates across all cards.json of a topic (pure Python).

    python3 tools/coverage.py decks/SWT/                 # whole topic folder
    python3 tools/coverage.py decks/SWT/04_UML.cards.json decks/SWT/03_ANA.cards.json
    python3 tools/coverage.py decks/T/new.cards.json --against decks/_anki-mirror/
                                                     # ^ dedupe vs the live collection

Complements lint_cards.py (which only checks ONE file for *exact* duplicates) with:
  1. **Near-duplicates** across file boundaries (token Jaccard of the questions) —
     for topics with many chapters where the same fact easily lands twice.
  2. **Coverage gaps**: per file, the cited source pages (`source: "... p. N"`)
     against the pages of the sibling .md (extracted/<topic>/<name>.md) — which
     pages have no card (yet)? Plus cards without any `source`.

Informational only (exit 0); with --strict, near-duplicates give exit 1.
"""
import argparse
import glob
import json
import os
import re
import sys

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
# Page citations/markers: English "p. N" and legacy German "S. N" both accepted.
# \b so that e.g. "Kap. 8" (chapter) is not misread as a page citation.
_PAGE_CITE_RE = re.compile(r"\b(?:p|S)\.\s*(\d+)")
_MARKER_RE = re.compile(r"<!--\s*(?:p|S)\.\s*(\d+)([^>]*?)-->")
# German + English question/function words; other languages just skip filtering.
_STOP = set("""
und oder der die das den dem des ein eine einen einem einer eines kein keine was
ist sind welche welcher welches wie warum wozu wann wo wer wieviel nenne nennen
fuer für mit von zu im in an um es bei auf aus nicht so dies diese woran wodurch
the and for with that this from are was were what which when where who why how
does name give state which
""".split())


def _norm(w):
    return (w.lower().replace("ä", "ae").replace("ö", "oe")
            .replace("ü", "ue").replace("ß", "ss"))


def _front_text(card):
    ctype = card.get("type", "basic")
    if ctype == "cloze":
        return _TAG_RE.sub(" ", card.get("text", ""))
    if ctype == "occlusion":
        return (card.get("header", "") + " "
                + " ".join((r.get("label") or "") for r in card.get("regions") or []))
    return _TAG_RE.sub(" ", card.get("front", ""))


def _tokens(text):
    return {_norm(w) for w in _WORD_RE.findall(text or "")
            if len(w) >= 3 and _norm(w) not in _STOP}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cards_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "*.cards.json")))
        elif p.endswith(".cards.json"):
            out.append(p)
    return out


def _sibling_md(cards_path):
    """The matching extracted/ .md — exact or by prefix (cards 'short', .md 'long')."""
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


def _source_pages(cards_path):
    """Existing (non-empty) pages of the sibling .md -> set of page numbers."""
    md = _sibling_md(cards_path)
    if not md:
        return None
    pages = set()
    with open(md, encoding="utf-8") as f:
        for m in _MARKER_RE.finditer(f.read()):
            # "empty"/"leer" marker suffix = page without content
            if "empty" not in m.group(2) and "leer" not in m.group(2):
                pages.add(int(m.group(1)))
    return pages


def _fmt_pages(pages):
    """Sorted pages as compact ranges: {1,2,3,7} -> '1-3, 7'."""
    pages = sorted(pages)
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}-{pages[j]}")
        i = j + 1
    return ", ".join(out)


def _corpus_entries(against, exclude_files):
    """All cards under `against` (recursive — matches the mirror layout
    decks/_anki-mirror/<deck>_cards/*.cards.json) as duplicate-check corpus.
    Files that are also direct inputs are skipped."""
    skip = {os.path.realpath(f) for f in exclude_files}
    entries = []
    for cf in sorted(glob.glob(os.path.join(against, "**", "*.cards.json"),
                               recursive=True)):
        if os.path.realpath(cf) in skip:
            continue
        with open(cf, encoding="utf-8") as f:
            cards = (json.load(f).get("cards") or [])
        for i, c in enumerate(cards):
            entries.append((cf, i, _front_text(c).strip()[:70],
                            _tokens(_front_text(c))))
    return entries


def run(paths, threshold=0.8, strict=False, against=None):
    files = _cards_files(paths)
    if not files:
        print("No cards.json found.", file=sys.stderr)
        return 1

    entries = []  # (file, index, front text, tokens)
    print("== Coverage per file ==")
    for cf in files:
        with open(cf, encoding="utf-8") as f:
            cards = (json.load(f).get("cards") or [])
        cited, no_src = set(), 0
        for i, c in enumerate(cards):
            entries.append((cf, i, _front_text(c).strip()[:70], _tokens(_front_text(c))))
            cite = _PAGE_CITE_RE.findall(c.get("source", "") or "")
            if cite:
                cited.update(int(n) for n in cite)
            else:
                no_src += 1
        src_pages = _source_pages(cf)
        line = f"  {os.path.basename(cf):42} {len(cards):3} cards"
        if no_src:
            line += f"; {no_src} without source"
        if src_pages:
            gaps = src_pages - cited
            # Only count citations of pages that actually exist — a wrong
            # citation (p. 99 in a 10-page source) must not inflate coverage.
            covered = cited & src_pages
            bogus = cited - src_pages
            line += (f"; source pages {len(covered)}/{len(src_pages)} covered"
                     + (f", gaps: p. {_fmt_pages(gaps)}" if gaps else ", no gaps ✓"))
            if bogus:
                line += f"\n    [warn] cites non-existent page(s): p. {_fmt_pages(bogus)}"
        print(line)

    print(f"\n== Near-duplicates (Jaccard ≥ {threshold:.0%}) ==")
    dups = 0

    def _report(a, b, j):
        fa, ia, ta, _ = a
        fb, ib, tb, _ = b
        tag = "EXACT" if ta.lower() == tb.lower() else f"{j:.0%}"
        print(f"  [{tag}] {os.path.basename(fa)}#{ia} ~ {os.path.basename(fb)}#{ib}")
        print(f"         A: {ta!r}")
        print(f"         B: {tb!r}")

    for a in range(len(entries)):
        for b in range(a + 1, len(entries)):
            j = _jaccard(entries[a][3], entries[b][3])
            if j >= threshold:
                dups += 1
                _report(entries[a], entries[b], j)
    if not dups:
        print("  none found ✓")

    corpus = _corpus_entries(against, files) if against else []
    if against:
        print(f"\n== Against corpus: {against} ({len(corpus)} cards) ==")
        corpus_dups = 0
        for a in range(len(entries)):
            for c in range(len(corpus)):
                j = _jaccard(entries[a][3], corpus[c][3])
                if j >= threshold:
                    corpus_dups += 1
                    _report(entries[a], corpus[c], j)
        if not corpus_dups:
            print("  none found ✓")
        dups += corpus_dups

    print(f"\n-> {len(files)} file(s), {len(entries)} cards, {dups} near-duplicate(s).")
    return 1 if (strict and dups) else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Coverage & duplicates across cards.json.")
    ap.add_argument("paths", nargs="+", help="decks/<topic>/ OR individual .cards.json")
    ap.add_argument("--threshold", type=float, default=0.8,
                    help="Jaccard threshold for near-duplicates (default 0.8)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on duplicates")
    ap.add_argument("--against", metavar="DIR",
                    help="additionally check the inputs against every "
                         "*.cards.json under DIR (recursive) — e.g. the live-"
                         "collection mirror decks/_anki-mirror/; corpus cards "
                         "are only compared against, not linted themselves")
    args = ap.parse_args(argv)
    return run(args.paths, args.threshold, args.strict, args.against)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
