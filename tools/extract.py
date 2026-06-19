#!/usr/bin/env python3
"""Konvertiert Quell-PDFs in maschinenlesbares Markdown (fuer effizientes Lesen/Zitieren).

Aufruf (i. d. R. ueber tools/extract.sh im Extract-Container):
    python extract.py quellen/EWP/03_Arbeitstechniken.pdf
    python extract.py quellen/EWP/                 # ganzen Themenordner
    python extract.py quellen/EWP/x.pdf -o aufbereitet/EWP/x.md
    python extract.py quellen/EWP/x.pdf -j 8       # 8 Seiten parallel (Default: alle Kerne)

pymupdf4llm liest die Textschicht als Markdown (behaelt Ueberschriften/Tabellen) und
OCR-t gescannte Seiten automatisch per Tesseract (Sprache via --lang, Default deu+eng).
Die Seiten werden **parallel** verarbeitet (Prozess-Pool), damit grosse gescannte PDFs
alle CPU-Kerne nutzen statt Seite fuer Seite zu kriechen.

Jede Seite bekommt einen Marker `<!-- S. N -->`; Seiten ohne echte Textschicht (Text
stammt aus OCR -> geringere Zuverlaessigkeit) werden `<!-- S. N (OCR) -->` markiert,
leere Seiten `<!-- S. N (leer) -->`. So sind Seitenzahlen fuer Quellenangaben da und
OCR-Seiten beim Zitieren erkennbar (dann gegen das Original-PDF gegenpruefen).

Ausgabe: aufbereitet/<Thema>/<name>.md  (gespiegelt aus quellen/<Thema>/...).
"""
import argparse
import concurrent.futures
import os
import sys

import fitz  # PyMuPDF
import pymupdf4llm

DEFAULT_LANG = "deu+eng"
MIN_CHARS = 20  # weniger alphanumerische Zeichen auf der Seite -> als (leer) markieren


def _alnum_len(text):
    return sum(c.isalnum() for c in (text or ""))


def _process_pages(task):
    """Worker (eigener Prozess): konvertiert eine Teilmenge der Seiten einer PDF.

    -> Liste von (seitenindex, native_alnum, markdown). `native_alnum` ist die
    Laenge der *echten* Textschicht (vor OCR), um OCR-Seiten zu erkennen.
    """
    in_path, page_indices, lang = task
    doc = fitz.open(in_path)
    out = []
    for i in page_indices:
        native = _alnum_len(doc[i].get_text())
        md = pymupdf4llm.to_markdown(doc, pages=[i], ocr_language=lang)
        out.append((i, native, (md or "").strip()))
    doc.close()
    return out


def convert(in_path, out_path, lang=DEFAULT_LANG, jobs=0):
    doc = fitz.open(in_path)
    npages = doc.page_count
    doc.close()

    jobs = jobs or (os.cpu_count() or 1)
    jobs = max(1, min(jobs, npages))

    # Seiten rundlaufend auf die Worker verteilen (gleichmaessige Last).
    buckets = [[] for _ in range(jobs)]
    for i in range(npages):
        buckets[i % jobs].append(i)
    tasks = [(in_path, b, lang) for b in buckets if b]

    print(f"… {os.path.basename(in_path)}: {npages} Seiten, {jobs} parallel", flush=True)
    results = {}
    if jobs == 1:
        for i, native, md in _process_pages(tasks[0]):
            results[i] = (native, md)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
            for chunk in ex.map(_process_pages, tasks):
                for i, native, md in chunk:
                    results[i] = (native, md)

    parts = []
    ocr_pages = empty_pages = 0
    for i in range(npages):
        native, text = results[i]
        n = i + 1
        from_ocr = native < MIN_CHARS  # keine echte Textschicht -> Text kam aus OCR
        if _alnum_len(text) >= MIN_CHARS:
            tag = f"S. {n} (OCR)" if from_ocr else f"S. {n}"
            parts.append(f"<!-- {tag} -->\n\n{text}")
            if from_ocr:
                ocr_pages += 1
        else:
            parts.append(f"<!-- S. {n} (leer) -->")
            empty_pages += 1

    md = "\n\n".join(parts).strip() + "\n"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(
        f"OK: {os.path.basename(in_path)} -> {out_path}  "
        f"({npages} Seiten; {ocr_pages} per OCR, {empty_pages} leer)"
    )
    return out_path


def _default_out(in_path):
    """quellen/<Thema>/<name>.pdf -> aufbereitet/<Thema>/<name>.md"""
    norm = in_path.replace(os.sep, "/")
    base = os.path.splitext(os.path.basename(in_path))[0] + ".md"
    if norm.startswith("quellen/"):
        rel = norm[len("quellen/"):]          # <Thema>/<name>.pdf
        theme = os.path.dirname(rel)          # <Thema> (kann leer sein)
        return os.path.join("aufbereitet", theme, base)
    return os.path.join("aufbereitet", base)


def _pdfs_in(folder):
    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".pdf")
    )


def main(argv):
    ap = argparse.ArgumentParser(description="PDF -> Markdown (parallel, mit OCR).")
    ap.add_argument("input", help="PDF-Datei oder Ordner (z. B. quellen/EWP/)")
    ap.add_argument("-o", "--out", help="Ziel-.md (nur bei Einzeldatei)")
    ap.add_argument("-j", "--jobs", type=int, default=0,
                    help="parallele Seiten-Worker (Default: alle CPU-Kerne)")
    ap.add_argument("--lang", default=DEFAULT_LANG,
                    help=f"OCR-Sprachen (Tesseract), Default {DEFAULT_LANG}")
    args = ap.parse_args(argv)

    if os.path.isdir(args.input):
        pdfs = _pdfs_in(args.input)
        if not pdfs:
            print(f"Keine PDFs in {args.input}", file=sys.stderr)
            return 1
        if args.out:
            print("-o/--out wird bei Ordner-Eingabe ignoriert.", file=sys.stderr)
        for p in pdfs:
            convert(p, _default_out(p), args.lang, args.jobs)
        return 0

    if not os.path.isfile(args.input):
        print(f"Eingabe nicht gefunden: {args.input}", file=sys.stderr)
        return 1
    if not args.input.lower().endswith(".pdf"):
        print(f"Nur PDF unterstuetzt (bekam: {args.input})", file=sys.stderr)
        return 1

    out = args.out or _default_out(args.input)
    convert(args.input, out, args.lang, args.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
