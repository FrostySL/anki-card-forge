"""Tests for the pure path helpers of tools/extract.py and tools/figextract.py.

The PDF logic itself needs PyMuPDF and runs inside Docker; here `fitz` (and
`pymupdf4llm`) are faked with empty modules so the modules import on the host
and the sources/ -> extracted/ mapping can be tested — the regression was that
'./sources/…' and absolute paths broke the topic mirroring (and with it the
sibling lookup of grounding_check/coverage).
"""
import io
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.modules.setdefault("fitz", types.ModuleType("fitz"))
sys.modules.setdefault("pymupdf4llm", types.ModuleType("pymupdf4llm"))

from _tools import load

ex = load("extract")
fx = load("figextract")


class TestDefaultOut(unittest.TestCase):
    def test_all_path_forms_map_to_extracted_topic(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                os.makedirs("sources/Bio")
                for form in ("sources/Bio/x.pdf",
                             "./sources/Bio/x.pdf",
                             os.path.abspath("sources/Bio/x.pdf")):
                    self.assertEqual(ex._default_out(form),
                                     os.path.join("extracted", "Bio", "x.md"),
                                     form)
                    self.assertEqual(fx._default_out_dir(form),
                                     os.path.join("extracted", "Bio"), form)
            finally:
                os.chdir(cwd)

    def test_outside_sources_falls_back_flat(self):
        self.assertEqual(ex._default_out(os.path.join(os.sep, "elsewhere", "x.pdf")),
                         os.path.join("extracted", "x.md"))
        self.assertEqual(fx._default_out_dir("notes/x.pdf"), "extracted")


class TestTextIngest(unittest.TestCase):
    def test_text_source_mirrored_for_grounding(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                os.makedirs("sources/Bio")
                with open("sources/Bio/notes.md", "w", encoding="utf-8") as f:
                    f.write("# Notes\nglycolysis")
                with io.StringIO() as buf, redirect_stdout(buf):
                    out = ex.convert_text("sources/Bio/notes.md",
                                          ex._default_out("sources/Bio/notes.md"))
                self.assertEqual(out, os.path.join("extracted", "Bio", "notes.md"))
                with open(out, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# Notes\nglycolysis\n")
            finally:
                os.chdir(cwd)

    def test_folder_collection_includes_text_but_not_context(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                os.makedirs("sources/Bio")
                for name in ("a.pdf", "b.md", "c.txt", "context.md", "Kontext.md",
                             "ignored.docx"):
                    open(os.path.join("sources/Bio", name), "wb").close()
                found = [os.path.basename(p)
                         for p in ex._sources_in("sources/Bio")]
            finally:
                os.chdir(cwd)
        self.assertEqual(found, ["a.pdf", "b.md", "c.txt"])


class TestFigextractExitCode(unittest.TestCase):
    def test_missing_input_returns_nonzero(self):
        # A typo'd path used to print 'Skipped' but still exit 0 — callers with
        # set -e carried on without any crops.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = fx.main(["definitely/missing.pdf"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
