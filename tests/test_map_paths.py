"""Tests for tools/_map_paths.py — the path mapper shared by the Docker wrappers.

Regression cover for the silent-failure bug: the wrappers mount PROJECT_DIR at
/work, so an absolute or wrong-cwd path did not resolve in the container (a
build reported OK while the .apkg was written inside the container and lost).
"""
import os
import tempfile
import unittest

from _tools import load

mp = load("_map_paths")


class TestLooksLikePath(unittest.TestCase):
    def test_flags_and_values_pass_through(self):
        self.assertFalse(mp._looks_like_path("--lang"))
        self.assertFalse(mp._looks_like_path("-j"))
        self.assertFalse(mp._looks_like_path("eng+fra"))
        self.assertFalse(mp._looks_like_path("2.5"))
        self.assertFalse(mp._looks_like_path("40"))

    def test_paths_recognized(self):
        self.assertTrue(mp._looks_like_path("decks/x.cards.json"))
        self.assertTrue(mp._looks_like_path("x.apkg"))          # bare name + ext
        self.assertTrue(mp._looks_like_path("sources/Bio/"))    # trailing slash


class TestMapArg(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.realpath(self.d)

    def _map(self, arg):
        return mp.map_arg(arg, self.root)

    def test_relative_inside_stays_relative(self):
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            os.makedirs("decks/Bio")
            open("decks/Bio/x.cards.json", "w").close()
            self.assertEqual(self._map("decks/Bio/x.cards.json"),
                             os.path.join("decks", "Bio", "x.cards.json"))
        finally:
            os.chdir(cwd)

    def test_absolute_inside_becomes_relative(self):
        # The core fix: an absolute path inside the project maps to /work/… .
        target = os.path.join(self.root, "decks", "x.apkg")
        self.assertEqual(self._map(target), os.path.join("decks", "x.apkg"))

    def test_nonexistent_output_inside_ok(self):
        # Output paths do not exist yet — must still map, not error.
        self.assertEqual(mp.map_arg(os.path.join(self.root, "decks", "new.apkg"),
                                    self.root),
                         os.path.join("decks", "new.apkg"))

    def test_wrong_cwd_relative_resolves(self):
        sub = os.path.join(self.root, "decks", "Bio")
        os.makedirs(sub)
        open(os.path.join(sub, "x.cards.json"), "w").close()
        cwd = os.getcwd()
        os.chdir(sub)  # as if called from within decks/Bio
        try:
            self.assertEqual(mp.map_arg("x.cards.json", self.root),
                             os.path.join("decks", "Bio", "x.cards.json"))
        finally:
            os.chdir(cwd)

    def test_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            outside = os.path.join(other, "evil.apkg")
            with self.assertRaises(SystemExit) as cm:
                mp.map_arg(outside, self.root)
            self.assertEqual(cm.exception.code, 2)

    def test_tmp_output_rejected(self):
        # The exact setup.sh failure: a /tmp output path would be lost.
        with self.assertRaises(SystemExit):
            mp.map_arg("/tmp/somewhere/out.apkg", self.root)

    def test_flag_passthrough_unchanged(self):
        self.assertEqual(self._map("--lang"), "--lang")
        self.assertEqual(self._map("eng+fra"), "eng+fra")


class TestMainOutput(unittest.TestCase):
    def test_nul_terminated_stream(self):
        import io
        import contextlib
        root = os.path.realpath(tempfile.mkdtemp())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mp.main([root, "--lang", "eng+deu", os.path.join(root, "decks", "a.apkg")])
        parts = buf.getvalue().split("\0")
        # trailing "" after the last NUL
        self.assertEqual(parts[:-1], ["--lang", "eng+deu", os.path.join("decks", "a.apkg")])

    def test_empty_args_empty_output(self):
        import io
        import contextlib
        root = os.path.realpath(tempfile.mkdtemp())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mp.main([root])
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
