"""Tests for tools/apkg_to_cards.py (.apkg back into cards.json, GUIDs preserved).

Pure stdlib (sqlite3 + zipfile) — builds mini collections of both schema variants:
- Legacy  (collection.anki2, models/decks as JSON in 'col')  as genanki writes it.
- Modern  (dedicated tables notetypes/decks)  as an UNcompressed 'collection.anki21'
  (the tool detects the SQLite signature and unpacks nothing) -> no zstd needed.

The note type names ("Anki-Karten ...") are this project's real, intentionally
unchanged legacy names — see the note in tools/build_deck.py.
"""
import json
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

try:
    import zstandard
except ImportError:
    zstandard = None

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

    def test_more_stays_byte_identical_in_its_own_field(self):
        more = ' \n<details><summary>Source</summary><img src="figure.png"></details>\n '
        for model in ("Anki-Karten Type-in", "Anki-Karten Basic+Reversed"):
            with self.subTest(model=model):
                warns = []
                card = a2c._note_to_card(model, ["Question", "Answer", more], "g", "", 1, warns)
                self.assertEqual(card["back"], "Answer")
                self.assertEqual(card["more"], more)
                self.assertNotIn("explanation", card)
                self.assertNotIn("source", card)
                self.assertEqual(warns, [])


class TestRawNotes(unittest.TestCase):
    def test_more_build_decode_rebuild_preserves_all_note_fields_and_card_ordinals(self):
        try:
            builder = load("build_deck")
        except ModuleNotFoundError as error:
            if error.name == "genanki":
                self.skipTest("genanki is not installed")
            raise

        def snapshot(package):
            con, tmp = a2c.open_collection(package)
            try:
                return sorted((note["guid"], note["model_id"], note["fields"], note["ords"])
                              for note in a2c.raw_notes(con))
            finally:
                con.close()
                os.unlink(tmp)

        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            source = Path(directory) / "source.cards.json"
            source.write_text(json.dumps({"deck": "Roundtrip::More", "cards": [
                {"type": "typein", "guid": "typein-more", "front": "Question", "back": "Answer",
                 "more": " \n<p>Raw feedback</p>\n ", "explanation": "Why", "source": "Page 1"},
                {"type": "basic", "reverse": True, "guid": "reverse-more", "front": "Term", "back": "Definition",
                 "more": " \n<p>Reverse feedback</p>\n ", "explanation": "Context", "source": "Page 2"}
            ]}), encoding="utf-8")
            original = Path(directory) / "original.apkg"
            builder.build(str(source), str(original))
            con, tmp = a2c.open_collection(original)
            try:
                decoded, warnings = a2c.extract(con, require_complete=True)
            finally:
                con.close()
                os.unlink(tmp)
            self.assertEqual(warnings, [])
            output = a2c.write_cards_json(decoded, Path(directory) / "decoded")[0][0]
            rebuilt = Path(directory) / "rebuilt.apkg"
            builder.build(output, str(rebuilt))
            self.assertEqual(snapshot(original), snapshot(rebuilt))

    def test_every_foreign_field_and_card_assignment_is_preserved(self):
        with sqlite3.connect(":memory:") as con:
            _legacy(con)
            model = {"name": "Foreign IO", "flds": [
                {"name": "More", "ord": 2}, {"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}]}
            con.execute("UPDATE col SET models=?", (json.dumps({"123": model}),))
            con.execute("UPDATE notes SET flds=? WHERE id=1", ("F\x1fB\x1fraw more",))
            con.execute("ALTER TABLE cards ADD COLUMN ord INTEGER DEFAULT 0")
            con.execute("INSERT INTO cards VALUES (1,1,1)")
            note = a2c.raw_notes(con)[0]
        self.assertEqual(note["guid"], "guidA")
        self.assertEqual(note["model_id"], 123)
        self.assertEqual(note["fields"], ["F", "B", "raw more"])
        self.assertEqual(note["field_names"], ["Front", "Back", "More"])
        self.assertEqual(note["decks"], ["Default", "T::Sub"])
        self.assertEqual(note["ords"], [0, 1])

    def test_modern_field_names_use_note_type_and_ordinal(self):
        with sqlite3.connect(":memory:") as con:
            _modern(con)
            con.execute("CREATE TABLE fields (ntid INTEGER, ord INTEGER, name TEXT)")
            con.executemany("INSERT INTO fields VALUES (?,?,?)", [(123, 1, "Back"), (123, 0, "Front")])
            note = a2c.raw_notes(con)[0]
        self.assertEqual(note["schema"], "modern")
        self.assertEqual(note["field_names"], ["Front", "Back"])
        self.assertEqual(note["fields"], ["F", "B"])

    def test_modern_export_with_anki_collated_without_rowid_fields(self):
        def modern(con):
            _modern(con)
            con.create_collation("unicase", lambda left, right: (left > right) - (left < right))
            con.execute("CREATE TABLE fields (ntid INTEGER NOT NULL, ord INTEGER NOT NULL, "
                        "name TEXT NOT NULL COLLATE unicase, PRIMARY KEY (ntid, ord)) WITHOUT ROWID")
            con.execute("CREATE UNIQUE INDEX fields_name ON fields (ntid, name)")
            con.executemany("INSERT INTO fields VALUES (?,?,?)", [(123, 1, "Back"), (123, 0, "Front")])
        package = _make_apkg("collection.anki21", _sqlite_bytes(modern))
        con, tmp = a2c.open_collection(package)
        try:
            note = a2c.raw_notes(con)[0]
            self.assertEqual(note["field_names"], ["Front", "Back"])
            self.assertEqual(note["fields"], ["F", "B"])
        finally:
            con.close()
            os.unlink(tmp)
            os.unlink(package)

    def test_cli_rejects_partial_occlusion_decode_before_writing(self):
        def mixed(con):
            _legacy(con)
            models = json.loads(con.execute("SELECT models FROM col").fetchone()[0])
            models["456"]["name"] = "Anki-Karten Image Occlusion"
            con.execute("UPDATE col SET models=?", (json.dumps(models),))
        apkg = _make_apkg("collection.anki2", _sqlite_bytes(mixed))
        try:
            with tempfile.TemporaryDirectory() as directory:
                out = os.path.join(directory, "decoded")
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                    a2c.main([apkg, "--out", out])
                self.assertEqual(result.exception.code, 1)
                self.assertFalse(os.path.exists(out))
            con, tmp = a2c.open_collection(apkg)
            try:
                cards, warnings = a2c.extract(con)  # Mirrors may still index the supported subset.
                self.assertEqual(sum(map(len, cards.values())), 1)
                self.assertTrue(any("Incomplete decode" in warning for warning in warnings))
                self.assertEqual(len(a2c.raw_notes(con)), 2)
            finally:
                con.close()
                os.unlink(tmp)
        finally:
            os.unlink(apkg)


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

    def test_more_media_is_rewritten(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                media = os.path.abspath(os.path.join("decoded", "media", "figure.png"))
                cards = {"T": [{"type": "typein", "more": '<img src="figure.png">'}]}
                self.assertEqual(a2c.rewrite_media_srcs(cards, {"figure.png": media}), 1)
                self.assertEqual(cards["T"][0]["more"], '<img src="decoded/media/figure.png">')
            finally:
                os.chdir(cwd)

    def test_valid_image_attribute_variants_are_rewritten_without_changing_other_html(self):
        variants = ('<img src = "figure.png">', "<img SRC='figure.png'>", '<img src=figure.png>')
        for markup in variants:
            with self.subTest(markup=markup):
                cards = {"T": [{"back": "before " + markup + " after"}]}
                self.assertEqual(a2c.rewrite_media_srcs(cards, {"figure.png": "decoded/media/figure.png"}), 1)
                self.assertIn("decoded/media/figure.png", cards["T"][0]["back"])
                self.assertTrue(cards["T"][0]["back"].startswith("before "))
                self.assertTrue(cards["T"][0]["back"].endswith(" after"))

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

    @unittest.skipUnless(zstandard or shutil.which("zstd"), "zstandard and zstd CLI unavailable")
    def test_zstd_compressed_media_file_is_decompressed(self):
        if zstandard:
            blob = zstandard.ZstdCompressor().compress(b"PNGDATA")
        else:
            blob = subprocess.run(["zstd", "-c"], input=b"PNGDATA",
                                  capture_output=True, check=True).stdout
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
