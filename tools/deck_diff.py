#!/usr/bin/env python3
"""Diffs two versions of a deck: which notes are added / removed / changed?

    python3 tools/deck_diff.py <old> <new> [--strict]

<old> and <new> are each: a .cards.json, an .apkg (decoded via apkg_to_cards,
GUIDs preserved), or a folder (all *.cards.json inside, recursive).

Built for the GUID-preserving rework workflow (CLAUDE.md, "Changing an
existing/learned deck"): before pushing a rebuilt deck, verify that it
contains exactly the intended changes —

  + added    note only in <new>
  - removed  note only in <old>   (lingers in Anki unless push --prune)
  ~ changed  same GUID, fields differ (a push OVERWRITES those fields)
  > moved    same GUID, deck name changed

Cloze safety: the card ords hang off the {{cN::…}} numbers (ord = N-1).
If a rework changes the SET OF NUMBERS of a note, Anki drops/creates cards
and the learning progress of those cards is lost -> loud [WARN]. Changed
answer text inside a kept cN updates the content but keeps the scheduling.

Notes without an explicit `guid` (hand-written cards.json) are matched by
content (type + text/front) as a fallback; the summary says how many.

Informational by default (exit 0). --strict: exit 1 if any cloze-number
warning — use it as a gate before `push`.

Runs on the host, stdlib only (zstd needed only when reading modern .apkg).
"""
import argparse
import glob
import json
import os
import re
import sys

_CLOZE_RE = re.compile(r"\{\{c(\d+)::(.+?)\}\}", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
# Everything content-bearing; 'guid' is the identity, not content.
_COMPARE_KEYS = ("type", "front", "back", "text", "extra", "explanation",
                 "source", "reverse", "tags", "image", "mode", "header",
                 "regions")


def _apkg_to_cards():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import apkg_to_cards
    return apkg_to_cards


def _snippet(card, limit=60):
    text = card.get("front") or card.get("text") or card.get("image") or ""
    text = " ".join(_TAG_RE.sub(" ", text).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _iter_decks(path, warnings):
    """Yields (deck name, cards list) from a .cards.json / .apkg / folder."""
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "**", "*.cards.json"),
                                 recursive=True))
        if not files:
            raise SystemExit(f"No *.cards.json under {path}")
        for f in files:
            yield from _iter_decks(f, warnings)
    elif path.endswith(".apkg"):
        atc = _apkg_to_cards()
        con, tmp = atc.open_collection(path)
        try:
            by_deck, decode_warnings = atc.extract(con)
        finally:
            con.close()
            os.unlink(tmp)
        # e.g. skipped occlusion notes — those are invisible to the diff.
        warnings.extend(f"{os.path.basename(path)}: {w}" for w in decode_warnings)
        yield from sorted(by_deck.items())
    elif path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        yield data.get("deck", "?"), data.get("cards") or []
    else:
        raise SystemExit(f"Unsupported input (expected .cards.json/.apkg/folder): {path}")


def _load(path, warnings):
    """-> ({key: (deck, card)}, number of guid-less fallback matches)."""
    notes, no_guid = {}, 0
    for deck, cards in _iter_decks(path, warnings):
        for card in cards:
            guid = card.get("guid")
            if guid:
                key = ("guid", guid)
            else:
                no_guid += 1
                basis = card.get("text") or card.get("front") or card.get("image") \
                    or json.dumps(card, sort_keys=True)
                key = ("content", card.get("type", "basic"), basis)
            if key in notes:
                warnings.append(f"{path}: duplicate note key {key[1]!r} — "
                                "only the last one is compared.")
            notes[key] = (deck, card)
    return notes, no_guid


def _cloze_numbers(text):
    return {int(m.group(1)) for m in _CLOZE_RE.finditer(text or "")}


def _cloze_tokens(text):
    """{(N, answer)} — answer without an optional ::hint suffix."""
    out = set()
    for m in _CLOZE_RE.finditer(text or ""):
        answer = (m.group(2).split("::", 1) + [""])[0]
        out.add((int(m.group(1)), answer))
    return out


def _changed_fields(a, b):
    return [k for k in _COMPARE_KEYS if a.get(k) != b.get(k)]


def diff(old_path, new_path, strict=False):
    warnings = []
    old, old_no_guid = _load(old_path, warnings)
    new, new_no_guid = _load(new_path, warnings)

    added = sorted(set(new) - set(old), key=str)
    removed = sorted(set(old) - set(new), key=str)
    common = sorted(set(old) & set(new), key=str)

    changed, moved, cloze_breaks = [], [], []
    for key in common:
        old_deck, old_card = old[key]
        new_deck, new_card = new[key]
        fields = _changed_fields(old_card, new_card)
        if fields:
            changed.append((key, new_deck, new_card, fields))
        if old_deck != new_deck:
            moved.append((key, old_deck, new_deck, new_card))
        if "text" in fields:
            old_nums, new_nums = (_cloze_numbers(old_card.get("text")),
                                  _cloze_numbers(new_card.get("text")))
            if old_nums != new_nums:
                cloze_breaks.append((key, new_card, old_nums, new_nums))

    unchanged = len(common) - len(changed)
    print(f"== Deck diff: {old_path} -> {new_path} ==")
    print(f"  notes: {len(old)} old / {len(new)} new — "
          f"{len(added)} added, {len(removed)} removed, "
          f"{len(changed)} changed, {unchanged} unchanged")
    if old_no_guid or new_no_guid:
        print(f"  (matched by content, no guid: {old_no_guid} old / {new_no_guid} new)")

    for key in added:
        deck, card = new[key]
        print(f"  + added   [{deck}] {_snippet(card)!r}")
    for key in removed:
        deck, card = old[key]
        print(f"  - removed [{deck}] {_snippet(card)!r}  "
              "(stays in Anki unless push --prune)")
    for key, deck, card, fields in changed:
        print(f"  ~ changed [{deck}] {_snippet(card)!r}: {', '.join(fields)}")
        if "text" in fields and key not in {k for k, *_ in cloze_breaks}:
            old_t, new_t = (_cloze_tokens(old[key][1].get("text")),
                            _cloze_tokens(card.get("text")))
            if old_t != new_t:
                print("      (cloze answers changed — ords/scheduling kept, "
                      "fields update on push)")
    for key, old_deck, new_deck, card in moved:
        print(f"  > moved   {_snippet(card)!r}: {old_deck} -> {new_deck}")
    for key, card, old_nums, new_nums in cloze_breaks:
        fmt = lambda nums: ",".join(f"c{n}" for n in sorted(nums)) or "-"
        print(f"  [WARN] {_snippet(card)!r}: cloze numbers {fmt(old_nums)} -> "
              f"{fmt(new_nums)} — Anki drops/creates those cards, their "
              "learning progress is LOST.")
    for w in warnings:
        print(f"  [note] {w}")

    if not (added or removed or changed or moved):
        print("  identical ✓")
    print(f"-> {len(cloze_breaks)} cloze warning(s), {len(warnings)} note(s).")
    return 1 if (strict and cloze_breaks) else 0


def main(argv):
    ap = argparse.ArgumentParser(
        description="Diff two deck versions (cards.json/.apkg/folder) by note GUID.")
    ap.add_argument("old", help="old state: .cards.json, .apkg or folder")
    ap.add_argument("new", help="new state: .cards.json, .apkg or folder")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on cloze-number warnings (scheduling breaks)")
    args = ap.parse_args(argv)
    return diff(args.old, args.new, args.strict)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
