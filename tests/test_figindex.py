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
        self.assertEqual(num, "1")              # numbers are strings now ("3.2" possible)
        self.assertEqual(page, 5)
        self.assertIn("Class diagram", cap)
        self.assertIn("· 1 fig.", new)          # per-page marker gets the figure count

    def test_sectioned_number_and_dash_separator(self):
        # "Figure 3.2:" (sectioned number) and "Abbildung 4 – …" (en-dash, no colon)
        # were both missed by the old colon-and-integer-only regex.
        md = ("<!-- p. 1 -->\n\nFigure 3.2: The pipeline\n\n"
              "<!-- p. 2 -->\n\nAbbildung 4 – Übersicht\n")
        _, idx = fi.scan(md)
        nums = {num: cap for num, _p, cap in idx}
        self.assertIn("3.2", nums)
        self.assertIn("The pipeline", nums["3.2"])
        self.assertIn("4", nums)
        self.assertIn("Übersicht", nums["4"])

    def test_same_number_on_two_pages_kept(self):
        # Chapter-wise numbering: "Fig. 1" on two pages must yield TWO entries
        # (the old index keyed by number only, so the second one vanished).
        md = ("<!-- p. 7 -->\n\nFig. 1: Alpha\n\n"
              "<!-- p. 9 -->\n\nFig. 1: Beta\n")
        _, idx = fi.scan(md)
        pages = sorted(p for _n, p, _c in idx)
        self.assertEqual(pages, [7, 9])
        self.assertEqual(len(idx), 2)

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


class TestExtractedDirsFor(unittest.TestCase):
    def test_file_maps_to_topic_dir(self):
        self.assertEqual(fi.extracted_dirs_for(["sources/Biology/x.pdf"]),
                         ["extracted/Biology"])

    def test_folder_maps_to_topic_dir(self):
        self.assertEqual(fi.extracted_dirs_for(["sources/Biology/"]),
                         ["extracted/Biology"])

    def test_flags_and_values_and_foreign_paths_skipped(self):
        self.assertEqual(
            fi.extracted_dirs_for(["sources/Bio/x.pdf", "--lang", "eng+deu",
                                   "-j", "8", "notes/y.pdf"]),
            ["extracted/Bio"])

    def test_deduplicated(self):
        self.assertEqual(
            fi.extracted_dirs_for(["sources/T/a.pdf", "sources/T/b.pdf", "sources/T/"]),
            ["extracted/T"])

    def test_empty_when_nothing_under_sources(self):
        self.assertEqual(fi.extracted_dirs_for(["--lang", "eng"]), [])


class TestForSourcesMain(unittest.TestCase):
    def test_indexes_only_the_input_topic(self):
        import io
        import os
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as root:
            for topic in ("Bio", "Math"):
                os.makedirs(os.path.join(root, "extracted", topic))
                with open(os.path.join(root, "extracted", topic, "x.md"), "w",
                          encoding="utf-8") as f:
                    f.write("<!-- p. 1 -->\n\nFig. 1: Something\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                fi.main(["--for-sources", root, "sources/Bio/x.pdf"])
            out = buf.getvalue()
        self.assertIn(os.path.join("Bio", "x.md"), out)
        self.assertNotIn(os.path.join("Math", "x.md"), out)  # Math left untouched


class TestCleanCaption(unittest.TestCase):
    def test_strips_dotted_leader(self):
        self.assertEqual(fi._clean_caption("Title ......... 12"), "Title")

    def test_strips_markup(self):
        self.assertEqual(fi._clean_caption("**Important** <br> rest"), "Important")


if __name__ == "__main__":
    unittest.main()
