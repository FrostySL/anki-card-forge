"""Exercise prep.sh routing with stand-in tools; no Docker or PDF libraries."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

BASH = shutil.which("bash")
PREP = Path(__file__).resolve().parent.parent / "tools" / "prep.sh"


@unittest.skipUnless(BASH and os.name == "posix", "requires a POSIX Bash environment")
class TestPrep(unittest.TestCase):
    def run_prep(self, files=(), directories=(), single=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            (tools / "prep.sh").write_text(PREP.read_text(encoding="utf-8"), encoding="utf-8")
            for name in ("extract", "figextract"):
                script = tools / f"{name}.sh"
                script.write_text(
                    f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" > {name}.args\n',
                    encoding="utf-8")
                script.chmod(0o755)
            source = root / "sources" / "Topic with spaces"
            source.mkdir(parents=True)
            for name in files:
                (source / name).write_text("synthetic fixture", encoding="utf-8")
            for name in directories:
                (source / name).mkdir()
            input_path = str((source / single if single else source).relative_to(root))
            result = subprocess.run(
                [BASH, str(tools / "prep.sh"), input_path, "--lang", "eng", "--zoom", "2"],
                cwd=root, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "extract.args").read_text().splitlines(),
                             [input_path, "--lang", "eng"])
            crop_log = root / "figextract.args"
            crop_args = crop_log.read_text().splitlines() if crop_log.exists() else None
            return input_path, crop_args

    def test_pdf_folder_runs_cropping_with_any_extension_case(self):
        for names in (("lecture.pdf",), ("lecture.PDF",), ("lecture.PdF",),
                      ("lower.pdf", "UPPER.PDF"), ("lecture notes.pdf", "notes.md")):
            with self.subTest(names=names):
                input_path, crops = self.run_prep(files=names)
                self.assertEqual(crops, [input_path, "--zoom", "2"])

    def test_folders_without_pdf_files_skip_cropping(self):
        for files, directories in (((), ()), (("notes.md",), ()),
                                   (("notes.txt",), ("folder.pdf",))):
            with self.subTest(files=files, directories=directories):
                _, crops = self.run_prep(files=files, directories=directories)
                self.assertIsNone(crops)

    def test_single_mixed_case_pdf_is_cropped(self):
        input_path, crops = self.run_prep(files=("lecture.PdF",), single="lecture.PdF")
        self.assertEqual(crops, [input_path, "--zoom", "2"])


if __name__ == "__main__":
    unittest.main()
