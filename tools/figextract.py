#!/usr/bin/env python3
"""Crops figures out of source PDFs as PNGs (for image/occlusion cards and a
cheap visual check).

Usage (normally via tools/figextract.sh inside the extract container):
    python figextract.py sources/SWT/04_UML.pdf
    python figextract.py sources/SWT/                  # whole topic folder
    python figextract.py sources/SWT/04_UML.pdf --min-area 0.05 --zoom 2.5

Why: the extracted .md contains captions only, no pixels. Slide diagrams
(UML/OOD ...) live in the PDF as vector graphics or embedded raster images and
have no standalone image file — but occlusion needs an `image`. This tool
extracts them:
  - embedded **raster images** (photos/screenshots) -> cropped exactly,
  - **vector clusters** (drawn diagrams) via PyMuPDF cluster_drawings().

Result per PDF (mirrored into extracted/<topic>/):
  extracted/<topic>/figures/<name>_p<page>_<i>.png   — the crops
  extracted/<topic>/<name>.figures.json              — manifest (page, bbox 0..1, kind)

The crops are small -> cheap to view with the Read tool (instead of loading the
whole PDF page) and directly usable as an occlusion `image` (path relative to the
project root, file names globally unique via the <name> prefix). Page numbers are
1-based like the `<!-- p. N -->` markers in the .md and the `<name>.figures.md`
(caption index, figindex.py).
"""
import argparse
import json
import os
import sys

import fitz  # PyMuPDF


def _rects_from_images(page):
    """Placement rectangles of all embedded raster images on the page."""
    rects = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            for r in page.get_image_rects(xref):
                rects.append(("raster", fitz.Rect(r)))
        except Exception:
            pass
    return rects


def _rects_from_drawings(page):
    """Bounding boxes of connected vector graphics (drawn diagrams)."""
    if not hasattr(page, "cluster_drawings"):
        return []
    try:
        clusters = page.cluster_drawings()
    except Exception:
        return []
    return [("vector", fitz.Rect(r)) for r in clusters]


def _overlap_ratio(a, b):
    inter = a & b  # intersection rect (empty -> area 0)
    ia = inter.get_area() if not inter.is_empty else 0.0
    smaller = min(a.get_area(), b.get_area()) or 1.0
    return ia / smaller


def _merge(rects, thresh=0.5):
    """Merges strongly overlapping rectangles (raster images are often reported
    multiple times; vector clusters overlap raster). Largest first, smaller ones
    get merged in."""
    rects = sorted(rects, key=lambda kr: kr[1].get_area(), reverse=True)
    kept = []
    for kind, r in rects:
        for i, (k2, r2) in enumerate(kept):
            if _overlap_ratio(r, r2) > thresh:
                kept[i] = (k2, r2 | r)  # union; keep the kind of the larger one
                break
        else:
            kept.append((kind, r))
    return kept


def _frac(rect, page_rect):
    pw, ph = page_rect.width or 1, page_rect.height or 1
    return {
        "x": round((rect.x0 - page_rect.x0) / pw, 4),
        "y": round((rect.y0 - page_rect.y0) / ph, 4),
        "w": round(rect.width / pw, 4),
        "h": round(rect.height / ph, 4),
    }


def _figures_on_page(page, min_area, max_area, min_side):
    """Filtered, merged figure rectangles of a page (1 = whole page)."""
    pr = page.rect
    page_area = (pr.width * pr.height) or 1.0
    candidates = _rects_from_images(page) + _rects_from_drawings(page)
    out = []
    for kind, r in _merge(candidates):
        f = _frac(r, pr)
        area = (r.width * r.height) / page_area
        if not (min_area <= area <= max_area):
            continue
        if f["w"] < min_side or f["h"] < min_side:  # drop thin lines/bands
            continue
        out.append((kind, r, f, area))
    out.sort(key=lambda t: (t[2]["y"], t[2]["x"]))  # top->bottom, left->right
    return out


def extract(in_path, out_dir, zoom=2.0, min_area=0.03, max_area=0.92,
            min_side=0.06, max_per_page=8):
    stem = os.path.splitext(os.path.basename(in_path))[0]
    fig_dir = os.path.join(out_dir, "figures")
    manifest = []
    doc = fitz.open(in_path)
    mat = fitz.Matrix(zoom, zoom)
    for i in range(doc.page_count):
        page = doc[i]
        figs = _figures_on_page(page, min_area, max_area, min_side)[:max_per_page]
        if figs:
            os.makedirs(fig_dir, exist_ok=True)
        for n, (kind, rect, frac, area) in enumerate(figs, start=1):
            fname = f"{stem}_p{i + 1}_{n}.png"
            rel = os.path.join(fig_dir, fname)
            page.get_pixmap(matrix=mat, clip=rect).save(rel)
            manifest.append({
                "page": i + 1,            # 1-based like the <!-- p. N --> markers
                "kind": kind,             # raster | vector
                "image": rel,             # path relative to project root (occlusion `image`)
                "area": round(area, 4),   # fraction of the page area
                **frac,                   # x, y, w, h as fractions 0..1
            })
    doc.close()

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, stem + ".figures.json")
    if manifest:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"source": in_path.replace(os.sep, "/"), "figures": manifest},
                      f, ensure_ascii=False, indent=2)
    elif os.path.exists(json_path):
        os.remove(json_path)
    print(f"OK: {stem}: {len(manifest)} figure(s) -> {fig_dir}/")
    return len(manifest)


def _rel_to_cwd(path):
    """Path relative to the cwd, '/'-separated — so './sources/x.pdf' and the
    absolute form are recognized like 'sources/x.pdf' (same logic as
    extract._rel_to_cwd; keep in sync)."""
    try:
        rel = os.path.relpath(os.path.abspath(path))
    except ValueError:  # Windows: other drive -> no relative form
        rel = path
    return rel.replace(os.sep, "/")


def _default_out_dir(in_path):
    """sources/<topic>/<name>.pdf -> extracted/<topic>/"""
    norm = _rel_to_cwd(in_path)
    if norm.startswith("sources/"):
        return os.path.join("extracted", os.path.dirname(norm[len("sources/"):]))
    return "extracted"


def _pdfs_in(folder):
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(".pdf"))


def main(argv):
    ap = argparse.ArgumentParser(description="Crop figures out of a PDF (-> PNG crops).")
    ap.add_argument("input", help="PDF file or folder (e.g. sources/SWT/)")
    ap.add_argument("--zoom", type=float, default=2.0, help="render zoom of the crops (default 2.0)")
    ap.add_argument("--min-area", type=float, default=0.03,
                    help="smallest figure as fraction of the page area (default 0.03)")
    ap.add_argument("--max-area", type=float, default=0.92,
                    help="largest figure (default 0.92; above = page background)")
    ap.add_argument("--min-side", type=float, default=0.06,
                    help="smallest edge length as a fraction (default 0.06)")
    args = ap.parse_args(argv)

    inputs = _pdfs_in(args.input) if os.path.isdir(args.input) else [args.input]
    if not inputs:
        print(f"No PDFs in {args.input}", file=sys.stderr)
        return 1
    total = 0
    processed = 0
    for p in inputs:
        if not p.lower().endswith(".pdf") or not os.path.isfile(p):
            print(f"Skipped (not a PDF file): {p}", file=sys.stderr)
            continue
        processed += 1
        total += extract(p, _default_out_dir(p), args.zoom,
                         args.min_area, args.max_area, args.min_side)
    print(f"Done: {total} figure(s) across all files.")
    if processed == 0:
        # Everything skipped (typo'd path etc.) must not look like success —
        # callers with set -e would silently carry on without any crops.
        print("No input was processed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
