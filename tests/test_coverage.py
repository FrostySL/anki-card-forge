"""Tests fuer tools/coverage.py (Dubletten + Abdeckung ueber cards.json)."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _tools import load

cov = load("coverage")


class TestHelpers(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(cov._jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(cov._jaccard({"a"}, {"b"}), 0.0)
        self.assertEqual(cov._jaccard(set(), {"a"}), 0.0)

    def test_front_text_per_type(self):
        self.assertIn("frage", cov._front_text({"type": "basic", "front": "Frage"}).lower())
        self.assertIn("luecke", cov._front_text({"type": "cloze", "text": "{{c1::Luecke}}"}).lower())
        occ = cov._front_text({"type": "occlusion", "header": "Herz", "regions": [{"label": "Aorta"}]})
        self.assertIn("Herz", occ)
        self.assertIn("Aorta", occ)

    def test_tokens_drop_short_and_stopwords(self):
        t = cov._tokens("Was ist die Klasse")
        self.assertIn("klasse", t)
        self.assertNotIn("die", t)
        self.assertNotIn("ist", t)
        self.assertNotIn("was", t)

    def test_fmt_pages_ranges(self):
        self.assertEqual(cov._fmt_pages({1, 2, 3, 7}), "1-3, 7")
        self.assertEqual(cov._fmt_pages({5}), "5")
        self.assertEqual(cov._fmt_pages(set()), "")


class TestSiblingMd(unittest.TestCase):
    def test_prefix_match(self):
        # cards heisst kurz (08_TST), die .md lang (08_TST_Testen_TDD) -> per Praefix finden
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                Path("decks/T").mkdir(parents=True)
                Path("aufbereitet/T").mkdir(parents=True)
                Path("decks/T/08_TST.cards.json").write_text("{}", encoding="utf-8")
                Path("aufbereitet/T/08_TST_Testen_TDD.md").write_text(
                    "<!-- S. 1 -->\nx\n", encoding="utf-8")
                self.assertEqual(
                    cov._sibling_md("decks/T/08_TST.cards.json"),
                    "aufbereitet/T/08_TST_Testen_TDD.md",
                )
            finally:
                os.chdir(cwd)


class TestRun(unittest.TestCase):
    def test_exact_duplicate_across_files(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                decks = Path("decks/T")
                decks.mkdir(parents=True)
                for name in ("a.cards.json", "b.cards.json"):
                    (decks / name).write_text(json.dumps({"deck": "T", "cards": [
                        {"type": "basic", "front": "Was ist eine Softwaremetrik genau", "back": "x"}]}),
                        encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cov.run(["decks/T"])
                out = buf.getvalue()
                self.assertEqual(rc, 0)              # informativ ohne --strict
                self.assertIn("EXAKT", out)          # identische Front markiert
            finally:
                os.chdir(cwd)

    def test_strict_returns_one_on_dupes(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                decks = Path("decks/T")
                decks.mkdir(parents=True)
                for name in ("a.cards.json", "b.cards.json"):
                    (decks / name).write_text(json.dumps({"deck": "T", "cards": [
                        {"type": "basic", "front": "Identische Frage hier", "back": "x"}]}),
                        encoding="utf-8")
                with redirect_stdout(io.StringIO()):
                    rc = cov.run(["decks/T"], strict=True)
                self.assertEqual(rc, 1)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
