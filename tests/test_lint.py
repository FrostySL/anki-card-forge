"""Tests for tools/lint_cards.py (structure/content check of a cards.json)."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _tools import load

lint = load("lint_cards")


def _run(data, extra_files=None):
    """Writes a cards.json (plus optional companion files) and lints -> (rc, stdout).

    Changes into the temp directory so relative image paths resolve there (as in
    real use, where the CWD is the project root)."""
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        for name, content in (extra_files or {}).items():
            (Path(d) / name).write_bytes(content)
        p = Path(d) / "c.cards.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        os.chdir(d)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = lint.lint("c.cards.json")
            return rc, buf.getvalue()
        finally:
            os.chdir(cwd)


class TestLint(unittest.TestCase):
    def test_valid_deck_passes(self):
        rc, _ = _run({"deck": "D", "cards": [{"type": "basic", "front": "Q", "back": "A"}]})
        self.assertEqual(rc, 0)

    def test_basic_without_back_errors(self):
        rc, out = _run({"deck": "D", "cards": [{"type": "basic", "front": "Q"}]})
        self.assertEqual(rc, 1)
        self.assertIn("without 'back'", out)

    def test_missing_deck_errors(self):
        rc, out = _run({"cards": [{"type": "basic", "front": "Q", "back": "A"}]})
        self.assertEqual(rc, 1)
        self.assertIn("'deck'", out)

    def test_cloze_without_gap_errors(self):
        rc, out = _run({"deck": "D", "cards": [{"type": "cloze", "text": "no deletion here"}]})
        self.assertEqual(rc, 1)
        self.assertIn("no deletion", out)

    def test_unknown_type_errors(self):
        rc, out = _run({"deck": "D", "cards": [{"type": "weird", "front": "Q"}]})
        self.assertEqual(rc, 1)
        self.assertIn("unknown type", out)

    def test_field_img_missing_errors(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": 'A<br><img src="nope.png">'}
        ]})
        self.assertEqual(rc, 1)
        self.assertIn("<img> not found: nope.png", out)

    def test_field_img_present_passes(self):
        rc, _ = _run(
            {"deck": "D", "cards": [
                {"type": "basic", "front": "Q", "back": 'A<br><img src="fig.png">'}
            ]},
            extra_files={"fig.png": b"\x89PNG"},
        )
        self.assertEqual(rc, 0)

    def test_field_img_remote_and_data_uris_ignored(self):
        rc, _ = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q",
             "back": 'A<img src="https://x.example/a.png"><img src="data:image/png;base64,AA==">'}
        ]})
        self.assertEqual(rc, 0)

    def test_occlusion_missing_image_errors(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "occlusion", "regions": [{"label": "x", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}]}]})
        self.assertEqual(rc, 1)
        self.assertIn("without 'image'", out)

    def test_occlusion_coord_out_of_range_only_warns(self):
        # Image exists (dummy), so only the coordinate WARNING remains, no image ERROR.
        rc, out = _run(
            {"deck": "D", "cards": [{"type": "occlusion", "image": "i.png",
                "regions": [{"label": "x", "x": 1.5, "y": 0.1, "w": 0.1, "h": 0.1}]}]},
            extra_files={"i.png": b"x"},
        )
        self.assertEqual(rc, 0)               # a warning does not block
        self.assertIn("outside 0..1", out)

    def test_duplicate_fronts_warn(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A"},
            {"type": "basic", "front": "Q", "back": "B"}]})
        self.assertEqual(rc, 0)
        self.assertIn("duplicate question", out)

    def test_unknown_card_field_warns(self):
        # A typo field ("explaination") would silently vanish at build time.
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A", "explaination": "lost"}]})
        self.assertEqual(rc, 0)
        self.assertIn("unknown field 'explaination'", out)

    def test_reverse_on_cloze_warns(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "cloze", "text": "a {{c1::b}}", "reverse": True}]})
        self.assertEqual(rc, 0)
        self.assertIn("'reverse' only works on type 'basic'", out)

    def test_unknown_deck_field_warns(self):
        rc, out = _run({"deck": "D", "Deck": "typo", "cards": [
            {"type": "basic", "front": "Q", "back": "A"}]})
        self.assertEqual(rc, 0)
        self.assertIn("unknown field 'Deck' at deck level", out)

    def test_unknown_region_field_warns(self):
        rc, out = _run(
            {"deck": "D", "cards": [{"type": "occlusion", "image": "i.png",
                "regions": [{"label": "x", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1, "lable": "y"}]}]},
            extra_files={"i.png": b"x"},
        )
        self.assertEqual(rc, 0)
        self.assertIn("unknown field 'lable'", out)

    def test_cloze_c0_errors(self):
        # genanki/Anki build no card for c0 — the note would silently have zero cards.
        rc, out = _run({"deck": "D", "cards": [{"type": "cloze", "text": "a {{c0::b}}"}]})
        self.assertEqual(rc, 1)
        self.assertIn("c0", out)

    def test_cloze_c1_still_passes(self):
        rc, _ = _run({"deck": "D", "cards": [{"type": "cloze", "text": "a {{c1::b}}"}]})
        self.assertEqual(rc, 0)

    def test_tags_as_string_errors(self):
        # genanki would iterate the string: "bio" -> tags b, i, o.
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A", "tags": "bio"}]})
        self.assertEqual(rc, 1)
        self.assertIn("list of strings", out)

    def test_non_object_card_reported_not_crash(self):
        rc, out = _run({"deck": "D", "cards": ["oops"]})
        self.assertEqual(rc, 1)
        self.assertIn("JSON object", out)

    def test_non_string_field_reported_not_crash(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": 42, "back": "A"}]})
        self.assertEqual(rc, 1)
        self.assertIn("must be a string", out)

    def test_invalid_shapes_reported_without_crashing(self):
        malformed = [[], {"deck": 7, "cards": []}, {"deck": "D", "cards": {}},
                     {"deck": "D", "cards": None}]
        for data in malformed:
            with self.subTest(data=data):
                rc, out = _run(data)
                self.assertEqual(rc, 1)
                self.assertIn("[ERROR]", out)

    def test_optional_field_types_are_checked(self):
        for key, value in (("explanation", []), ("source", 42), ("extra", None),
                           ("header", {}), ("more", []), ("reverse", "false"),
                           ("type", [])):
            with self.subTest(key=key):
                rc, out = _run({"deck": "D", "cards": [
                    {"front": "Q", "back": "A", key: value}]})
                self.assertEqual(rc, 1)
                self.assertIn(f"'{key}'", out)

    def test_optional_raw_more_is_accepted_and_its_images_checked(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "typein", "front": "Q", "back": "A", "more": " raw HTML "}]})
        self.assertEqual(rc, 0)
        self.assertIn("all good", out)
        rc, out = _run({"deck": "D", "cards": [
            {"type": "typein", "front": "Q", "back": "A",
             "more": '<img src = "missing.png">'}]})
        self.assertEqual(rc, 1)
        self.assertIn("missing.png", out)

    def test_image_attributes_with_spaces_or_unquoted_values_are_checked(self):
        for markup in ('<img src = "missing.png">', '<img src=missing.png>',
                       '<img data-src="ignore.png" src="missing.png">'):
            with self.subTest(markup=markup):
                rc, out = _run({"deck": "D", "cards": [{"front": "Q", "back": markup}]})
                self.assertEqual(rc, 1)
                self.assertIn("missing.png", out)
                self.assertNotIn("ignore.png", out)

    def test_region_types_reported_without_crashing(self):
        for regions in ({}, [{"label": 3, "x": .1, "y": .1, "w": .1, "h": .1}],
                        [{"label": "A", "x": True, "y": .1, "w": .1, "h": .1}],
                        [{"label": "A", "x": float("nan"), "y": .1, "w": .1, "h": .1}]):
            with self.subTest(regions=regions):
                rc, out = _run({"deck": "D", "cards": [
                    {"type": "occlusion", "image": "i.png", "regions": regions}]})
                self.assertEqual(rc, 1)
                self.assertIn("[ERROR]", out)

    def test_non_object_region_reported_not_crash(self):
        rc, out = _run(
            {"deck": "D", "cards": [{"type": "occlusion", "image": "i.png",
                                     "regions": ["oops"]}]},
            extra_files={"i.png": b"x"},
        )
        self.assertEqual(rc, 1)
        self.assertIn("region 0", out)

    def test_duplicate_guid_errors(self):
        # Two notes sharing a GUID -> Anki keeps one, the other's content is lost.
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q1", "back": "A1", "guid": "same"},
            {"type": "basic", "front": "Q2", "back": "A2", "guid": "same"}]})
        self.assertEqual(rc, 1)
        self.assertIn("duplicate guid", out)

    def test_distinct_guids_pass(self):
        rc, _ = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q1", "back": "A1", "guid": "g1"},
            {"type": "basic", "front": "Q2", "back": "A2", "guid": "g2"}]})
        self.assertEqual(rc, 0)

    def test_empty_guid_errors(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A", "guid": "  "}]})
        self.assertEqual(rc, 1)
        self.assertIn("non-empty string", out)

    def test_all_known_fields_pass_clean(self):
        # A card using every allowed field must NOT trigger any warning.
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A", "reverse": True,
             "explanation": "e", "source": "s", "tags": ["t"], "guid": "g"},
            {"type": "cloze", "text": "a {{c1::b}}", "extra": "x",
             "explanation": "e", "source": "s", "tags": ["t"]}]})
        self.assertEqual(rc, 0)
        self.assertIn("all good", out)


if __name__ == "__main__":
    unittest.main()
