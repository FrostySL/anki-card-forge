#!/usr/bin/env python3
"""Reads an Anki .apkg BACK into cards.json — one per deck — preserving the
note GUIDs. This lets you rework cards that have **already been learned/edited
in Anki** WITHOUT losing the learning progress.

    python3 tools/apkg_to_cards.py <export.apkg> [-o TARGET_DIR]

Workflow (see CLAUDE.md, section "Changing an existing deck without losing progress"):
  1. Export in Anki: File -> Export -> .apkg (with scheduling).
  2. Run this tool -> one cards.json per deck (fields = current state,
     `guid` preserved per card).
  3. Edit the cards.json (structure/HTML, see the `card-authoring` skill).
  4. Rebuild with tools/build.sh — build_deck picks up the `guid`, so the
     re-import in Anki UPDATES the note instead of duplicating it (progress kept).
  5. Import in Anki: "Update notes", do NOT reset scheduling.

Why this is needed: learning progress hangs off the note GUID. Without a
preserved GUID, genanki computes a new one for changed text -> duplicates,
progress gone.

Supports the modern export format (collection.anki21b, zstd-compressed; the real
data) and the legacy format (collection.anki2, as genanki writes it). Maps this
project's note types (the German display names are intentional legacy — renaming
them would disconnect existing decks):
  'Anki-Karten Basic'          -> basic
  'Anki-Karten Cloze'          -> cloze
  'Anki-Karten Type-in'        -> typein
  'Anki-Karten Basic+Reversed' -> basic + "reverse": true
Cloze is also detected via `{{c…::}}` in the first field. Occlusion notes CANNOT
be converted back to image/regions (warning, skipped). Foreign note types are
taken over best-effort as basic (warning).

IMPORTANT: the extracted fields already contain any "details & source" box baked
in (inside Back/Extra). When editing, do NOT set `explanation`/`source` on top
(double box) — either leave the box in the field or move it cleanly into
`explanation`/`source`.

Runs on the host (stdlib + zstd only) — NO Docker needed.
"""
import argparse
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

FIELD_SEP = "\x1f"
KNOWN = {
    "Anki-Karten Basic", "Anki-Karten Cloze", "Anki-Karten Type-in",
    "Anki-Karten Basic+Reversed", "Anki-Karten Image Occlusion",
}


def _decompress_zstd(data: bytes) -> bytes:
    """zstd frame -> raw bytes. Prefers python-zstandard, falls back to the zstd CLI."""
    try:
        import zstandard
    except ImportError:
        proc = subprocess.run(["zstd", "-dc"], input=data, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "Need python 'zstandard' OR the 'zstd' CLI to unpack "
                "collection.anki21b: " + proc.stderr.decode("utf-8", "replace")[:200]
            )
        return proc.stdout
    dctx = zstandard.ZstdDecompressor()
    try:
        return dctx.decompress(data)
    except zstandard.ZstdError:  # size not in the frame header -> stream
        return dctx.stream_reader(io.BytesIO(data)).read()


def open_collection(apkg_path):
    """Writes the REAL collection DB to a temp file and returns (connection, path)."""
    with zipfile.ZipFile(apkg_path) as z:
        names = set(z.namelist())
        if "collection.anki21b" in names:           # modern, zstd
            raw = _decompress_zstd(z.read("collection.anki21b"))
        elif "collection.anki21" in names:          # transitional format
            blob = z.read("collection.anki21")
            raw = blob if blob[:16] == b"SQLite format 3\x00" else _decompress_zstd(blob)
        elif "collection.anki2" in names:           # legacy (genanki)
            raw = z.read("collection.anki2")
        else:
            raise RuntimeError("No collection.* found in the .apkg.")
    tmp = tempfile.NamedTemporaryFile(suffix=".anki2", delete=False)
    tmp.write(raw)
    tmp.close()
    return sqlite3.connect(tmp.name), tmp.name


def _maps(con):
    """(notetype id->name, deck id->name, schema). Deck name separator -> '::'."""
    tabs = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "notetypes" in tabs:  # modern DB: dedicated tables
        ntype = dict(con.execute("SELECT id, name FROM notetypes"))
        decks = {d: n.replace(FIELD_SEP, "::") for d, n in con.execute("SELECT id, name FROM decks")}
        return ntype, decks, "modern"
    # Legacy: everything in col as JSON
    models, decks_json = con.execute("SELECT models, decks FROM col").fetchone()
    ntype = {int(mid): m["name"] for mid, m in json.loads(models).items()}
    decks = {int(did): d["name"].replace(FIELD_SEP, "::") for did, d in json.loads(decks_json).items()}
    return ntype, decks, "legacy"


def _note_to_card(model, fields, guid, tags, nid, warnings):
    """One DB note -> one cards.json entry (or None for occlusion)."""
    def f(i):
        return fields[i] if i < len(fields) else ""

    m = model.lower()
    card = {"guid": guid}
    if "occlusion" in m:
        warnings.append(f"nid {nid}: occlusion skipped (cannot be converted back to image/regions).")
        return None
    if "cloze" in m or "{{c" in f(0):
        card.update(type="cloze", text=f(0), extra=f(1))
    elif "type-in" in m or "typein" in m:
        card.update(type="typein", front=f(0), back=f(1))
    elif "reversed" in m or "reverse" in m:
        # The reversed model has [Front, Back, More]; append More (3rd field) to
        # Back so a possibly baked-in box is not lost.
        back = f(1) + (f(2) if f(2).strip() else "")
        card.update(type="basic", reverse=True, front=f(0), back=back)
        if f(2).strip():
            warnings.append(f"nid {nid}: reversed – 'More' field appended to Back (verify).")
    else:
        if model not in KNOWN:
            warnings.append(f"nid {nid}: unknown note type {model!r} -> taken over as basic.")
        card.update(type="basic", front=f(0), back=f(1))
    card["tags"] = tags.split()
    return card


def extract(con):
    """-> (dict deck name->[cards], warnings)."""
    ntype, decks, _schema = _maps(con)
    note_deck = {nid: decks.get(did, "Default")
                 for nid, did in con.execute("SELECT nid, MIN(did) FROM cards GROUP BY nid")}
    by_deck, warnings = {}, []
    for nid, guid, mid, flds, tags in con.execute("SELECT id, guid, mid, flds, tags FROM notes"):
        card = _note_to_card(ntype.get(mid, f"mid:{mid}"), flds.split(FIELD_SEP), guid, tags, nid, warnings)
        if card:
            by_deck.setdefault(note_deck.get(nid, "Default"), []).append(card)
    return by_deck, warnings


def write_cards_json(by_deck, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    for deck, cards in sorted(by_deck.items()):
        safe = re.sub(r"[^\w.+-]+", "_", deck).strip("_")
        path = os.path.join(outdir, safe + ".cards.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"deck": deck, "cards": cards}, fh, ensure_ascii=False, indent=1)
        files.append((path, deck, len(cards)))
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Anki .apkg back into cards.json (GUIDs preserved).")
    ap.add_argument("apkg", help="path to the .apkg (Anki export or built by us)")
    ap.add_argument("-o", "--out", help="target folder (default: <apkg>_cards/ next to it)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.apkg):
        ap.error(f"File not found: {args.apkg}")
    outdir = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.apkg)),
        re.sub(r"\.apkg$", "", os.path.basename(args.apkg)) + "_cards",
    )

    con, tmp = open_collection(args.apkg)
    try:
        by_deck, warnings = extract(con)
    finally:
        con.close()
        os.unlink(tmp)

    files = write_cards_json(by_deck, outdir)
    total = sum(n for _, _, n in files)
    print(f"== {os.path.basename(args.apkg)} -> {len(files)} cards.json ({total} notes) ==")
    for path, deck, n in files:
        print(f"  {n:3d}  {deck}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  -", w)
    print(f"\ncards.json in: {outdir}")
    quoted = " ".join(f'"{p}"' for p, _, _ in files)
    print("Rebuild (GUIDs/progress preserved), e.g.:")
    print(f'  ./tools/build.sh {quoted} "out.apkg"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
