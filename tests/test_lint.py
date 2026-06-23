"""Tests fuer tools/lint_cards.py (Struktur-/Inhalts-Check der cards.json)."""
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
    """Schreibt cards.json (plus optionale Begleitdateien) und lintet -> (rc, stdout).

    Wechselt ins Tempverzeichnis, damit relative Bildpfade dort aufloesen (wie in echt,
    wo das CWD der Projekt-Root ist)."""
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
        self.assertIn("ohne 'back'", out)

    def test_missing_deck_errors(self):
        rc, out = _run({"cards": [{"type": "basic", "front": "Q", "back": "A"}]})
        self.assertEqual(rc, 1)
        self.assertIn("'deck'", out)

    def test_cloze_without_gap_errors(self):
        rc, out = _run({"deck": "D", "cards": [{"type": "cloze", "text": "kein luecke hier"}]})
        self.assertEqual(rc, 1)
        self.assertIn("keine Luecke", out)

    def test_unknown_type_errors(self):
        rc, out = _run({"deck": "D", "cards": [{"type": "weird", "front": "Q"}]})
        self.assertEqual(rc, 1)
        self.assertIn("unbekannter type", out)

    def test_occlusion_missing_image_errors(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "occlusion", "regions": [{"label": "x", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}]}]})
        self.assertEqual(rc, 1)
        self.assertIn("ohne 'image'", out)

    def test_occlusion_coord_out_of_range_only_warns(self):
        # Bild existiert (Dummy), damit nur die Koordinaten-WARNUNG bleibt, kein Bild-FEHLER.
        rc, out = _run(
            {"deck": "D", "cards": [{"type": "occlusion", "image": "i.png",
                "regions": [{"label": "x", "x": 1.5, "y": 0.1, "w": 0.1, "h": 0.1}]}]},
            extra_files={"i.png": b"x"},
        )
        self.assertEqual(rc, 0)               # Warnung blockiert nicht
        self.assertIn("ausserhalb 0..1", out)

    def test_duplicate_fronts_warn(self):
        rc, out = _run({"deck": "D", "cards": [
            {"type": "basic", "front": "Q", "back": "A"},
            {"type": "basic", "front": "Q", "back": "B"}]})
        self.assertEqual(rc, 0)
        self.assertIn("doppelte Frage", out)


if __name__ == "__main__":
    unittest.main()
