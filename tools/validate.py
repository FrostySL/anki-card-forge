#!/usr/bin/env python3
"""Validates an .apkg in a REAL Anki collection (official backend, no GUI):
import it + render every card with Anki's template engine. This is the strongest
check — it uses the same engine as the desktop app, not our preview emulation.

Usage (via tools/validate.sh inside the validate container):
    ./tools/validate.sh decks/script.apkg

Exit code 0 = all good; 1 = import error, render errors, or empty cards.
"""
import os
import re
import sys
import tempfile

from anki.collection import Collection


def _import(col, apkg):
    """Prefer the modern import API, fall back to the legacy importer."""
    try:
        from anki.collection import ImportAnkiPackageRequest

        col.import_anki_package(ImportAnkiPackageRequest(package_path=apkg))
        return "modern API"
    except Exception as e_new:
        import anki.lang

        try:
            anki.lang.set_lang("en")
        except TypeError:
            anki.lang.set_lang("en", "")
        from anki.importing.apkg import AnkiPackageImporter

        AnkiPackageImporter(col, apkg).run()
        return f"legacy (modern API: {e_new})"


def validate(apkg):
    if not os.path.exists(apkg):
        print(f"ERROR: file not found: {apkg}")
        return 1

    tmp = tempfile.mkdtemp()
    col = Collection(os.path.join(tmp, "col.anki2"))
    try:
        how = _import(col, apkg)
        print(f"Import OK ({how}): {apkg}")

        decks = [d.name for d in col.decks.all_names_and_ids() if d.name != "Default"]
        card_ids = list(col.find_cards(""))
        print("Decks:", sorted(decks))
        print(f"Notes: {len(col.find_notes(''))}  Cards: {len(card_ids)}")

        strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
        # An image or audio IS content: an occlusion front without the optional
        # header, or a picture-only side, must not count as an empty card.
        has_content = lambda s: bool(strip(s)) or "<img" in s.lower() or "[sound:" in s.lower()
        errors = empty = 0
        by_type = {}
        for cid in card_ids:
            c = col.get_card(cid)
            try:
                out = c.render_output()
                q, a = out.question_text, out.answer_text
            except Exception as e:
                errors += 1
                print("  RENDER ERROR:", e)
                continue
            if not has_content(q) or not has_content(a):
                empty += 1
                print(f"  EMPTY CARD: {c.note_type()['name']} (cid {cid})")
            by_type.setdefault(c.note_type()["name"], []).append((q, a))

        print("\nCards per note type:")
        for nt, cards in sorted(by_type.items()):
            print(f"  {nt}: {len(cards)}")

        print("\n=== One render sample per note type (Anki engine) ===")
        for nt, cards in sorted(by_type.items()):
            q, a = cards[0]
            print(f"--- {nt} ---")
            print("  FRONT:", strip(q)[:140])
            print("  BACK :", strip(a)[:180])

        ok = errors == 0 and empty == 0
        print(f"\n-> {errors} render errors, {empty} empty cards — "
              + ("OK ✓" if ok else "PROBLEMS ✗"))
        return 0 if ok else 1
    finally:
        col.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(validate(sys.argv[1]))
