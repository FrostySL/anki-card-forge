#!/usr/bin/env python3
"""Converts source PDFs into machine-readable Markdown (for efficient reading/citing).

Usage (normally via tools/extract.sh inside the extract container):
    python extract.py sources/Biology/chapter3.pdf
    python extract.py sources/Biology/               # whole topic folder
    python extract.py sources/Biology/x.pdf -o extracted/Biology/x.md
    python extract.py sources/Biology/x.pdf -j 8     # 8 pages in parallel (default: all cores)

pymupdf4llm reads the text layer as Markdown (keeps headings/tables) and OCRs
scanned pages automatically via Tesseract (language via --lang; add languages to
Dockerfile.extract if yours is missing). Pages are processed **in parallel**
(process pool) so large scanned PDFs use all CPU cores instead of crawling
page by page.

Every page gets a marker `<!-- p. N -->`; pages without a real text layer (text
came from OCR -> lower reliability) are marked `<!-- p. N (OCR) -->`, empty pages
`<!-- p. N (empty) -->`. That gives you page numbers for citations and makes OCR
pages recognizable when quoting (verify those against the original PDF).

Text sources (.md/.markdown/.txt) are mirrored into extracted/ unchanged
(no page markers), so grounding_check/coverage find them as sibling sources;
context.md/kontext.md are meta files and are skipped in folder runs.

Output: extracted/<topic>/<name>.md  (mirrored from sources/<topic>/...).
"""
import argparse
import concurrent.futures
import os
import sys

import fitz  # PyMuPDF
import pymupdf4llm

DEFAULT_LANG = "eng+deu"
MIN_CHARS = 20  # fewer alphanumeric chars on the page -> mark as (empty)
TEXT_EXTS = (".md", ".markdown", ".txt")
# Meta files, not sources: context.md steers card authoring (see CLAUDE.md)
# and must not become a grounding source.
META_NAMES = ("context.md", "kontext.md")


def _alnum_len(text):
    return sum(c.isalnum() for c in (text or ""))


def _process_pages(task):
    """Worker (own process): converts a subset of a PDF's pages.

    -> list of (page index, native_alnum, markdown). `native_alnum` is the length
    of the *real* text layer (before OCR), used to detect OCR pages.
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
    if npages == 0:
        print(f"WARN: {os.path.basename(in_path)} has 0 pages – skipped.", file=sys.stderr)
        return None

    jobs = jobs or (os.cpu_count() or 1)
    jobs = max(1, min(jobs, npages))

    # Distribute pages round-robin across the workers (even load).
    buckets = [[] for _ in range(jobs)]
    for i in range(npages):
        buckets[i % jobs].append(i)
    tasks = [(in_path, b, lang) for b in buckets if b]

    print(f"… {os.path.basename(in_path)}: {npages} pages, {jobs} in parallel", flush=True)
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
        from_ocr = native < MIN_CHARS  # no real text layer -> text came from OCR
        if _alnum_len(text) >= MIN_CHARS:
            tag = f"p. {n} (OCR)" if from_ocr else f"p. {n}"
            parts.append(f"<!-- {tag} -->\n\n{text}")
            if from_ocr:
                ocr_pages += 1
        else:
            parts.append(f"<!-- p. {n} (empty) -->")
            empty_pages += 1

    md = "\n\n".join(parts).strip() + "\n"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(
        f"OK: {os.path.basename(in_path)} -> {out_path}  "
        f"({npages} pages; {ocr_pages} via OCR, {empty_pages} empty)"
    )
    return out_path


def convert_text(in_path, out_path):
    """Mirrors a text/Markdown source into extracted/ unchanged.

    Text sources need no PDF machinery, but WITHOUT the extracted/ mirror the
    whole quality pipeline goes blind: grounding_check/coverage look up their
    source as the sibling .md under extracted/<topic>/. No page markers exist,
    so the page-citation check simply stays off (global check still runs).
    """
    with open(in_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")
    print(f"OK: {os.path.basename(in_path)} -> {out_path}  (text source, no page markers)")
    return out_path


def _rel_to_cwd(path):
    """Path relative to the cwd, '/'-separated — so './sources/x.pdf' and the
    absolute form are recognized like 'sources/x.pdf'. Paths outside the cwd
    come back with '../' and simply don't match the sources/ prefix."""
    try:
        rel = os.path.relpath(os.path.abspath(path))
    except ValueError:  # Windows: other drive -> no relative form
        rel = path
    return rel.replace(os.sep, "/")


def _default_out(in_path):
    """sources/<topic>/<name>.pdf -> extracted/<topic>/<name>.md"""
    norm = _rel_to_cwd(in_path)
    base = os.path.splitext(os.path.basename(in_path))[0] + ".md"
    if norm.startswith("sources/"):
        rel = norm[len("sources/"):]          # <topic>/<name>.pdf
        theme = os.path.dirname(rel)          # <topic> (may be empty)
        return os.path.join("extracted", theme, base)
    return os.path.join("extracted", base)


def _sources_in(folder):
    """PDF and text sources of a topic folder (context.md etc. excluded)."""
    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith((".pdf",) + TEXT_EXTS)
        and f.lower() not in META_NAMES
    )


def main(argv):
    ap = argparse.ArgumentParser(description="PDF -> Markdown (parallel, with OCR).")
    ap.add_argument("input", help="PDF file or folder (e.g. sources/Biology/)")
    ap.add_argument("-o", "--out", help="target .md (single file only)")
    ap.add_argument("-j", "--jobs", type=int, default=0,
                    help="parallel page workers (default: all CPU cores)")
    ap.add_argument("--lang", default=DEFAULT_LANG,
                    help=f"OCR languages (Tesseract), default {DEFAULT_LANG}")
    args = ap.parse_args(argv)

    if os.path.isdir(args.input):
        sources = _sources_in(args.input)
        if not sources:
            print(f"No PDF/text sources in {args.input}", file=sys.stderr)
            return 1
        if args.out:
            print("-o/--out is ignored for folder input.", file=sys.stderr)
        for p in sources:
            if p.lower().endswith(".pdf"):
                convert(p, _default_out(p), args.lang, args.jobs)
            else:
                convert_text(p, _default_out(p))
        return 0

    if not os.path.isfile(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1
    if args.input.lower().endswith(TEXT_EXTS):
        convert_text(args.input, args.out or _default_out(args.input))
        return 0
    if not args.input.lower().endswith(".pdf"):
        print(f"Only PDF/Markdown/text supported (got: {args.input})", file=sys.stderr)
        return 1

    out = args.out or _default_out(args.input)
    convert(args.input, out, args.lang, args.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
