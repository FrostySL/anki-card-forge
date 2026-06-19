#!/usr/bin/env python3
"""Validiert eine .apkg in einer ECHTEN Anki-Collection (offizielles Backend, ohne
GUI): importieren + jede Karte mit Ankis Template-Engine rendern. Das ist die
staerkste Pruefung – sie nutzt dieselbe Engine wie die Desktop-App, nicht unsere
Vorschau-Emulation.

Aufruf (ueber tools/validate.sh im Validate-Container):
    ./tools/validate.sh decks/skript.apkg

Exit-Code 0 = alles ok; 1 = Importfehler, Render-Fehler oder leere Karten.
"""
import os
import re
import sys
import tempfile

from anki.collection import Collection


def _import(col, apkg):
    """Moderne Import-API bevorzugt, Fallback auf Legacy-Importer."""
    try:
        from anki.collection import ImportAnkiPackageRequest

        col.import_anki_package(ImportAnkiPackageRequest(package_path=apkg))
        return "moderne API"
    except Exception as e_new:
        import anki.lang

        try:
            anki.lang.set_lang("en")
        except TypeError:
            anki.lang.set_lang("en", "")
        from anki.importing.apkg import AnkiPackageImporter

        AnkiPackageImporter(col, apkg).run()
        return f"legacy (moderne API: {e_new})"


def validate(apkg):
    if not os.path.exists(apkg):
        print(f"FEHLER: Datei nicht gefunden: {apkg}")
        return 1

    tmp = tempfile.mkdtemp()
    col = Collection(os.path.join(tmp, "col.anki2"))
    try:
        how = _import(col, apkg)
        print(f"Import OK ({how}): {apkg}")

        decks = [d.name for d in col.decks.all_names_and_ids() if d.name != "Default"]
        card_ids = list(col.find_cards(""))
        print("Decks:", sorted(decks))
        print(f"Notizen: {len(col.find_notes(''))}  Karten: {len(card_ids)}")

        strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
        errors = empty = 0
        by_type = {}
        for cid in card_ids:
            c = col.get_card(cid)
            try:
                out = c.render_output()
                q, a = out.question_text, out.answer_text
            except Exception as e:
                errors += 1
                print("  RENDER-FEHLER:", e)
                continue
            if not strip(q) or not strip(a):
                empty += 1
                print(f"  LEERE KARTE: {c.note_type()['name']} (cid {cid})")
            by_type.setdefault(c.note_type()["name"], []).append((q, a))

        print("\nKarten pro Notiztyp:")
        for nt, cards in sorted(by_type.items()):
            print(f"  {nt}: {len(cards)}")

        print("\n=== Je ein Render-Beispiel pro Notiztyp (Anki-Engine) ===")
        for nt, cards in sorted(by_type.items()):
            q, a = cards[0]
            print(f"--- {nt} ---")
            print("  FRONT:", strip(q)[:140])
            print("  BACK :", strip(a)[:180])

        ok = errors == 0 and empty == 0
        print(f"\n-> {errors} Render-Fehler, {empty} leere Karten — "
              + ("OK ✓" if ok else "PROBLEME ✗"))
        return 0 if ok else 1
    finally:
        col.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(validate(sys.argv[1]))
