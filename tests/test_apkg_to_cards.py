"""Tests for tools/apkg_to_cards.py (.apkg back into cards.json, GUIDs preserved).

Pure stdlib (sqlite3 + zipfile) — builds mini collections of both schema variants:
- Legacy  (collection.anki2, models/decks as JSON in 'col')  as genanki writes it.
- Modern  (dedicated tables notetypes/decks)  as an UNcompressed 'collection.anki21'
  (the tool detects the SQLite signature and unpacks nothing) -> no zstd needed.

The note type names ("Anki-Karten ...") are this project's real, intentionally
unchanged legacy names — see the note in tools/build_deck.py.
"""
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile

from _tools import load

a2c = load("apkg_to_cards")
SEP = "\x1f"


def _sqlite_bytes(build):
    """build(con) fills a DB; returns the file bytes."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        con = sqlite3.connect(path)
        build(con)
        con.commit()
        con.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def _make_apkg(member, db_bytes):
    """Writes an .apkg with exactly one collection member and returns the path."""
    fd, path = tempfile.mkstemp(suffix=".apkg")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(member, db_bytes)
        z.writestr("media", "{}")
    return path


def _legacy(con):
    con.execute("CREATE TABLE col (models TEXT, decks TEXT)")
    models = {"123": {"name": "Anki-Karten Basic"}, "456": {"name": "Anki-Karten Cloze"}}
    decks = {"1": {"name": "Default"}, "99": {"name": "T::Sub"}}
    con.execute("INSERT INTO col VALUES (?,?)", (json.dumps(models), json.dumps(decks)))
    con.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER, flds TEXT, tags TEXT)")
    con.execute("INSERT INTO notes VALUES (1,'guidA',123,?,' t1 t2 ')", (f"Front1{SEP}Back1",))
    con.execute("INSERT INTO notes VALUES (2,'guidB',456,?,'')", (f"The {{{{c1::X}}}}.{SEP}Extra",))
    con.execute("CREATE TABLE cards (nid INTEGER, did INTEGER)")
    con.executemany("INSERT INTO cards VALUES (?,?)", [(1, 99), (2, 99)])


def _modern(con):
    con.execute("CREATE TABLE notetypes (id INTEGER, name TEXT)")
    con.execute("INSERT INTO notetypes VALUES (123,'Anki-Karten Basic')")
    con.execute("CREATE TABLE decks (id INTEGER, name TEXT)")
    con.execute("INSERT INTO decks VALUES (1,'Default')")
    con.execute("INSERT INTO decks VALUES (99,?)", (f"T{SEP}Sub",))  # \x1f -> '::'
    con.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER, flds TEXT, tags TEXT)")
    con.execute("INSERT INTO notes VALUES (1,'g1',123,?,'')", (f"F{SEP}B",))
    con.execute("CREATE TABLE cards (nid INTEGER, did INTEGER)")
    con.execute("INSERT INTO cards VALUES (1,99)")


class TestExtract(unittest.TestCase):
    def _extract(self, apkg):
        con, tmp = a2c.open_collection(apkg)
        try:
            return a2c.extract(con)
        finally:
            con.close()
            os.unlink(tmp)

    def test_legacy_roundtrip(self):
        apkg = _make_apkg("collection.anki2", _sqlite_bytes(_legacy))
        try:
            by_deck, warnings = self._extract(apkg)
        finally:
            os.unlink(apkg)
        self.assertEqual(set(by_deck), {"T::Sub"})
        cards = {c["guid"]: c for c in by_deck["T::Sub"]}
        self.assertEqual(set(cards), {"guidA", "guidB"})
        self.assertEqual(cards["guidA"], {
            "guid": "guidA", "type": "basic", "front": "Front1", "back": "Back1",
            "tags": ["t1", "t2"]})
        self.assertEqual(cards["guidB"]["type"], "cloze")
        self.assertEqual(cards["guidB"]["text"], "The {{c1::X}}.")
        self.assertEqual(cards["guidB"]["extra"], "Extra")
        self.assertEqual(warnings, [])

    def test_modern_uncompressed_and_deck_separator(self):
        # Modern schema as an UNcompressed collection.anki21 (SQLite signature).
        apkg = _make_apkg("collection.anki21", _sqlite_bytes(_modern))
        try:
            by_deck, _ = self._extract(apkg)
        finally:
            os.unlink(apkg)
        self.assertEqual(set(by_deck), {"T::Sub"})  # \x1f became '::'
        self.assertEqual(by_deck["T::Sub"][0]["guid"], "g1")


class TestNoteMapping(unittest.TestCase):
    def test_cloze_detected_by_content_in_unknown_type(self):
        warns = []
        card = a2c._note_to_card("Foreign note type", ["The {{c1::A}}.", "x"], "g", "", 7, warns)
        self.assertEqual(card["type"], "cloze")

    def test_unknown_type_falls_back_to_basic_with_warning(self):
        warns = []
        card = a2c._note_to_card("My Type", ["F", "B"], "g", "tag", 7, warns)
        self.assertEqual(card["type"], "basic")
        self.assertEqual(card["front"], "F")
        self.assertEqual(card["tags"], ["tag"])
        self.assertTrue(warns)

    def test_occlusion_skipped(self):
        warns = []
        card = a2c._note_to_card("Anki-Karten Image Occlusion", ["a", "b"], "g", "", 7, warns)
        self.assertIsNone(card)
        self.assertTrue(warns)

    def test_typein_and_reverse(self):
        self.assertEqual(a2c._note_to_card("Anki-Karten Type-in", ["F", "B"], "g", "", 1, [])["type"], "typein")
        rev = a2c._note_to_card("Anki-Karten Basic+Reversed", ["F", "B", ""], "g", "", 1, [])
        self.assertEqual(rev["type"], "basic")
        self.assertTrue(rev["reverse"])


if __name__ == "__main__":
    unittest.main()
