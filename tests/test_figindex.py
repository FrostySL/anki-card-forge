"""Tests fuer tools/figindex.py (Abbildungs-Index aus Captions)."""
import unittest

from _tools import load

fi = load("figindex")


class TestScan(unittest.TestCase):
    def test_caption_indexed_and_marker_annotated(self):
        md = "<!-- S. 5 -->\n\nText. Abb. 1: Klassendiagramm\n\n<!-- S. 6 -->\n\nnix\n"
        new, idx = fi.scan(md)
        self.assertEqual(len(idx), 1)
        num, page, cap = idx[0]
        self.assertEqual(num, 1)
        self.assertEqual(page, 5)
        self.assertIn("Klassendiagramm", cap)
        self.assertIn("· 1 Abb.", new)          # Per-Seite-Marker bekommt die Bildzahl

    def test_idempotent(self):
        md = "<!-- S. 5 -->\n\nAbb. 1: X\n"
        once, _ = fi.scan(md)
        twice, _ = fi.scan(once)
        self.assertEqual(once, twice)            # "· 1 Abb." wird nicht verdoppelt

    def test_directory_entry_ignored(self):
        # Caption mit langer Punktfuehrung = Abbildungsverzeichnis-Eintrag, kein echtes Bild
        md = "<!-- S. 2 -->\n\nAbb. 1: Etwas ........... 7\n"
        _, idx = fi.scan(md)
        self.assertEqual(idx, [])

    def test_ocr_flag_preserved(self):
        md = "<!-- S. 3 (OCR) -->\n\nAbb. 1: Schema\n"
        new, _ = fi.scan(md)
        self.assertIn("(OCR)", new)
        self.assertIn("· 1 Abb.", new)


class TestCleanCaption(unittest.TestCase):
    def test_strips_dotted_leader(self):
        self.assertEqual(fi._clean_caption("Titel ......... 12"), "Titel")

    def test_strips_markup(self):
        self.assertEqual(fi._clean_caption("**Wichtig** <br> Rest"), "Wichtig")


if __name__ == "__main__":
    unittest.main()
