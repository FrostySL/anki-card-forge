"""Preview validation and image inlining without starting Chromium."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _tools import load

try:
    preview = load("preview")
except ModuleNotFoundError as exc:
    if exc.name not in ("genanki", "playwright", "playwright.sync_api"):
        raise
    preview = None


@unittest.skipIf(preview is None, "preview dependencies not installed")
class TestPreviewInputs(unittest.TestCase):
    def test_rejects_wrong_types_before_rendering(self):
        for data in ([], {"deck": "D", "cards": {}},
                     {"deck": "D", "cards": [{"front": "Q", "back": "A", "reverse": "false"}]},
                     {"deck": "D", "cards": [{"front": "Q", "back": "A", "explanation": []}]}):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "Invalid cards JSON"):
                preview._collect(data)

    def test_inlines_spaced_src_and_keeps_data_src_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "image.png"
            path.write_bytes(b"synthetic image")
            markup = f'<img data-src="unused.png" src = "{path}">'
            actual = preview._inline_imgs(markup)
            self.assertIn('data-src="unused.png"', actual)
            self.assertIn("data:image/png;base64," + base64.b64encode(b"synthetic image").decode(), actual)

    def test_review_manifest_tracks_rendered_variants_in_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            image = folder / "labels.png"
            image.write_bytes(b"synthetic image")
            fields = {"front": "Q", "back": "<b title='x > y'>A &amp; B</b><br>or C"}
            region = {"x": 0, "y": 0, "w": .1, "h": .1}
            notes = [
                {"type": "cloze", "text": "A long introduction before the first deletion. "
                 "{{c8::eight::number}} {{c2::<b>one &amp; two</b>}} {{c8::also eight}} {{c8::eight}}",
                 "guid": "original"},
                {"reverse": True, **fields}, fields, {"type": "typein", **fields},
                {"type": "occlusion", "image": str(image),
                 "regions": [dict(region, label="Left"), dict(region, label="Right")]},
            ]
            snapshot = folder / "snapshot.json"
            snapshot.write_text(json.dumps({"deck": "Test", "cards": notes}), encoding="utf-8")
            output = folder / "output"
            output.mkdir()
            with patch.object(preview, "_render") as render:
                cards = preview.preview_review(snapshot, output)
            items = render.call_args.args[0]
            render.assert_called_once_with(items, output, ("dark", "light"), offline=True, width=420)
            self.assertEqual([c["id"] for c in cards], [
                "note-1:c2", "note-1:c8", "note-2:forward", "note-2:reverse",
                "note-3:forward", "note-4:typein", "note-5:region-1", "note-5:region-2"])
            self.assertIn('<span class="cloze"><b>one &amp; two</b></span>', items[0].back)
            self.assertIn('<span class="cloze">also eight</span>', items[1].back)
            self.assertEqual(items[3].front, fields["back"])
            self.assertEqual([c["label"] for c in cards[:4]],
                             ["one & two", "eight · also eight", "Q", "A & B or C"])
            self.assertTrue(items[0].index_label().startswith("c2: A long introduction"))
            self.assertEqual(items[3].index_label(), "← A & B or C")
            self.assertEqual(cards[-1]["label"], "Right")
            self.assertEqual(cards[0]["guid"], "original")
            self.assertNotIn("guid", cards[-1])
            self.assertEqual(cards[1]["front"], "02-cloze-front-dark.png")
            self.assertEqual(cards[1]["back"], "02-cloze-back-dark.png")
            self.assertEqual(cards[1]["front_light"], "02-cloze-front.png")
            self.assertEqual(cards[1]["back_light"], "02-cloze-back.png")
            self.assertIn("[one & two]", cards[0]["context"])
            self.assertIn("[eight] one & two [also eight] [eight]", cards[1]["context"])
            self.assertNotIn("context", cards[2])
            self.assertEqual(cards, json.loads((output / "cards.json").read_text(encoding="utf-8")))
            self.assertFalse((folder / "preview").exists())

    def test_cloze_context_keeps_the_active_deletion_inside_a_long_note(self):
        text = ("{{c1::Hammer}} und [Hammer] " * 18 +
                "Der <b>{{c3::Hammer::Werkzeug}}</b> formt das Metall. " + "Weiterer Text. " * 20)
        excerpt = preview._cloze_context(text, 3)
        self.assertIn("Der [Hammer] formt das Metall.", excerpt)
        self.assertTrue(excerpt.startswith("…") and excerpt.endswith("…"), excerpt)
        self.assertLess(len(excerpt), 110)


if __name__ == "__main__":
    unittest.main()
