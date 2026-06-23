#!/usr/bin/env python3
"""Erzeugt/aktualisiert einen Abbildungs-Index zu aufbereiteten Markdown-Dateien.

Reines stdlib (kein PyMuPDF/Docker noetig) – laeuft direkt auf dem Host ueber die
bereits erzeugten aufbereitet/<Thema>/<name>.md. Wird von tools/extract.sh nach der
Extraktion automatisch aufgerufen, kann aber auch einzeln laufen.

Pro <name>.md:
  - scannt je Seite die Bildunterschriften ("Abb. N: ...") und ausgelassene Bilder,
  - schreibt aufbereitet/<Thema>/<name>.figures.md (Liste: Abb. N – S. P: Titel),
  - ergaenzt die Seitenmarker um die Abbildungszahl: "<!-- S. 21 · 2 Abb. -->".

So ist beim Kartenbau auf einen Blick sichtbar, wo Bilder liegen. Bei
raeumlich-visuellen Konzepten dann die echte PDF-Seite ansehen (Read-Tool,
pages="N") und ggf. eine occlusion-/Bildkarte bauen, statt das Bild zu uebersehen.

Idempotent: vorhandene "· N Abb."-Zusaetze werden vor dem Neuschreiben entfernt.

Aufruf:
  python3 tools/figindex.py aufbereitet/SWT/        # ganzer Themenordner (rekursiv)
  python3 tools/figindex.py aufbereitet/SWT/12_MET_Software_Architekturmetriken.md
"""
import os
import re
import sys

MARKER_RE = re.compile(r"<!--\s*S\.\s*(\d+)([^>]*?)-->")
CAPTION_RE = re.compile(r"Abb\.\s*(\d+)\s*:\**\s*([^\n]*)")
OMITTED_RE = re.compile(r"intentionally omitted")


def _clean_caption(raw):
    """Macht aus einer rohen Caption-Zeile einen knappen Titel."""
    s = raw
    for cut in ("<br>", "**---", "----- End", "----- Start"):
        idx = s.find(cut)
        if idx != -1:
            s = s[:idx]
    s = re.split(r"\.{3,}", s, 1)[0]      # Punktfuehrung eines Verzeichnis-Eintrags abschneiden
    s = s.replace("*", " ")
    s = re.sub(r"\s+", " ", s).strip(" —–-:")
    return s


def _flag(suffix):
    """Behaelt nur (OCR)/(leer) aus dem alten Marker-Suffix; alte Abb.-Zusaetze fallen weg."""
    m = re.search(r"\((OCR|leer)\)", suffix)
    return f" ({m.group(1)})" if m else ""


def scan(md_text):
    """-> (annotierter_text, index). index: sortierte Liste (num, seite, caption)."""
    markers = list(MARKER_RE.finditer(md_text))
    index = {}            # num -> (seite, caption); laengste Caption gewinnt
    out = []
    last = 0
    for i, m in enumerate(markers):
        out.append(md_text[last:m.start()])          # Seiteninhalt davor unveraendert
        page = int(m.group(1))
        flag = _flag(m.group(2))
        seg = md_text[m.end():(markers[i + 1].start() if i + 1 < len(markers) else len(md_text))]
        figs = {}
        for cm in CAPTION_RE.finditer(seg):
            if re.search(r"\.{4,}", cm.group(0)):   # Abbildungsverzeichnis-Eintrag (Punktfuehrung) -> kein echtes Bild
                continue
            num, cap = int(cm.group(1)), _clean_caption(cm.group(2))
            if num not in figs or len(cap) > len(figs[num]):
                figs[num] = cap
        k = len(figs) + len(OMITTED_RE.findall(seg))
        out.append(f"<!-- S. {page}{flag}" + (f" · {k} Abb." if k else "") + " -->")
        last = m.end()
        for num, cap in figs.items():
            if num not in index or len(cap) > len(index[num][1]):
                index[num] = (page, cap)
    out.append(md_text[last:])
    return "".join(out), sorted((num, p, c) for num, (p, c) in index.items())


def process(md_path):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    new_text, idx = scan(text)
    if new_text != text:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_text)
    fig_path = os.path.splitext(md_path)[0] + ".figures.md"
    if idx:
        lines = [
            f"# Abbildungen: {os.path.basename(md_path)}",
            "",
            f"{len(idx)} Abbildungen (S. = Position im aufbereiteten .md). "
            'Bild ansehen: Read-Tool auf das Original-PDF mit pages="<S.>".',
            "",
        ]
        lines += [f"- **Abb. {num}** — S. {page}: {cap or '(ohne Titel)'}" for num, page, cap in idx]
        with open(fig_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    elif os.path.exists(fig_path):
        os.remove(fig_path)
    return len(idx)


def _md_files(path):
    if os.path.isfile(path):
        return [path] if path.endswith(".md") and not path.endswith(".figures.md") else []
    out = []
    for root, _, files in os.walk(path):
        for fn in sorted(files):
            if fn.endswith(".md") and not fn.endswith(".figures.md"):
                out.append(os.path.join(root, fn))
    return out


def main(argv):
    if not argv:
        print("Aufruf: figindex.py <aufbereitet/Thema/ | datei.md>", file=sys.stderr)
        return 1
    total = 0
    for p in argv:
        for md in _md_files(p):
            n = process(md)
            total += n
            print(f"{md}: {n} Abbildungen")
    print(f"Fertig: {total} Abbildungen über alle Dateien.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
