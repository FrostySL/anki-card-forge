"""Tests for tools/grounding_check.py — the most error-prone heuristic.

Contains regression tests for the two bugs from development:
  1. Substring matching (instead of token matching) let hallucinations through.
  2. `_STOP` used `_norm` before its definition -> import crash. The successful
     `load("grounding_check")` alone covers (2).
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
        terms = g._terms("The UML diagram shows a class and its methods")
        self.assertIn("uml", terms)        # acronym (2 capitals)
        self.assertIn("diagram", terms)
        self.assertIn("class", terms)
        self.assertNotIn("the", terms)     # too short + stopword
        self.assertNotIn("and", terms)

    def test_norm_umlaut_folding(self):
        # Umlaut folding keeps German sources matchable (Koeln ~ Köln).
        self.assertEqual(g._norm("Köln"), "koeln")
        self.assertEqual(g._norm("Größe"), "groesse")


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.idx = g._index(
            "A unit test checks a single component in isolation. Mitochondrium.")

    def test_prefix_tolerance(self):
        # Morphology: mitochondria ~ mitochondrium via the shared 6-char prefix
        self.assertTrue(g._found("mitochondria", self.idx))

    def test_exact_token(self):
        self.assertTrue(g._found("component", self.idx))

    def test_absent_term(self):
        self.assertFalse(g._found("quaxomatron", self.idx))

    def test_coverage_fraction_and_missing(self):
        cover, missing = g._coverage({"component", "quaxomatron"}, self.idx)
        self.assertAlmostEqual(cover, 0.5)
        self.assertEqual(missing, ["quaxomatron"])

    def test_coverage_empty_terms(self):
        cover, missing = g._coverage(set(), self.idx)
        self.assertIsNone(cover)


class TestAnswerText(unittest.TestCase):
    def test_basic_uses_back(self):
        self.assertEqual(g._answer_text({"type": "basic", "back": "Hello"}).strip(), "Hello")

    def test_cloze_uses_deletions(self):
        t = g._answer_text({"type": "cloze", "text": "The {{c1::glycolysis}} and {{c2::ATP}}"})
        self.assertIn("glycolysis", t)
        self.assertIn("ATP", t)

    def test_occlusion_uses_labels(self):
        t = g._answer_text({"type": "occlusion", "regions": [{"label": "Aorta"}, {"label": "Valve"}]})
        self.assertIn("Aorta", t)
        self.assertIn("Valve", t)


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
                {"type": "basic", "front": "What does a unit test check?",
                 "back": "A single component in isolation."},
                {"type": "basic", "front": "Invented?",
                 "back": "The quaxomatron regulates flimmerblubb twirl dynamics.",
                 "source": "p. 999"},
            ],
            "<!-- p. 1 -->\n\nA unit test checks a single component in isolation.\n",
        )
        self.assertEqual(rc, 1)                      # ERROR -> exit 1
        self.assertIn("hallucination", out)
        self.assertIn("quaxomatron", out.lower())    # invented terms listed
        self.assertIn("p. 999", out)                 # phantom page reported

    def test_grounded_card_passes(self):
        rc, out = _run_check(
            [{"type": "cloze", "text": "The {{c1::glycolysis}} runs in the {{c2::cytoplasm}}."}],
            "<!-- p. 1 -->\n\nThe glycolysis runs in the cytoplasm.\n",
        )
        self.assertEqual(rc, 0)

    def test_legacy_german_markers_still_work(self):
        # Old extracts use "<!-- S. N -->" markers and "S. N" citations.
        rc, out = _run_check(
            [{"type": "basic", "front": "Where does glycolysis run?",
              "back": "In the cytoplasm.", "source": "script S. 1"}],
            "<!-- S. 1 -->\n\nThe glycolysis runs in the cytoplasm.\n",
        )
        self.assertEqual(rc, 0)
        self.assertNotIn("does not exist", out)      # S. 1 was found as a page


if __name__ == "__main__":
    unittest.main()
