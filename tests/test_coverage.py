"""Tests for tools/coverage.py (duplicates + coverage across cards.json)."""
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
        self.assertIn("question", cov._front_text({"type": "basic", "front": "Question"}).lower())
        self.assertIn("deletion", cov._front_text({"type": "cloze", "text": "{{c1::Deletion}}"}).lower())
        occ = cov._front_text({"type": "occlusion", "header": "Heart", "regions": [{"label": "Aorta"}]})
        self.assertIn("Heart", occ)
        self.assertIn("Aorta", occ)

    def test_tokens_drop_short_and_stopwords(self):
        t = cov._tokens("What is the class")
        self.assertIn("class", t)
        self.assertNotIn("the", t)
        self.assertNotIn("what", t)

    def test_fmt_pages_ranges(self):
        self.assertEqual(cov._fmt_pages({1, 2, 3, 7}), "1-3, 7")
        self.assertEqual(cov._fmt_pages({5}), "5")
        self.assertEqual(cov._fmt_pages(set()), "")


class TestSiblingMd(unittest.TestCase):
    def test_prefix_match(self):
        # cards named short (08_TST), the .md long (08_TST_Testing_TDD) -> match by prefix
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                Path("decks/T").mkdir(parents=True)
                Path("extracted/T").mkdir(parents=True)
                Path("decks/T/08_TST.cards.json").write_text("{}", encoding="utf-8")
                Path("extracted/T/08_TST_Testing_TDD.md").write_text(
                    "<!-- p. 1 -->\nx\n", encoding="utf-8")
                self.assertEqual(
                    cov._sibling_md("decks/T/08_TST.cards.json"),
                    "extracted/T/08_TST_Testing_TDD.md",
                )
            finally:
                os.chdir(cwd)


class TestBogusPageCitations(unittest.TestCase):
    def test_non_existent_cited_pages_warned_not_counted(self):
        # A card citing p. 99 of a 2-page source must not inflate coverage —
        # it gets its own warning line instead.
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                Path("decks/T").mkdir(parents=True)
                Path("extracted/T").mkdir(parents=True)
                Path("decks/T/a.cards.json").write_text(json.dumps({
                    "deck": "T", "cards": [
                        {"type": "basic", "front": "Question alpha beta",
                         "back": "x", "source": "p. 1"},
                        {"type": "basic", "front": "Question gamma delta",
                         "back": "y", "source": "p. 99"},
                    ]}), encoding="utf-8")
                Path("extracted/T/a.md").write_text(
                    "<!-- p. 1 -->\na\n\n<!-- p. 2 -->\nb\n", encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cov.run(["decks/T"])
                out = buf.getvalue()
            finally:
                os.chdir(cwd)
        self.assertEqual(rc, 0)
        self.assertIn("1/2 covered", out)          # p. 99 not counted
        self.assertIn("non-existent", out)
        self.assertIn("p. 99", out)


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
                        {"type": "basic", "front": "What exactly is a software metric", "back": "x"}]}),
                        encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cov.run(["decks/T"])
                out = buf.getvalue()
                self.assertEqual(rc, 0)              # informational without --strict
                self.assertIn("EXACT", out)          # identical front flagged
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
                        {"type": "basic", "front": "Identical question here", "back": "x"}]}),
                        encoding="utf-8")
                with redirect_stdout(io.StringIO()):
                    rc = cov.run(["decks/T"], strict=True)
                self.assertEqual(rc, 1)
            finally:
                os.chdir(cwd)


class TestAgainstCorpus(unittest.TestCase):
    def test_duplicate_against_mirror_found(self):
        # New deck vs. the live-collection mirror (nested _cards/ layout):
        # the duplicate lives ONLY in the corpus, not among the inputs.
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                Path("decks/T").mkdir(parents=True)
                mirror = Path("decks/_anki-mirror/Old_cards")
                mirror.mkdir(parents=True)
                Path("decks/T/new.cards.json").write_text(json.dumps(
                    {"deck": "T", "cards": [
                        {"type": "basic", "front": "What exactly is a software metric",
                         "back": "x"}]}), encoding="utf-8")
                (mirror / "Old.cards.json").write_text(json.dumps(
                    {"deck": "Old", "cards": [
                        {"type": "basic", "front": "What exactly is a software metric",
                         "back": "y"}]}), encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cov.run(["decks/T"], against="decks/_anki-mirror")
                out = buf.getvalue()
            finally:
                os.chdir(cwd)
        self.assertEqual(rc, 0)
        self.assertIn("Against corpus", out)
        self.assertIn("EXACT", out)
        self.assertIn("Old.cards.json", out)

    def test_input_files_not_compared_against_themselves(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                Path("decks/T").mkdir(parents=True)
                Path("decks/T/a.cards.json").write_text(json.dumps(
                    {"deck": "T", "cards": [
                        {"type": "basic", "front": "Unique question alpha",
                         "back": "x"}]}), encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    # corpus dir == input dir: the file must be excluded
                    rc = cov.run(["decks/T"], against="decks/T")
                out = buf.getvalue()
            finally:
                os.chdir(cwd)
        self.assertEqual(rc, 0)
        self.assertIn("(0 cards)", out)   # nothing left in the corpus
        self.assertNotIn("EXACT", out)


if __name__ == "__main__":
    unittest.main()
