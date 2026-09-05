#!/usr/bin/env python3
"""Reads an Anki .apkg BACK into cards.json — one per deck — preserving the
note GUIDs. This lets you rework cards that have **already been learned/edited
in Anki** WITHOUT losing the learning progress.

    python3 tools/apkg_to_cards.py <export.apkg> [-o TARGET_DIR]

Workflow (see AGENTS.md, section "Changing an existing/learned deck"):
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
be converted back to image/regions; conversion aborts before writing partial
JSON. Foreign note types are
taken over best-effort as basic (warning).

IMPORTANT: the extracted fields already contain any "details & source" box baked
in (inside Back/Extra). When editing, do NOT set `explanation`/`source` on top
(double box) — either leave the box in the field or move it cleanly into
`explanation`/`source`.

Media in the package (images) is unpacked to <outdir>/media/ and the
`<img src>` attributes are rewritten to those paths — the rebuild then embeds
them again (without this, rebuilding an exported image deck dies on the bare
Anki file names).

Runs on the host (stdlib + zstd only) — NO Docker needed.
"""
import argparse
from _filenames import unique_stems, unique_media_names
from _card_media import rewrite_local_images
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
        try:
            proc = subprocess.run(["zstd", "-dc"], input=data, capture_output=True)
        except FileNotFoundError:
            raise RuntimeError(
                "Need python 'zstandard' OR the 'zstd' CLI to unpack "
                "collection.anki21b — neither is available (e.g. `apt install zstd`)."
            ) from None
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
    con = sqlite3.connect(tmp.name)
    # Modern Anki schemas declare this application collation, including on
    # WITHOUT ROWID tables. SQLite needs it registered even for a full scan.
    # Readers below do not filter/order by those text columns; all note fields
    # remain untouched and numeric field ordinals are sorted in Python.
    con.create_collation("unicase", lambda left, right:
                         (left.casefold() > right.casefold()) - (left.casefold() < right.casefold()))
    return con, tmp.name


_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def _read_varint(buf, pos):
    """Protobuf varint at `pos` -> (value, new pos)."""
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def _pb_strings(raw, want_field):
    """Length-delimited payloads of `want_field` in one protobuf message.
    Enough protobuf to read Anki's MediaEntries without a dependency."""
    out, pos = [], 0
    while pos < len(raw):
        tag, pos = _read_varint(raw, pos)
        field, wire = tag >> 3, tag & 7
        if wire == 2:  # length-delimited
            ln, pos = _read_varint(raw, pos)
            if field == want_field:
                out.append(raw[pos:pos + ln])
            pos += ln
        elif wire == 0:  # varint
            _, pos = _read_varint(raw, pos)
        elif wire == 5:  # 32-bit
            pos += 4
        elif wire == 1:  # 64-bit
            pos += 8
        else:  # unknown wire type: stop, keep what we have
            break
    return out


def _media_map(z):
    """{zip member name: original file name} from the .apkg's `media` entry.

    Legacy format: `media` is plain JSON {"0": "name.png", ...}.
    Modern format (collection.anki21b): `media` is a zstd-compressed protobuf
    (MediaEntries: repeated entry, whose field 1 is the name); list index i
    corresponds to zip member "i".
    """
    if "media" not in z.namelist():
        return {}
    raw = z.read("media")
    if raw[:4] == _ZSTD_MAGIC:
        raw = _decompress_zstd(raw)
    if not raw:
        return {}
    if raw[:1] == b"{":
        return dict(json.loads(raw.decode("utf-8")))
    names = [_pb_strings(entry, 1) for entry in _pb_strings(raw, 1)]
    return {str(i): n[0].decode("utf-8") for i, n in enumerate(names) if n}


def extract_media(apkg_path, outdir):
    """Unpacks the .apkg's media files to <outdir>/media/ and returns
    {original file name: written path}. Modern exports store each media file
    zstd-compressed — detected per file via the frame magic, so legacy (raw)
    files take the same path. No media in the package -> nothing is written."""
    out = {}
    media_dir = os.path.join(outdir, "media")
    with zipfile.ZipFile(apkg_path) as z:
        members = set(z.namelist())
        entries = sorted(_media_map(z).items())
        bases = [name.replace("\\", "/").rsplit("/", 1)[-1]
                 for member, name in entries if member in members]
        if len(bases) != len(set(bases)):
            raise ValueError("Media entries have identical base names; refusing to overwrite decoded files.")
        filenames = unique_media_names(sorted({name.replace("\\", "/").rsplit("/", 1)[-1]
                                               for _, name in entries}))
        for member, name in entries:
            base = name.replace("\\", "/").rsplit("/", 1)[-1]
            if not base or member not in members:
                continue
            data = z.read(member)
            if data[:4] == _ZSTD_MAGIC:
                data = _decompress_zstd(data)
            os.makedirs(media_dir, exist_ok=True)
            path = os.path.join(media_dir, filenames[base])
            with open(path, "wb") as fh:
                fh.write(data)
            out[base] = path
    return out


def rewrite_media_srcs(by_deck, media_paths):
    """Points <img src="X"> in the extracted fields at the unpacked media/
    copies (relative path, the form build_deck embeds again). Without this,
    the rebuild of an exported deck with images dies on the bare Anki file
    names. Unknown srcs (http/data or not in the package) stay untouched.
    -> number of rewritten srcs."""
    if not media_paths:
        return 0
    count = 0

    def repl(source):
        nonlocal count
        target = media_paths.get(source.replace("\\", "/").rsplit("/", 1)[-1])
        if not target:
            return source
        count += 1
        return os.path.relpath(target).replace(os.sep, "/")

    for cards in by_deck.values():
        for card in cards:
            for key in ("front", "back", "text", "extra", "more"):
                val = card.get(key)
                if isinstance(val, str) and "<img" in val.lower():
                    card[key] = rewrite_local_images(val, repl)
    return count


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
        card.update(type="typein", front=f(0), back=f(1), more=f(2))
    elif "reversed" in m or "reverse" in m:
        # More is a separate field: putting it into Back changes the reverse
        # question and rebuilding would clear the original More field.
        card.update(type="basic", reverse=True, front=f(0), back=f(1), more=f(2))
    else:
        if model not in KNOWN:
            warnings.append(f"nid {nid}: unknown note type {model!r} -> taken over as basic.")
        card.update(type="basic", front=f(0), back=f(1))
    card["tags"] = tags.split()
    return card


def raw_notes(con):
    """Read every note without converting or dropping any field/note type.

    Numeric note/card IDs and scheduling are deliberately not identities for a
    package comparison. Deck memberships and card ordinals remain available so
    callers can detect changes that affect existing cards. Missing field names
    or ordinals stay explicit, rather than being guessed for malformed exports.
    """
    ntype, decks, schema = _maps(con)
    field_names = {}
    if schema == "modern":
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "fields" in tables:
            # Modern exports may index field names with Anki-only collations.
            # Let SQLite scan the rows and sort the portable numeric keys here.
            for mid, _ord, name in sorted(con.execute("SELECT ntid, ord, name FROM fields"),
                                          key=lambda row: (row[0], row[1])):
                field_names.setdefault(mid, []).append(name)
    else:
        models = json.loads(con.execute("SELECT models FROM col").fetchone()[0])
        for mid, model in models.items():
            field_names[int(mid)] = [field["name"] for field in sorted(
                model.get("flds", []), key=lambda field: field.get("ord", 0))]
    columns = {row[1] for row in con.execute("PRAGMA table_info(cards)")}
    ord_column = "ord" if "ord" in columns else "NULL"
    memberships, ordinals = {}, {}
    for nid, did, ordinal in con.execute(f"SELECT nid, did, {ord_column} FROM cards"):
        memberships.setdefault(nid, set()).add(decks.get(did, f"did:{did}"))
        if ordinal is not None:
            ordinals.setdefault(nid, []).append(ordinal)
    notes = []
    for nid, guid, mid, flds, tags in con.execute("SELECT id, guid, mid, flds, tags FROM notes ORDER BY id"):
        notes.append({"id": nid, "guid": guid, "model_id": mid,
                      "model": ntype.get(mid, f"mid:{mid}"), "schema": schema,
                      "field_names": field_names.get(mid, []), "fields": flds.split(FIELD_SEP),
                      "tags": tags.split(), "decks": sorted(memberships.get(nid, {"Default"})),
                      "ords": sorted(ordinals.get(nid, [])) if "ord" in columns else None})
    return notes


def extract(con, *, require_complete=False):
    """-> (dict deck name->[cards], warnings)."""
    by_deck, warnings = {}, []
    incomplete = []
    for note in raw_notes(con):
        nid, model, fields = note["id"], note["model"], note["fields"]
        expected = 3 if model in {"Anki-Karten Type-in", "Anki-Karten Basic+Reversed"} else 2
        if model in KNOWN and len(fields) != expected:
            incomplete.append(f"nid {nid}: {model!r} has {len(fields)} fields; expected {expected}.")
            continue
        if len(note["decks"]) != 1:
            incomplete.append(f"nid {nid}: cards belong to several decks; cards.json cannot preserve this assignment.")
            continue
        card = _note_to_card(model, fields, note["guid"], " ".join(note["tags"]), nid, warnings)
        if card:
            by_deck.setdefault(note["decks"][0], []).append(card)
        else:
            incomplete.append(f"nid {nid}: {model!r} cannot be converted to image/regions.")
    if incomplete and require_complete:
        raise RuntimeError("Incomplete rework decode refused; no cards.json was written. "
                           "Keep the original .apkg and edit unsupported notes in Anki.\n- "
                           + "\n- ".join(incomplete))
    warnings.extend("Incomplete decode: " + message for message in incomplete)
    return by_deck, warnings


def write_cards_json(by_deck, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    names = unique_stems(sorted(by_deck))
    for deck, cards in sorted(by_deck.items()):
        path = os.path.join(outdir, names[deck] + ".cards.json")
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
        try:
            by_deck, warnings = extract(con, require_complete=True)
        except RuntimeError as error:
            ap.exit(1, f"Decode error: {error}\n")
    finally:
        con.close()
        os.unlink(tmp)

    media_paths = extract_media(args.apkg, outdir)
    rewritten = rewrite_media_srcs(by_deck, media_paths)
    files = write_cards_json(by_deck, outdir)
    total = sum(n for _, _, n in files)
    print(f"== {os.path.basename(args.apkg)} -> {len(files)} cards.json ({total} notes) ==")
    for path, deck, n in files:
        print(f"  {n:3d}  {deck}")
    if media_paths:
        print(f"Media: {len(media_paths)} file(s) -> {os.path.join(outdir, 'media')}/"
              f" ({rewritten} <img> src rewritten)")
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  -", w)
    print(f"\ncards.json in: {outdir}")
    quoted = " ".join(f'"{p}"' for p, _, _ in files)
    print("Rebuild compatible note types with preserved GUIDs, then verify with diff --strict:")
    starter = r".\forge.cmd build" if os.name == "nt" else "./tools/build.sh"
    print(f'  {starter} {quoted} "out.apkg"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
