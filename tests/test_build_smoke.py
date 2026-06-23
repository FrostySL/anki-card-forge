"""Smoke-Test fuer tools/build_deck.py: baut ein Mini-Deck jedes Typs zu einer .apkg.

Braucht genanki -> nur im Build-Container (anki-karten) vorhanden. Auf dem Host ohne
genanki ueberspringt sich der Test selbst. Im Container laufen lassen z. B. mit:
    docker run --rm -v "$PWD":/work --entrypoint python anki-karten \
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


@unittest.skipUnless(HAVE_GENANKI, "genanki nicht installiert (nur im Build-Container)")
class TestBuildSmoke(unittest.TestCase):
    def test_builds_valid_apkg(self):
        with tempfile.TemporaryDirectory() as d:
            cards = Path(d) / "t.cards.json"
            cards.write_text(json.dumps({"deck": "T::Smoke", "cards": [
                {"type": "basic", "front": "Q", "back": "A"},
                {"type": "cloze", "text": "Die {{c1::Antwort}}."},
                {"type": "typein", "front": "Q2", "back": "A2"},
            ]}), encoding="utf-8")
            out = Path(d) / "t.apkg"
            bd.build(str(cards), str(out))
            self.assertTrue(out.exists())
            self.assertTrue(zipfile.is_zipfile(out))


if __name__ == "__main__":
    unittest.main()
