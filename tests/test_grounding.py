"""Tests fuer tools/grounding_check.py – die fehleranfaelligste Heuristik.

Enthaelt Regressionstests fuer die zwei Bugs aus der Entwicklung:
  1. Substring- statt Token-Matching liess Halluzinationen durch.
  2. `_STOP` nutzte `_norm` vor dessen Definition -> Import-Crash. Allein das
     erfolgreiche `load("grounding_check")` deckt (2) ab.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _tools import load

g = load("grounding_check")


class TestTerms(unittest.TestCase):
    def test_acronyms_kept_stopwords_dropped(self):
        terms = g._terms("Das UML-Diagramm zeigt eine Klasse und Methoden")
        self.assertIn("uml", terms)        # Akronym (2 Grossbuchstaben)
        self.assertIn("diagramm", terms)
        self.assertIn("klasse", terms)
        self.assertNotIn("das", terms)     # zu kurz
        self.assertNotIn("eine", terms)    # Stoppwort
        self.assertNotIn("und", terms)

    def test_norm_umlaut_folding(self):
        self.assertEqual(g._norm("Köln"), "koeln")
        self.assertEqual(g._norm("Größe"), "groesse")


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.idx = g._index(
            "Ein Unit-Test prueft eine einzelne Komponente isoliert. Mitochondrium.")

    def test_prefix_tolerance(self):
        # Morphologie: Mitochondrien ~ Mitochondrium ueber gemeinsamen 6-Zeichen-Praefix
        self.assertTrue(g._found("mitochondrien", self.idx))

    def test_exact_token(self):
        self.assertTrue(g._found("komponente", self.idx))

    def test_absent_term(self):
        self.assertFalse(g._found("quaxomatron", self.idx))

    def test_coverage_fraction_and_missing(self):
        cover, missing = g._coverage({"komponente", "quaxomatron"}, self.idx)
        self.assertAlmostEqual(cover, 0.5)
        self.assertEqual(missing, ["quaxomatron"])

    def test_coverage_empty_terms(self):
        cover, missing = g._coverage(set(), self.idx)
        self.assertIsNone(cover)


class TestAnswerText(unittest.TestCase):
    def test_basic_uses_back(self):
        self.assertEqual(g._answer_text({"type": "basic", "back": "Hallo"}).strip(), "Hallo")

    def test_cloze_uses_deletions(self):
        t = g._answer_text({"type": "cloze", "text": "Die {{c1::Glykolyse}} und {{c2::ATP}}"})
        self.assertIn("Glykolyse", t)
        self.assertIn("ATP", t)

    def test_occlusion_uses_labels(self):
        t = g._answer_text({"type": "occlusion", "regions": [{"label": "Aorta"}, {"label": "Klappe"}]})
        self.assertIn("Aorta", t)
        self.assertIn("Klappe", t)


def _run_check(cards, source_text):
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "src.md"
        md.write_text(source_text, encoding="utf-8")
        cf = Path(d) / "x.cards.json"
        cf.write_text(json.dumps({"deck": "T", "cards": cards}), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = g.check(str(cf), source=str(md))
        return rc, buf.getvalue()


class TestCheckRegression(unittest.TestCase):
    def test_hallucination_is_flagged(self):
        rc, out = _run_check(
            [
                {"type": "basic", "front": "Was prueft ein Unit-Test?",
                 "back": "Eine einzelne Komponente isoliert."},
                {"type": "basic", "front": "Erfunden?",
                 "back": "Das Quaxomatron nach Flimmerblubb steuert die Zwirbeldynamik.",
                 "source": "S. 999"},
            ],
            "<!-- S. 1 -->\n\nEin Unit-Test prueft eine einzelne Komponente isoliert.\n",
        )
        self.assertEqual(rc, 1)                      # FEHLER -> Exit 1
        self.assertIn("Halluzination", out)
        self.assertIn("quaxomatron", out.lower())    # erfundene Begriffe gelistet
        self.assertIn("S. 999", out)                 # Phantom-Seite gemeldet

    def test_grounded_card_passes(self):
        rc, out = _run_check(
            [{"type": "cloze", "text": "Die {{c1::Glykolyse}} laeuft im {{c2::Zytoplasma}} ab."}],
            "<!-- S. 1 -->\n\nDie Glykolyse laeuft im Zytoplasma ab.\n",
        )
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
