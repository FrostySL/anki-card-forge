"""Tests for tools/deck_diff.py (GUID diff of two deck versions)."""
import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing, redirect_stdout
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
    def package(self, directory, name, notes, *, mid=123, model="Anki-Karten Image Occlusion",
                field_names=("Front", "Back"), ords=(0,)):
        db = Path(directory) / (name + ".db")
        with closing(sqlite3.connect(db)) as con, con:
            con.execute("CREATE TABLE col (models TEXT, decks TEXT)")
            con.execute("INSERT INTO col VALUES (?,?)", (
                json.dumps({str(mid): {"name": model, "flds": [
                    {"name": value, "ord": ordinal} for ordinal, value in enumerate(field_names)]}}),
                json.dumps({"9": {"name": "T"}})))
            con.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER, flds TEXT, tags TEXT)")
            con.execute("CREATE TABLE cards (nid INTEGER, did INTEGER, ord INTEGER)")
            for nid, (guid, fields) in enumerate(notes, 1):
                con.execute("INSERT INTO notes VALUES (?,?,?,?,?)", (nid, guid, mid, "\x1f".join(fields), ""))
                con.executemany("INSERT INTO cards VALUES (?,?,?)", [(nid, 9, ordinal) for ordinal in ords])
        package = Path(directory) / (name + ".apkg")
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("collection.anki2", db.read_bytes())
            archive.writestr("media", "{}")
        return str(package)

    def test_occlusion_note_removed_is_reported_without_changing_removal_policy(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.package(d, "old", [("io", ["masked", "label"])])
            new = self.package(d, "new", [])
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 0)  # Removal may be intentional; strict guards scheduling changes.
        self.assertIn("1 old / 0 new", output)
        self.assertIn("1 removed", output)
        self.assertNotIn("identical", output)

    def test_occlusion_field_changes_are_compared(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.package(d, "old", [("io", ["masked", "old label"])])
            new = self.package(d, "new", [("io", ["masked", "new label"])])
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 0)
        self.assertIn("1 changed", output)
        self.assertIn("back", output)

    def test_unknown_third_field_is_not_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            args = {"model": "Foreign", "field_names": ("F", "B", "Hidden")}
            old = self.package(d, "old", [("g", ["Q", "A", "old"])], **args)
            new = self.package(d, "new", [("g", ["Q", "A", "new"])], **args)
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 0)
        self.assertIn("1 changed", output)
        self.assertIn("fields", output)

    def test_model_field_layout_and_card_ordinals_are_strict_failures(self):
        cases = ({"mid": 456}, {"field_names": ("Back", "Front")}, {"ords": (0, 1)})
        for overrides in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as d:
                old = self.package(d, "old", [("g", ["Q", "A"])])
                new = self.package(d, "new", [("g", ["Q", "A"])], **overrides)
                rc, output = _run(old, new, strict=True)
                self.assertEqual(rc, 1)
                self.assertIn("[WARN]", output)

    def test_raw_cloze_in_later_field_is_checked(self):
        with tempfile.TemporaryDirectory() as d:
            args = {"model": "Foreign cloze", "field_names": ("Title", "Text")}
            old = self.package(d, "old", [("g", ["Q", "{{c1::A}} {{c2::B}}"] )], **args)
            new = self.package(d, "new", [("g", ["Q", "{{c1::A}} B"] )], **args)
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 1)
        self.assertIn("c1,c2 -> c1", output)

    def test_changed_field_count_cannot_hide_behind_unchanged_model_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.package(d, "old", [("g", ["Q", "A"])])
            new = self.package(d, "new", [("g", ["Q", "A", "unexpected field"])])
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 1)
        self.assertIn("field_count", output)

    def test_unsupported_mixed_comparison_cannot_claim_identical(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.package(d, "old", [("g", ["Q", "A"])])
            new = _write(d, "new.cards.json", "T", [{"guid": "g", "type": "occlusion",
                          "front": "Q", "back": "A", "tags": []}])
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 1)
        self.assertIn("compare two .apkg files", output)
        self.assertNotIn("identical", output)

    def test_mixed_comparison_checks_numeric_model_field_order_and_ordinals(self):
        cases = (({"mid": 99}, "model_id"),
                 ({"field_names": ("Back", "Front")}, "field_names"),
                 ({"field_names": ()}, "field_names"),
                 ({"ords": (1,)}, "card ordinals"))
        for overrides, message in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as d:
                options = {"model": "Anki-Karten Basic", "mid": 1776014608, **overrides}
                old = self.package(d, "old", [("g", ["Q", "A"])], **options)
                new = _write(d, "new.cards.json", "T", [{"guid": "g", "type": "basic",
                              "front": "Q", "back": "A", "tags": []}])
                for first, second in ((old, new), (new, old)):
                    rc, output = _run(first, second, strict=True)
                    self.assertEqual(rc, 1)
                    self.assertIn(message, output)
                    self.assertNotIn("identical", output)

    def test_compatible_mixed_comparison_checks_sparse_cloze_and_reverse_ordinals(self):
        cases = [
            ("Anki-Karten Basic", ["Q", "A"], (0,), {"type": "basic", "front": "Q", "back": "A"}),
            ("Anki-Karten Type-in", ["Q", "A", "raw"], (0,),
             {"type": "typein", "front": "Q", "back": "A", "more": "raw"}),
            ("Anki-Karten Basic+Reversed", ["Q", "A", "raw"], (0, 1),
             {"type": "basic", "reverse": True, "front": "Q", "back": "A", "more": "raw"}),
            ("Anki-Karten Cloze", ["{{c1::A}} {{c3::B}}", ""], (0, 2),
             {"type": "cloze", "text": "{{c1::A}} {{c3::B}}", "extra": ""}),
        ]
        for model, fields, ords, card in cases:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as d:
                mid, names = dd._JSON_MODEL_LAYOUTS[model]
                old = self.package(d, "old", [("g", fields)], mid=mid, model=model,
                                   field_names=names, ords=ords)
                new = _write(d, "new.cards.json", "T", [{"guid": "g", "tags": [], **card}])
                rc, output = _run(old, new, strict=True)
                self.assertEqual(rc, 0, output)
                self.assertIn("identical", output)

    def test_duplicate_guid_makes_strict_comparison_ambiguous(self):
        with tempfile.TemporaryDirectory() as d:
            old = self.package(d, "old", [("g", ["Q", "A"]), ("g", ["Other", "A"])])
            new = self.package(d, "new", [("g", ["Other", "A"])])
            rc, output = _run(old, new, strict=True)
        self.assertEqual(rc, 1)
        self.assertIn("duplicate note key", output)
        self.assertNotIn("identical", output)

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
