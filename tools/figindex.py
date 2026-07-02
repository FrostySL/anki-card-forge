#!/usr/bin/env python3
"""Creates/updates a figure index for extracted Markdown files.

Pure stdlib (no PyMuPDF/Docker needed) — runs directly on the host over the
already generated extracted/<topic>/<name>.md. Called automatically by
tools/extract.sh after extraction, but can also run on its own.

Per <name>.md it:
  - scans each page for figure captions ("Fig. N: ..." / "Abb. N: ...") and
    omitted images,
  - writes extracted/<topic>/<name>.figures.md (list: Fig. N — p. P: title),
  - annotates the page markers with the figure count: "<!-- p. 21 · 2 fig. -->".

That makes it visible at a glance where images live when building cards. For
spatial/visual concepts, look at the real PDF page (Read tool, pages="N") or the
cropped figure and consider an occlusion/image card instead of missing the image.

Idempotent: existing "· N fig." (or legacy "· N Abb.") annotations are removed
before rewriting. Legacy German markers ("<!-- S. N -->", "(leer)") are accepted.

Usage:
  python3 tools/figindex.py extracted/SWT/        # whole topic folder (recursive)
  python3 tools/figindex.py extracted/SWT/12_MET_Software_Architecture_Metrics.md
"""
import os
import re
import sys

MARKER_RE = re.compile(r"<!--\s*(?:p|S)\.\s*(\d+)([^>]*?)-->")
CAPTION_RE = re.compile(r"(?:Fig|Figure|Abb|Abbildung)\.?\s*(\d+)\s*:\**\s*([^\n]*)")
OMITTED_RE = re.compile(r"intentionally omitted")


def _clean_caption(raw):
    """Turns a raw caption line into a concise title."""
    s = raw
    for cut in ("<br>", "**---", "----- End", "----- Start"):
        idx = s.find(cut)
        if idx != -1:
            s = s[:idx]
    s = re.split(r"\.{3,}", s, maxsplit=1)[0]  # cut the dotted leader of a list-of-figures entry
    s = s.replace("*", " ")
    s = re.sub(r"\s+", " ", s).strip(" —–-:")
    return s


def _flag(suffix):
    """Keeps only (OCR)/(empty)/(leer) from the old marker suffix; old figure
    annotations are dropped."""
    m = re.search(r"\((OCR|empty|leer)\)", suffix)
    return f" ({m.group(1)})" if m else ""


def scan(md_text):
    """-> (annotated_text, index). index: sorted list of (num, page, caption)."""
    markers = list(MARKER_RE.finditer(md_text))
    index = {}            # num -> (page, caption); longest caption wins
    out = []
    last = 0
    for i, m in enumerate(markers):
        out.append(md_text[last:m.start()])          # page content before stays untouched
        page = int(m.group(1))
        flag = _flag(m.group(2))
        seg = md_text[m.end():(markers[i + 1].start() if i + 1 < len(markers) else len(md_text))]
        figs = {}
        for cm in CAPTION_RE.finditer(seg):
            if re.search(r"\.{4,}", cm.group(0)):   # list-of-figures entry (dotted leader) -> not a real image
                continue
            num, cap = int(cm.group(1)), _clean_caption(cm.group(2))
            if num not in figs or len(cap) > len(figs[num]):
                figs[num] = cap
        k = len(figs) + len(OMITTED_RE.findall(seg))
        out.append(f"<!-- p. {page}{flag}" + (f" · {k} fig." if k else "") + " -->")
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
            f"# Figures: {os.path.basename(md_path)}",
            "",
            f"{len(idx)} figures (p. = position in the extracted .md). "
            'To view an image: Read tool on the original PDF with pages="<p>".',
            "",
        ]
        lines += [f"- **Fig. {num}** — p. {page}: {cap or '(untitled)'}" for num, page, cap in idx]
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
        print("Usage: figindex.py <extracted/topic/ | file.md>", file=sys.stderr)
        return 1
    total = 0
    for p in argv:
        for md in _md_files(p):
            n = process(md)
            total += n
            print(f"{md}: {n} figures")
    print(f"Done: {total} figures across all files.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
