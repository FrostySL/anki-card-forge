#!/usr/bin/env python3
"""Prueft, ob jede Karte durch den Quelltext gedeckt ist (Anti-Halluzination).

    python3 tools/grounding_check.py decks/SWT/04_UML.cards.json
    python3 tools/grounding_check.py decks/SWT/04_UML.cards.json --source aufbereitet/SWT/04_UML.md

Reines Python, keine Deps. Fuer jede Karte werden die **Inhaltswoerter der Antwort**
(back / Cloze-Luecken / Occlusion-Labels) gegen den aufbereiteten Quelltext geprueft:
tauchen sie dort auf? Zitiert `source` eine Seite ("S. N"), wird zusaetzlich geprueft,
ob die Antwort **auf dieser Seite** steht. So fallen erfundene Fakten und falsche
Seitenangaben *vor* dem Build auf.

Quelle: ohne --source automatisch die Schwester-.md
(decks/<Thema>/<name>.cards.json -> aufbereitet/<Thema>/<name>.md); fehlt sie, wird der
ganze Themenordner aufbereitet/<Thema>/ herangezogen (dann nur globale Pruefung).

Heuristik – kein Ersatz fuer Nachdenken: niedrige Deckung = "bitte gegen die Quelle
gegenpruefen", nicht zwingend falsch (Paraphrasen/Synonyme schlagen evtl. fehl).
"""
import argparse
import glob
import json
import os
import re
import sys

_CLOZE_RE = re.compile(r"\{\{c\d+::(.+?)(?:::.+?)?\}\}", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_PAGE_CITE_RE = re.compile(r"S\.\s*(\d+)")
_MARKER_RE = re.compile(r"<!--\s*S\.\s*(\d+)[^>]*-->")
_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+")


def _norm(token):
    t = token.lower()
    return (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))


# Funktionswoerter raus – sie sind ueberall und sagen nichts ueber Deckung aus.
_STOP = set(_norm(w) for w in """
und oder aber denn weil dass wenn als wie also dann noch nur auch sehr mehr
der die das den dem des ein eine einen einem einer eines kein keine nach durch
ist sind war waren wird werden wurde wurden sein hat haben hatte habe dazu damit
fuer für mit ohne bei beim aus auf vom von zum zur zu im in an am um es er sie wir
ich du ihr man sich nicht so dies diese dieser dieses jede jeder jedes sowie bzw
ueber über sowohl sondern jedoch dabei somit etwa mehrere viele ihre seine deren
the and for with that this from are was were can will not all any one two each
""".split())


def _terms(text):
    """Inhaltswoerter (normalisiert): laenge>=4 und kein Stoppwort, plus kurze
    Akronyme (Grossbuchstaben, z. B. UML, TDD, OOD)."""
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
    if ctype == "cloze":
        return " ".join(_CLOZE_RE.findall(card.get("text", "")))
    if ctype == "occlusion":
        return " ".join((r.get("label") or "") for r in card.get("regions") or [])
    return _strip(card.get("back", ""))


def _sibling_md(cards_path):
    """Zugehoerige aufbereitet/-.md zur cards.json – exakt oder per Praefix (cards heisst
    oft kurz '08_TST', die .md lang '08_TST_Testen_TDD'). -> Pfad oder None."""
    exact = cards_path.replace("decks/", "aufbereitet/", 1).replace(".cards.json", ".md")
    if os.path.isfile(exact):
        return exact
    theme = os.path.dirname(cards_path).replace("decks/", "aufbereitet/", 1)
    stem = os.path.basename(cards_path)[:-len(".cards.json")]
    cands = [p for p in sorted(glob.glob(os.path.join(theme, "*.md")))
             if not p.endswith(".figures.md")]
    pref = [p for p in cands if os.path.basename(p)[:-3].startswith(stem)
            or stem.startswith(os.path.basename(p)[:-3])]
    return pref[0] if len(pref) == 1 else None


def _load_source(cards_path, override):
    """-> (gesamt_normtext, {seite: normtext}, pfade). Mehrere Quellen: nur Gesamttext."""
    if override:
        paths = [override] if os.path.isfile(override) else sorted(
            glob.glob(os.path.join(override, "**", "*.md"), recursive=True))
    else:
        sibling = _sibling_md(cards_path)
        if sibling:
            paths = [sibling]
        else:
            theme = os.path.dirname(cards_path).replace("decks/", "aufbereitet/", 1)
            paths = [p for p in sorted(glob.glob(os.path.join(theme, "*.md")))
                     if not p.endswith(".figures.md")]
    blob_text, page_text = [], {}
    single = len(paths) == 1
    for p in paths:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        blob_text.append(text)
        if single:  # Seiten-genaue Pruefung nur bei eindeutiger Einzelquelle
            markers = list(_MARKER_RE.finditer(text))
            for i, m in enumerate(markers):
                end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
                pg = int(m.group(1))
                page_text[pg] = page_text.get(pg, "") + text[m.end():end]
    src_idx = _index(" ".join(blob_text))
    by_page = {pg: _index(t) for pg, t in page_text.items()}
    return src_idx, by_page, paths


def _index(text):
    """(Token-Menge, 6-Zeichen-Praefixe) des Quelltexts – fuer Treffer mit
    Morphologie-Toleranz (Mitochondrien ~ Mitochondrium)."""
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
            infos.append(f"  [info]  Karte {i}: keine pruefbaren Inhaltswoerter (z. B. nur Zahlen).")
            continue
        sample = ", ".join(sorted(missing)[:6])
        if cover < err_cover:
            errors.append(f"  [FEHLER] Karte {i}: Antwort kaum im Quelltext "
                          f"({cover:.0%} gedeckt) – evtl. Halluzination. Fehlt: {sample}")
        elif cover < min_cover:
            warnings.append(f"  [warn]  Karte {i}: Antwort nur teils im Quelltext "
                            f"({cover:.0%}). Pruefen. Fehlt: {sample}")

        # Seitenzitat gegenpruefen (nur wenn Einzelquelle mit Seitenmarkern vorliegt)
        cited = [int(n) for n in _PAGE_CITE_RE.findall(card.get("source", "") or "")]
        for pg in cited:
            if by_page and pg not in by_page:
                warnings.append(f"  [warn]  Karte {i}: zitiert S. {pg}, "
                                f"die es im Quelltext nicht gibt.")
            elif by_page and terms:
                pcov, _ = _coverage(terms, by_page[pg])
                if pcov is not None and pcov < err_cover and cover >= min_cover:
                    warnings.append(f"  [warn]  Karte {i}: Antwort steht nicht auf der "
                                    f"zitierten S. {pg} ({pcov:.0%}) – Seitenangabe pruefen.")

    print(f"== Grounding: {cards_path} ({len(cards)} Karten) ==")
    print(f"   Quelle: {', '.join(paths) if paths else '(keine gefunden!)'}")
    if not paths:
        print("  [FEHLER] Kein Quelltext gefunden – nichts geprueft.")
        return 1
    for line in errors + warnings + infos:
        print(line)
    if not (errors or warnings):
        print("  alles gedeckt ✓")
    print(f"-> {len(errors)} Fehler, {len(warnings)} Warnungen, {len(infos)} Infos")
    return 1 if errors else 0


def main(argv):
    ap = argparse.ArgumentParser(description="Karten gegen den Quelltext pruefen.")
    ap.add_argument("cards", help="decks/<Thema>/<name>.cards.json")
    ap.add_argument("--source", help="Quelle: .md-Datei ODER aufbereitet/<Thema>/-Ordner")
    ap.add_argument("--min-cover", type=float, default=0.5,
                    help="unter diesem Deckungsgrad Warnung (Default 0.5)")
    ap.add_argument("--err-cover", type=float, default=0.25,
                    help="unter diesem Deckungsgrad Fehler (Default 0.25)")
    args = ap.parse_args(argv)
    return check(args.cards, args.source, args.min_cover, args.err_cover)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
