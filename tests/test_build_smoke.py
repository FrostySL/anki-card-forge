"""Smoke test for tools/build_deck.py: builds a mini deck of each type into an .apkg.

Needs genanki -> only present in the build container (anki-cards). On the host
without genanki the test skips itself. Run inside the container e.g. with:
    docker run --rm -v "$PWD":/work --entrypoint python anki-cards \
        -m unittest discover -s /work/tests
"""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from _tools import load

try:
    bd = load("build_deck")
    HAVE_GENANKI = True
except Exception:
    HAVE_GENANKI = False


@unittest.skipUnless(HAVE_GENANKI, "genanki not installed (build container only)")
class TestBuildSmoke(unittest.TestCase):
    def test_builds_valid_apkg(self):
        with tempfile.TemporaryDirectory() as d:
            cards = Path(d) / "t.cards.json"
            cards.write_text(json.dumps({"deck": "T::Smoke", "cards": [
                {"type": "basic", "front": "Q", "back": "A"},
                {"type": "cloze", "text": "The {{c1::answer}}."},
                {"type": "typein", "front": "Q2", "back": "A2"},
            ]}), encoding="utf-8")
            out = Path(d) / "t.apkg"
            bd.build(str(cards), str(out))
            self.assertTrue(out.exists())
            self.assertTrue(zipfile.is_zipfile(out))


if __name__ == "__main__":
    unittest.main()
