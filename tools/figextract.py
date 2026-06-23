#!/usr/bin/env python3
"""Schneidet Abbildungen aus Quell-PDFs als PNG heraus (fuer Bild-/Occlusion-Karten
und einen billigen Bild-Check).

Aufruf (i. d. R. ueber tools/figextract.sh im Extract-Container):
    python figextract.py quellen/SWT/04_UML.pdf
    python figextract.py quellen/SWT/                  # ganzer Themenordner
    python figextract.py quellen/SWT/04_UML.pdf --min-area 0.05 --zoom 2.5

Warum: Das aufbereitete .md enthaelt nur Captions, keine Pixel. Folien-Diagramme
(UML/OOD ...) liegen als Vektorgrafik oder eingebettetes Rasterbild im PDF und haben
keine eigene Bilddatei – occlusion braucht aber ein `image`. Dieses Tool extrahiert sie:
  - eingebettete **Rasterbilder** (Fotos/Screenshots) -> exakt zugeschnitten,
  - **Vektor-Cluster** (gezeichnete Diagramme) via PyMuPDF cluster_drawings().

Ergebnis pro PDF (gespiegelt nach aufbereitet/<Thema>/):
  aufbereitet/<Thema>/figures/<name>_S<Seite>_<i>.png   – die Crops
  aufbereitet/<Thema>/<name>.figures.json               – Manifest (Seite, Bbox 0..1, Art)

Die Crops sind klein -> billig per Read-Tool ansehen (statt die ganze PDF-Seite zu
laden) und direkt als occlusion-`image` referenzierbar (Pfad relativ zum Projekt-Root,
Dateinamen global eindeutig durch <name>-Praefix). Seitenzahlen sind 1-basiert wie die
`<!-- S. N -->`-Marker im .md und die `<name>.figures.md` (Caption-Index, figindex.py).
"""
import argparse
import json
import os
import sys

import fitz  # PyMuPDF


def _rects_from_images(page):
    """Platzierungs-Rechtecke aller eingebetteten Rasterbilder der Seite."""
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
    """Bounding-Boxen zusammenhaengender Vektorgrafik (gezeichnete Diagramme)."""
    if not hasattr(page, "cluster_drawings"):
        return []
    try:
        clusters = page.cluster_drawings()
    except Exception:
        return []
    return [("vektor", fitz.Rect(r)) for r in clusters]


def _overlap_ratio(a, b):
    inter = a & b  # Schnitt-Rechteck (leer -> Flaeche 0)
    ia = inter.get_area() if not inter.is_empty else 0.0
    smaller = min(a.get_area(), b.get_area()) or 1.0
    return ia / smaller


def _merge(rects, thresh=0.5):
    """Vereinigt stark ueberlappende Rechtecke (Raster wird oft mehrfach gemeldet;
    Vektor-Cluster ueberlappen Raster). Groesste zuerst, kleinere verschmelzen rein."""
    rects = sorted(rects, key=lambda kr: kr[1].get_area(), reverse=True)
    kept = []
    for kind, r in rects:
        for i, (k2, r2) in enumerate(kept):
            if _overlap_ratio(r, r2) > thresh:
                kept[i] = (k2, r2 | r)  # Union; Art des groesseren behalten
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
    """Gefilterte, zusammengefuehrte Figur-Rechtecke einer Seite (1 = ganze Seite)."""
    pr = page.rect
    page_area = (pr.width * pr.height) or 1.0
    candidates = _rects_from_images(page) + _rects_from_drawings(page)
    out = []
    for kind, r in _merge(candidates):
        f = _frac(r, pr)
        area = (r.width * r.height) / page_area
        if not (min_area <= area <= max_area):
            continue
        if f["w"] < min_side or f["h"] < min_side:  # duenne Linien/Baender raus
            continue
        out.append((kind, r, f, area))
    out.sort(key=lambda t: (t[2]["y"], t[2]["x"]))  # oben->unten, links->rechts
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
            fname = f"{stem}_S{i + 1}_{n}.png"
            rel = os.path.join(fig_dir, fname)
            page.get_pixmap(matrix=mat, clip=rect).save(rel)
            manifest.append({
                "page": i + 1,            # 1-basiert wie die <!-- S. N -->-Marker
                "kind": kind,             # raster | vektor
                "image": rel,             # Pfad relativ zum Projekt-Root (occlusion-`image`)
                "area": round(area, 4),   # Flaechenanteil der Seite
                **frac,                   # x, y, w, h als Bruchteil 0..1
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
    print(f"OK: {stem}: {len(manifest)} Abbildung(en) -> {fig_dir}/")
    return len(manifest)


def _default_out_dir(in_path):
    """quellen/<Thema>/<name>.pdf -> aufbereitet/<Thema>/"""
    norm = in_path.replace(os.sep, "/")
    if norm.startswith("quellen/"):
        return os.path.join("aufbereitet", os.path.dirname(norm[len("quellen/"):]))
    return "aufbereitet"


def _pdfs_in(folder):
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(".pdf"))


def main(argv):
    ap = argparse.ArgumentParser(description="Abbildungen aus PDF schneiden (-> PNG-Crops).")
    ap.add_argument("input", help="PDF-Datei oder Ordner (z. B. quellen/SWT/)")
    ap.add_argument("--zoom", type=float, default=2.0, help="Render-Zoom der Crops (Default 2.0)")
    ap.add_argument("--min-area", type=float, default=0.03,
                    help="kleinste Figur als Flaechenanteil der Seite (Default 0.03)")
    ap.add_argument("--max-area", type=float, default=0.92,
                    help="groesste Figur (Default 0.92; darueber = Seitenhintergrund)")
    ap.add_argument("--min-side", type=float, default=0.06,
                    help="kleinste Kantenlaenge als Bruchteil (Default 0.06)")
    args = ap.parse_args(argv)

    inputs = _pdfs_in(args.input) if os.path.isdir(args.input) else [args.input]
    if not inputs:
        print(f"Keine PDFs in {args.input}", file=sys.stderr)
        return 1
    total = 0
    for p in inputs:
        if not p.lower().endswith(".pdf") or not os.path.isfile(p):
            print(f"Uebersprungen (keine PDF-Datei): {p}", file=sys.stderr)
            continue
        total += extract(p, _default_out_dir(p), args.zoom,
                         args.min_area, args.max_area, args.min_side)
    print(f"Fertig: {total} Abbildung(en) ueber alle Dateien.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
