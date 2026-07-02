"""Tests for tools/figindex.py (figure index from captions)."""
import unittest

from _tools import load

fi = load("figindex")


class TestScan(unittest.TestCase):
    def test_caption_indexed_and_marker_annotated(self):
        md = "<!-- p. 5 -->\n\nText. Fig. 1: Class diagram\n\n<!-- p. 6 -->\n\nnothing\n"
        new, idx = fi.scan(md)
        self.assertEqual(len(idx), 1)
        num, page, cap = idx[0]
        self.assertEqual(num, 1)
        self.assertEqual(page, 5)
        self.assertIn("Class diagram", cap)
        self.assertIn("· 1 fig.", new)          # per-page marker gets the figure count

    def test_idempotent(self):
        md = "<!-- p. 5 -->\n\nFig. 1: X\n"
        once, _ = fi.scan(md)
        twice, _ = fi.scan(once)
        self.assertEqual(once, twice)            # "· 1 fig." is not duplicated

    def test_directory_entry_ignored(self):
        # Caption with a long dotted leader = list-of-figures entry, not a real image
        md = "<!-- p. 2 -->\n\nFig. 1: Something ........... 7\n"
        _, idx = fi.scan(md)
        self.assertEqual(idx, [])

    def test_ocr_flag_preserved(self):
        md = "<!-- p. 3 (OCR) -->\n\nFig. 1: Schema\n"
        new, _ = fi.scan(md)
        self.assertIn("(OCR)", new)
        self.assertIn("· 1 fig.", new)

    def test_legacy_german_markers_and_captions(self):
        # Old extracts: "<!-- S. N -->" markers and "Abb. N:" captions still work
        # and get normalized to the English marker format.
        md = "<!-- S. 5 (OCR) -->\n\nAbb. 1: Schema\n"
        new, idx = fi.scan(md)
        self.assertEqual(len(idx), 1)
        self.assertEqual(idx[0][1], 5)
        self.assertIn("<!-- p. 5 (OCR) · 1 fig. -->", new)


class TestCleanCaption(unittest.TestCase):
    def test_strips_dotted_leader(self):
        self.assertEqual(fi._clean_caption("Title ......... 12"), "Title")

    def test_strips_markup(self):
        self.assertEqual(fi._clean_caption("**Important** <br> rest"), "Important")


if __name__ == "__main__":
    unittest.main()
