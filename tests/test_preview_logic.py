"""Preview validation and image inlining without starting Chromium."""
import base64
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
