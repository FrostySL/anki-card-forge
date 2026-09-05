"""Exercise the shared staged, tracked and PR-diff guard in disposable Git repos."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


GIT = shutil.which("git")
CHECKER = Path(__file__).resolve().parent.parent / "tools/check_repo_files.py"


@unittest.skipUnless(GIT, "git is required for repository file guard tests")
class TestRepositoryFileGuard(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        # Git may have launched the test suite from a real checkout's hook.
        self.env = {key: value for key, value in os.environ.items()
                    if not key.upper().startswith("GIT_")}
        self.env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        self.git("init", "--quiet", "--template=", ".")
        self.git("config", "user.name", "Guard Test")
        self.git("config", "user.email", "guard@example.invalid")
        self.write("README.md")
        self.base = self.commit("base")

    def git(self, *args):
        return subprocess.run([GIT, *args], cwd=self.root, env=self.env,
                              check=True, capture_output=True).stdout.decode().strip()

    def write(self, path, text="fixture\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.git("add", "--force", "--", path)

    def commit(self, message):
        self.git("commit", "--quiet", "--no-gpg-sign", "-m", message)
        return self.git("rev-parse", "HEAD")

    def guard(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(CHECKER), *args],
                              cwd=cwd or self.root, env=self.env,
                              capture_output=True, text=True, encoding="utf-8")

    def assert_blocked(self, result, path):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"BLOCKED: {json.dumps(path)}", result.stderr)

    def test_staged_rename_and_copy_destinations_are_checked(self):
        self.write("tools/original.py")
        self.commit("tracked fixture")
        (self.root / "sources").mkdir()
        self.git("mv", "tools/original.py", "sources/renamed notes.txt")
        self.write("decks/copied.cards.json")
        result = self.guard("--staged")
        self.assert_blocked(result, "sources/renamed notes.txt")
        self.assertIn('"decks/copied.cards.json"', result.stderr)

    def test_staged_modification_deletion_and_move_out_of_private_path(self):
        # A previously tracked file can still be edited or removed. The complete
        # snapshot check below deliberately applies stricter rules in CI.
        self.write("sources/legacy.txt")
        self.write("sources/remove.txt")
        self.write("sources/move.txt")
        self.commit("legacy files without guard")
        self.write("sources/legacy.txt", "updated content\n")
        self.git("rm", "sources/remove.txt")
        self.git("mv", "sources/move.txt", "public.txt")
        result = self.guard("--staged")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_range_checks_all_branch_commits_and_not_the_index(self):
        self.write("tools/helper.py")
        self.commit("first change")
        self.write("sources/private.txt")
        head = self.commit("second change")
        self.write("decks/only-staged.cards.json")
        result = self.guard("--base", self.base, "--head", head)
        self.assert_blocked(result, "sources/private.txt")
        self.assertNotIn("only-staged", result.stderr)

    def test_range_uses_merge_base_when_base_branch_has_diverged(self):
        self.write("sources/private.txt")
        feature = self.commit("feature file")
        self.git("checkout", "--quiet", "--detach", self.base)
        # Identical content on the other branch cancels out in a two-dot diff,
        # but remains visible in the PR's three-dot diff.
        self.write("sources/private.txt")
        other_branch = self.commit("independent base branch file")
        result = self.guard("--base", other_branch, "--head", feature)
        self.assert_blocked(result, "sources/private.txt")

    def test_range_rename_is_checked(self):
        (self.root / "sources").mkdir()
        self.git("mv", "README.md", "sources/private.txt")
        self.commit("rename")
        self.assert_blocked(self.guard("--base", self.base), "sources/private.txt")

    def test_invalid_ref_and_unrelated_histories_fail_closed(self):
        for args in (("--base", "missing-ref"),
                     ("--base", self.base, "--head", "missing-head"),
                     ("--base=--help",)):
            with self.subTest(args=args):
                result = self.guard(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("could not run", result.stderr)
        self.git("checkout", "--quiet", "--orphan", "unrelated")
        self.write("other.txt")
        self.commit("unrelated root")
        result = self.guard("--base", self.base)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("could not run", result.stderr)

    @unittest.skipIf(os.name == "nt", "Windows cannot create newline filenames")
    def test_nul_delimited_paths_and_escaped_output(self):
        path = "sources/private notes\nREADME.md"
        self.write(path)
        self.write("tools/allowed notes\nREADME.md")
        staged = self.guard("--staged")
        self.assert_blocked(staged, path)
        self.assertEqual(staged.stderr.count("BLOCKED:"), 1)
        self.assertNotIn("notes\nREADME", staged.stderr)
        self.commit("unusual filenames")
        self.assert_blocked(self.guard("--base", self.base), path)

    def test_tracked_snapshot_checks_old_files_but_ignores_untracked_files(self):
        self.write("tools/helper.py")
        self.commit("allowed")
        (self.root / "private.PDF").write_text("untracked", encoding="utf-8")
        result = self.guard("--tracked")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write("tools/legacy.PDF")
        self.commit("legacy blocked format")
        self.assert_blocked(self.guard("--tracked"), "tools/legacy.PDF")

    def test_git_relative_configuration_cannot_hide_paths(self):
        self.git("config", "diff.relative", "true")
        self.write("sources/private.txt")
        nested = self.root / "tools"
        nested.mkdir()
        self.assert_blocked(self.guard("--staged", cwd=nested), "sources/private.txt")
        self.assert_blocked(self.guard("--tracked", cwd=nested), "sources/private.txt")

    def test_non_repository_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.guard("--staged", cwd=directory)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("could not run", result.stderr)


if __name__ == "__main__":
    unittest.main()
