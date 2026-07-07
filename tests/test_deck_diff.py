"""Tests for tools/deck_diff.py (GUID diff of two deck versions)."""
import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from _tools import load

dd = load("deck_diff")


def _write(d, name, deck, cards):
    p = Path(d) / name
    p.write_text(json.dumps({"deck": deck, "cards": cards}), encoding="utf-8")
    return str(p)


def _run(old, new, strict=False):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = dd.diff(old, new, strict=strict)
    return rc, buf.getvalue()


class TestDiff(unittest.TestCase):
    def test_identical_is_clean(self):
        cards = [{"guid": "g1", "type": "basic", "front": "Q", "back": "A"}]
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.cards.json", "T", cards)
            b = _write(d, "b.cards.json", "T", cards)
            rc, out = _run(a, b)
        self.assertEqual(rc, 0)
        self.assertIn("identical ✓", out)

    def test_added_removed_changed_moved(self):
        old = [
            {"guid": "g1", "type": "basic", "front": "Q1", "back": "A1"},
            {"guid": "g2", "type": "basic", "front": "Q2", "back": "A2"},
            {"guid": "g4", "type": "basic", "front": "Q4", "back": "A4"},
        ]
        new = [
            {"guid": "g1", "type": "basic", "front": "Q1", "back": "A1 improved"},
            {"guid": "g3", "type": "basic", "front": "Q3", "back": "A3"},
            {"guid": "g4", "type": "basic", "front": "Q4", "back": "A4"},
        ]
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.cards.json", "T", old)
            b = _write(d, "b.cards.json", "T::Moved", new)
            rc, out = _run(a, b)
        self.assertEqual(rc, 0)
        self.assertIn("+ added", out)
        self.assertIn("'Q3'", out)
        self.assertIn("- removed", out)
        self.assertIn("'Q2'", out)
        self.assertIn("~ changed", out)
        self.assertIn("back", out)
        self.assertIn("> moved", out)          # deck renamed T -> T::Moved
        self.assertIn("1 added, 1 removed, 1 changed", out)

    def test_cloze_number_change_warns_and_strict_fails(self):
        old = [{"guid": "g1", "type": "cloze", "text": "a {{c1::x}} b {{c2::y}}"}]
        new = [{"guid": "g1", "type": "cloze", "text": "a {{c1::x}} b y"}]
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.cards.json", "T", old)
            b = _write(d, "b.cards.json", "T", new)
            rc, out = _run(a, b, strict=True)
        self.assertEqual(rc, 1)                # --strict gate
        self.assertIn("[WARN]", out)
        self.assertIn("c1,c2 -> c1", out)
        self.assertIn("LOST", out)

    def test_cloze_answer_change_keeps_scheduling_note(self):
        old = [{"guid": "g1", "type": "cloze", "text": "a {{c1::x}}"}]
        new = [{"guid": "g1", "type": "cloze", "text": "a {{c1::better x}}"}]
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.cards.json", "T", old)
            b = _write(d, "b.cards.json", "T", new)
            rc, out = _run(a, b, strict=True)
        self.assertEqual(rc, 0)                # same cN set -> no strict failure
        self.assertIn("ords/scheduling kept", out)

    def test_guidless_cards_matched_by_content(self):
        old = [{"type": "basic", "front": "Q", "back": "A"}]
        new = [{"type": "basic", "front": "Q", "back": "A better"}]
        with tempfile.TemporaryDirectory() as d:
            a = _write(d, "a.cards.json", "T", old)
            b = _write(d, "b.cards.json", "T", new)
            rc, out = _run(a, b)
        self.assertEqual(rc, 0)
        self.assertIn("matched by content", out)
        self.assertIn("~ changed", out)        # same front -> recognized as change

    def test_folder_input_collects_recursively(self):
        cards = [{"guid": "g1", "type": "basic", "front": "Q", "back": "A"}]
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "olddir" / "nested"
            sub.mkdir(parents=True)
            _write(sub, "a.cards.json", "T", cards)
            b = _write(d, "b.cards.json", "T", cards)
            rc, out = _run(str(Path(d) / "olddir"), b)
        self.assertEqual(rc, 0)
        self.assertIn("identical ✓", out)


class TestApkgInput(unittest.TestCase):
    def test_reads_legacy_apkg(self):
        # Mini legacy .apkg (like genanki writes) vs. an edited cards.json.
        def build(con):
            con.execute("CREATE TABLE col (models TEXT, decks TEXT)")
            con.execute("INSERT INTO col VALUES (?,?)", (
                json.dumps({"1": {"name": "Anki-Karten Basic"}}),
                json.dumps({"9": {"name": "T"}})))
            con.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER,"
                        " flds TEXT, tags TEXT)")
            con.execute("INSERT INTO notes VALUES (1,'g1',1,?, '')",
                        ("Q\x1fA",))
            con.execute("CREATE TABLE cards (nid INTEGER, did INTEGER)")
            con.execute("INSERT INTO cards VALUES (1,9)")

        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "col.db"
            con = sqlite3.connect(db)
            build(con)
            con.commit()
            con.close()
            apkg = Path(d) / "old.apkg"
            with zipfile.ZipFile(apkg, "w") as z:
                z.writestr("collection.anki2", db.read_bytes())
                z.writestr("media", "{}")
            b = _write(d, "b.cards.json", "T",
                       [{"guid": "g1", "type": "basic", "front": "Q",
                         "back": "A new"}])
            rc, out = _run(str(apkg), b)
        self.assertEqual(rc, 0)
        self.assertIn("~ changed", out)
        self.assertIn("back", out)


if __name__ == "__main__":
    unittest.main()
