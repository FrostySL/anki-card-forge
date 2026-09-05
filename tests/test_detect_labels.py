"""Managed Windows OCR streams images without narrow-character temp paths."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _tools import load

try:
    detection = load("detect_labels")
except ModuleNotFoundError as error:
    if error.name not in {"PIL", "pytesseract"}:
        raise
    detection = None


HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
TSV = (HEADER + "1\t1\t0\t0\t0\t0\t0\t0\t200\t100\t-1\t\n"
       + "5\t1\t1\t1\t1\t1\t10\t20\t40\t10\t95.25\tALPHA\n"
       + '5\t1\t1\t1\t1\t2\t70\t20\t50\t10\t91\t"READY"\n').encode("utf-8")


@unittest.skipIf(detection is None, "Pillow/pytesseract are not installed (native/Docker OCR dependencies)")
class TestLabelDetection(unittest.TestCase):
    def test_tsv_preserves_literal_quotes_and_ignores_blank_structural_text(self):
        result = detection._parse_tsv(TSV)
        self.assertEqual(result["text"], ["", "ALPHA", '"READY"'])
        self.assertEqual(result["left"], [0, 10, 70])
        self.assertEqual(result["conf"], [-1.0, 95.25, 91.0])
        self.assertEqual(detection._parse_tsv(HEADER.encode())["text"], [])

    def test_malformed_tsv_fails_with_a_clear_error(self):
        for body in (b"", b"not\ta\theader", TSV.replace(b"95.25", b"NaN"),
                     TSV.replace(b"\t70\t20\t", b"\tleft\t20\t"),
                     TSV.replace(b'91\t"READY"', b"91")):
            with self.subTest(body=body), self.assertRaisesRegex(RuntimeError, "Tesseract"):
                detection._parse_tsv(body)

    def test_streamed_png_and_tsv_preserve_label_geometry_with_unicode_temp(self):
        image = detection.Image.new("RGB", (200, 100), "white")
        executable = Path("managed") / "tesseract.exe"
        relative_models = ".forge/tools/tesseract-test/tessdata"
        with tempfile.TemporaryDirectory(prefix="acf-labels-測試-") as temporary:
            source = Path(temporary) / "Diagramm 測試.png"
            image.save(source)
            before_cwd = os.getcwd()
            with patch.dict(os.environ, {"TEMP": str(source.parent), "TMP": str(source.parent)}), \
                    patch.object(detection, "_managed_windows_tesseract", return_value=(executable, relative_models)), \
                    patch.object(detection.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, TSV, b"")) as run:
                before_env = dict(os.environ)
                _, labels = detection.detect(source)
                self.assertEqual(dict(os.environ), before_env)
                self.assertEqual(os.getcwd(), before_cwd)
            self.assertEqual(labels, [
                {"label": "ALPHA", "x": .05, "y": .2, "w": .2, "h": .1},
                {"label": '"READY"', "x": .35, "y": .2, "w": .25, "h": .1},
            ])
            arguments, kwargs = run.call_args
            self.assertEqual(arguments[0], [str(executable), "stdin", "stdout", "-l", "eng+deu", "-c", "tessedit_create_tsv=1"])
            self.assertTrue(kwargs["input"].startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(kwargs["cwd"], detection.ROOT)
            self.assertEqual(kwargs["env"]["TESSDATA_PREFIX"], relative_models)
            self.assertEqual(kwargs["env"]["TEMP"], str(source.parent))
            self.assertNotIn("shell", kwargs)
            self.assertEqual(list(source.parent.iterdir()), [source])

    def test_failed_tesseract_is_not_accepted_as_an_empty_label_list(self):
        image = detection.Image.new("RGB", (10, 10), "white")
        with patch.object(detection, "_managed_windows_tesseract", return_value=(Path("tesseract.exe"), ".forge/tessdata")), \
                patch.object(detection.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"cannot read language data")):
            with self.assertRaisesRegex(RuntimeError, "cannot read language data"):
                detection._ocr_data(image, "eng")

    def test_unmanaged_and_linux_environments_keep_pytesseract_behavior(self):
        image = detection.Image.new("RGB", (10, 10), "white")
        with patch.object(detection, "_managed_windows_tesseract", return_value=None), \
                patch.object(detection.pytesseract, "image_to_data", return_value={"text": []}) as original:
            self.assertEqual(detection._ocr_data(image, "fra"), {"text": []})
        original.assert_called_once_with(image, lang="fra", output_type=detection.Output.DICT)


if __name__ == "__main__":
    unittest.main()
