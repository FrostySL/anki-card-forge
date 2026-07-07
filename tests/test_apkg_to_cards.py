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
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

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


def _legacy_img(con):
    """Legacy schema with one basic note that references an image twice."""
    con.execute("CREATE TABLE col (models TEXT, decks TEXT)")
    con.execute("INSERT INTO col VALUES (?,?)", (
        json.dumps({"123": {"name": "Anki-Karten Basic"}}),
        json.dumps({"99": {"name": "T"}})))
    con.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER, flds TEXT, tags TEXT)")
    con.execute("INSERT INTO notes VALUES (1,'g',123,?,'')",
                (f'Q <img src="fig.png">{SEP}A <img src="fig.png"> end',))
    con.execute("CREATE TABLE cards (nid INTEGER, did INTEGER)")
    con.execute("INSERT INTO cards VALUES (1,99)")


def _pb_media(names):
    """Minimal MediaEntries protobuf: repeated entry (field 1), each with a
    name (field 1, string) plus a size varint (field 2) to exercise skipping."""
    out = b""
    for name in names:
        nb = name.encode("utf-8")
        entry = b"\x0a" + bytes([len(nb)]) + nb + b"\x10\x2a"  # name + size=42
        out += b"\x0a" + bytes([len(entry)]) + entry
    return out


class TestMedia(unittest.TestCase):
    """Media extraction — without it, the rework roundtrip (export ->
    cards.json -> build) dies for every deck that contains images."""

    def test_legacy_media_json_unpacked_and_srcs_rewritten(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                with zipfile.ZipFile("in.apkg", "w") as z:
                    z.writestr("collection.anki2", _sqlite_bytes(_legacy_img))
                    z.writestr("media", json.dumps({"0": "fig.png"}))
                    z.writestr("0", b"\x89PNGdata")
                media = a2c.extract_media("in.apkg", "out")
                self.assertEqual(list(media), ["fig.png"])
                with open(media["fig.png"], "rb") as fh:
                    self.assertEqual(fh.read(), b"\x89PNGdata")

                con, tmp = a2c.open_collection("in.apkg")
                try:
                    by_deck, _ = a2c.extract(con)
                finally:
                    con.close()
                    os.unlink(tmp)
                n = a2c.rewrite_media_srcs(by_deck, media)
                self.assertEqual(n, 2)  # front + back occurrence
                card = by_deck["T"][0]
                self.assertIn('src="out/media/fig.png"', card["front"])
                self.assertIn('src="out/media/fig.png"', card["back"])
            finally:
                os.chdir(cwd)

    def test_modern_protobuf_media_map(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.apkg")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("collection.anki21", _sqlite_bytes(_modern))
                z.writestr("media", _pb_media(["a.png", "b.jpg"]))
                z.writestr("0", b"A")
                z.writestr("1", b"B")
            media = a2c.extract_media(path, os.path.join(d, "out"))
            self.assertEqual(sorted(media), ["a.png", "b.jpg"])
            with open(media["b.jpg"], "rb") as fh:
                self.assertEqual(fh.read(), b"B")

    @unittest.skipUnless(shutil.which("zstd"), "zstd CLI not available")
    def test_zstd_compressed_media_file_is_decompressed(self):
        blob = subprocess.run(["zstd", "-c"], input=b"PNGDATA",
                              capture_output=True).stdout
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.apkg")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("collection.anki2", _sqlite_bytes(_legacy))
                z.writestr("media", json.dumps({"0": "x.png"}))
                z.writestr("0", blob)
            media = a2c.extract_media(path, os.path.join(d, "out"))
            with open(media["x.png"], "rb") as fh:
                self.assertEqual(fh.read(), b"PNGDATA")

    def test_media_name_cannot_escape_outdir(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.apkg")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("collection.anki2", _sqlite_bytes(_legacy))
                z.writestr("media", json.dumps({"0": "../../evil.png"}))
                z.writestr("0", b"x")
            media = a2c.extract_media(path, os.path.join(d, "out"))
            self.assertEqual(list(media), ["evil.png"])
            self.assertTrue(media["evil.png"].startswith(
                os.path.join(d, "out", "media")))

    def test_no_media_member_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.apkg")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("collection.anki2", _sqlite_bytes(_legacy))
            self.assertEqual(a2c.extract_media(path, os.path.join(d, "out")), {})
            self.assertFalse(os.path.exists(os.path.join(d, "out", "media")))


class TestDecompressErrors(unittest.TestCase):
    def test_missing_zstandard_and_cli_gives_clear_error(self):
        # Neither the python module nor the CLI available -> explanatory
        # RuntimeError instead of a raw FileNotFoundError traceback.
        with mock.patch.dict(sys.modules, {"zstandard": None}), \
                mock.patch.object(a2c.subprocess, "run",
                                  side_effect=FileNotFoundError("no zstd")):
            with self.assertRaisesRegex(RuntimeError, "zstd"):
                a2c._decompress_zstd(b"\x28\xb5\x2f\xfd\x00")


class TestWriteCardsJson(unittest.TestCase):
    def test_colliding_deck_names_get_suffixes(self):
        # 'A::B' and 'A B' both sanitize to 'A_B' — the second file must not
        # silently overwrite the first.
        with tempfile.TemporaryDirectory() as d:
            files = a2c.write_cards_json(
                {"A::B": [{"guid": "g1"}], "A B": [{"guid": "g2"}]}, d)
            names = sorted(os.path.basename(p) for p, _, _ in files)
            self.assertEqual(names, ["A_B.cards.json", "A_B_2.cards.json"])


if __name__ == "__main__":
    unittest.main()
