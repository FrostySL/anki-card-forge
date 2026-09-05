"""Exercise the public-repository commit guard in disposable Git repositories.

The real checkout and its index are never used by the hook invocations. Git
and a POSIX shell are required; like the container-only tests, these tests skip when
the required executables are unavailable.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


GIT = shutil.which("git")
SHELL = shutil.which("sh")
if os.name == "nt" and GIT:
    git_shell = Path(GIT).resolve().parents[1] / "usr/bin/sh.exe"
    if git_shell.is_file():
        SHELL = str(git_shell)
HOOK = Path(__file__).resolve().parent.parent / ".githooks" / "pre-commit"
CHECKER = HOOK.parent.parent / "tools" / "check_repo_files.py"


@unittest.skipUnless(GIT and SHELL, "git and a POSIX shell are required for commit guard tests")
class TestCommitGuard(unittest.TestCase):
    def run_guard(self, path):
        # A test run may itself be launched by a Git hook. In particular, an
        # inherited GIT_INDEX_FILE or GIT_DIR must not target the real checkout.
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith("GIT_")}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run([GIT, "init", "--quiet", "--template=", directory],
                           env=env, check=True, capture_output=True)
            (root / "tools").mkdir()
            shutil.copy2(CHECKER, root / "tools/check_repo_files.py")
            # A managed interpreter must work without a python3 command on PATH.
            # The shell shim uses the same managed-Python branch as a POSIX venv.
            interpreter = root / ".venv/bin/python"
            interpreter.parent.mkdir(parents=True)
            executable = sys.executable.replace("\\", "/").replace("'", "'\"'\"'")
            interpreter.write_text(f"#!/bin/sh\nexec '{executable}' \"$@\"\n", encoding="utf-8")
            interpreter.chmod(0o755)
            # Reproduce forced additions of normally ignored personal material.
            (root / ".gitignore").write_text(
                "sources/\nextracted/\ndecks/\n*.pdf\n*.apkg\n*.colpkg\n",
                encoding="utf-8")
            candidate = root / path
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("test fixture\n", encoding="utf-8")
            subprocess.run([GIT, "add", "--force", "--", path], cwd=root,
                           env=env, check=True, capture_output=True)
            # Pass the actual hook through stdin so Bash does not need to
            # translate a host-specific absolute path to the project checkout.
            return subprocess.run([SHELL], cwd=root, env=env,
                                  input=HOOK.read_text(encoding="utf-8"),
                                  capture_output=True, text=True,
                                  encoding="utf-8")

    def assert_allowed(self, path):
        result = self.run_guard(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("BLOCKED:", result.stderr)

    def assert_blocked(self, path):
        result = self.run_guard(path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"BLOCKED: {json.dumps(path)}", result.stderr)

    def test_provider_neutral_documentation_is_allowed(self):
        for path in ("AGENTS.md", "skills/card-authoring/SKILL.md",
                     "skills/card-authoring/quality.md", "workflows/forge.md",
                     "workflows/rework.md"):
            with self.subTest(path=path):
                self.assert_allowed(path)

    def test_existing_adapter_and_project_paths_remain_allowed(self):
        for path in ("README.md", "Dockerfile",
                     ".claude/commands/forge.md", ".claude/commands/rework.md",
                     ".claude/skills/card-authoring/SKILL.md",
                     "tools/helper.py", "tests/test_helper.py",
                     ".github/workflows/tests.yml", ".githooks/pre-commit",
                     "reference/README.md", "sources/.gitkeep",
                     "decks/.gitkeep", "decks/example.cards.json",
                     "docs/setup.md", "docs/img/demo.png", "docs/img/demo.gif"):
            with self.subTest(path=path):
                self.assert_allowed(path)

    def test_personal_material_is_blocked(self):
        for path in ("sources/Biology/notes.md", "sources/course notes.txt",
                     "extracted/Biology/lecture.md",
                     "decks/Biology/personal.cards.json",
                     "decks/personal.cards.json", "reference/personal.txt",
                     ".forge/python/python.exe", ".venv/pyvenv.cfg"):
            with self.subTest(path=path):
                self.assert_blocked(path)

    def test_unrelated_skills_and_workflows_are_blocked(self):
        for path in ("skills/other/SKILL.md", "skills/SKILL.md",
                     "skills/card-authoring/personal.txt",
                     "skills/card-authoring/helper.py", "workflows/personal.md",
                     "workflows/forge.txt", "workflows/rework.json",
                     "workflows/private/forge.md", "docs/recording.mp4"):
            with self.subTest(path=path):
                self.assert_blocked(path)

    def test_pdf_and_anki_packages_are_blocked_even_in_allowed_directories(self):
        for path in (".pdf", ".APKG", "tools/.colpkg"):
            with self.subTest(path=path):
                self.assert_blocked(path)
        for directory in ("", "tools/", "tests/", ".claude/", ".github/",
                          ".githooks/", "docs/", "docs/img/",
                          "skills/card-authoring/", "workflows/"):
            for extension in ("pdf", "apkg", "colpkg", "PDF", "ApKg", "COLPKG"):
                path = f"{directory}personal.{extension}"
                with self.subTest(path=path):
                    result = self.run_guard(path)
                    self.assertEqual(result.returncode, 1,
                                     result.stdout + result.stderr)
                    self.assertIn(f"BLOCKED: {json.dumps(path)}", result.stderr)
                    self.assertIn("PDFs/Anki packages", result.stderr)


if __name__ == "__main__":
    unittest.main()
