"""Verify shared orchestration without Docker or a user's Anki collection."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _tools import load

forge = load("forge")


class TestForge(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="acf forge ü ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.calls = []
        self.failures = {}

        def run(command, **kwargs):
            self.calls.append((command, kwargs))
            script = Path(command[1] if command[0] == "managed-python" else command[0]).name
            return subprocess.CompletedProcess(command, self.failures.get(script, 0))

        self.app = forge.Forge(root=self.root, cwd=self.root, backend="native",
                               python="managed-python", runner=run, env={})

    def file(self, relative, text="fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def cards(self, relative="decks/Biologie ü/one.cards.json", occlusion=False):
        return self.file(relative, json.dumps({"deck": "Synthetic", "cards": [
            {"type": "occlusion" if occlusion else "basic", "front": "Q", "back": "A"}
        ]}))

    def dispatch(self, command, args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.app.dispatch(command, args)
        return out.getvalue(), err.getvalue()

    def invocations(self):
        return [(Path(cmd[1]).name, cmd[2:]) for cmd, _ in self.calls]

    def test_native_paths_resolve_from_caller_and_children_run_at_root(self):
        cards = self.cards()
        self.app.cwd = cards.parent
        self.dispatch("preview", [cards.name, "--theme=both", "--offline"])
        self.assertEqual(self.invocations(), [("preview.py", ["decks/Biologie ü/one.cards.json", "--theme", "both", "--offline"])])
        command, kwargs = self.calls[0]
        self.assertEqual(kwargs["cwd"], self.root)
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")
        self.assertNotIn("shell", kwargs)
        self.assertEqual(command[0], "managed-python")

    def test_windows_absolute_paths_and_drive_case(self):
        if os.name != "nt":
            self.skipTest("Windows path semantics")
        cards = self.cards()
        value = str(cards)
        value = value[0].swapcase() + value[1:]
        self.dispatch("lint", [value])
        self.assertEqual(self.invocations()[0][1], ["decks/Biologie ü/one.cards.json"])

    def test_output_and_source_option_paths_resolve_from_caller(self):
        cards = self.cards()
        self.app.cwd = cards.parent
        self.dispatch("grounding", [cards.name, "--source=../../extracted/Biologie ü/one.md", "--min-cover", "0.4"])
        self.assertEqual(self.invocations()[0][1], ["decks/Biologie ü/one.cards.json", "--source", "extracted/Biologie ü/one.md", "--min-cover", "0.4"])
        self.calls.clear()
        self.dispatch("decode", ["original.apkg", "-orebuilt"])
        self.assertEqual(self.invocations()[0][1], ["decks/Biologie ü/original.apkg", "-o", "decks/Biologie ü/rebuilt"])

    def test_paths_outside_project_fail_before_any_tool(self):
        for command, args in (("lint", ["../outside.cards.json"]),
                              ("decode", ["decks/a.apkg", "--out", "../out"]),
                              ("anki", ["export", "A/B::deck.pdf", "../out.apkg"])):
            with self.subTest(command=command), self.assertRaises(forge.UsageError):
                self.dispatch(command, args)
        self.assertEqual(self.calls, [])

    def test_case_insensitive_extensions_and_sorted_unexpanded_glob(self):
        self.cards("decks/B/z.CARDS.JSON")
        self.cards("decks/B/a.CARDS.JSON")
        self.dispatch("finish", ["decks/B/*.CARDS.JSON", "decks/B/all.APKG"])
        self.assertEqual(self.invocations()[:2], [("lint_cards.py", ["decks/B/a.CARDS.JSON"]), ("lint_cards.py", ["decks/B/z.CARDS.JSON"])])
        self.assertIn(("coverage.py", ["decks/B/a.CARDS.JSON", "decks/B/z.CARDS.JSON"]), self.invocations())
        self.assertIn(("build_deck.py", ["decks/B/a.CARDS.JSON", "decks/B/z.CARDS.JSON", "decks/B/all.APKG"]), self.invocations())

    def test_unmatched_glob_fails_and_existing_brackets_are_literal(self):
        with self.assertRaisesRegex(forge.UsageError, "No inputs match"):
            self.dispatch("build", ["decks/*.cards.json"])
        self.assertFalse(self.calls)
        self.cards("decks/[chapter].cards.json")
        self.dispatch("build", ["decks/[chapter].cards.json"])
        self.assertEqual(self.invocations()[0][1], ["decks/[chapter].cards.json"])

    def test_prep_routes_options_indexes_only_outputs_and_crops_mixed_case_pdf(self):
        self.file("sources/Topic ü/one.PdF")
        self.file("sources/Topic ü/notes.txt")
        self.file("sources/Topic ü/context.md")
        self.file("extracted/Topic ü/one.md")
        self.file("extracted/Topic ü/notes.md")
        self.file("extracted/Unrelated/old.md")
        self.dispatch("prep", ["sources/Topic ü", "--lang=eng+deu", "-j2", "--zoom", "1.5", "--min-area=0.1"])
        self.assertEqual(self.invocations(), [
            ("extract.py", ["sources/Topic ü", "--lang", "eng+deu", "-j", "2"]),
            ("figindex.py", ["extracted/Topic ü/notes.md", "extracted/Topic ü/one.md"]),
            ("figextract.py", ["sources/Topic ü", "--zoom", "1.5", "--min-area", "0.1"]),
        ])

    def test_text_prep_skips_cropping_and_direct_custom_output_is_indexed(self):
        self.file("sources/Topic/notes.txt")
        (self.root / "sources/Topic/folder.pdf").mkdir()
        self.file("extracted/Topic/notes.md")
        out, _ = self.dispatch("prep", ["sources/Topic"])
        self.assertIn("skipping figure crops", out)
        self.assertEqual([name for name, _ in self.invocations()], ["extract.py", "figindex.py"])
        self.calls.clear()
        self.file("extracted/custom/result.md")
        self.dispatch("extract", ["sources/Topic/notes.txt", "-o", "extracted/custom/result.md"])
        self.assertEqual(self.invocations()[-1], ("figindex.py", ["extracted/custom/result.md"]))

    def test_prep_extraction_error_prevents_indexing_and_crops(self):
        self.file("sources/one.pdf")
        self.failures["extract.py"] = 7
        with self.assertRaises(forge.CommandFailed) as raised:
            self.dispatch("prep", ["sources/one.pdf"])
        self.assertEqual(raised.exception.returncode, 7)
        self.assertEqual([name for name, _ in self.invocations()], ["extract.py"])

    def test_missing_ocr_language_has_actionable_setup_command(self):
        tessdata = self.root / "tessdata"
        tessdata.mkdir()
        (tessdata / "eng.traineddata").write_bytes(b"fixture")
        self.app.env["TESSDATA_PREFIX"] = str(tessdata)
        self.file("sources/T/source.pdf")
        for command, args in (("detect", ["sources/label.png", "--lang=eng+fra"]),
                              ("extract", ["sources/T/source.pdf"]),
                              ("prep", ["sources/T", "--lang", "eng+fra"])):
            with self.subTest(command=command), self.assertRaisesRegex(forge.UsageError, r"forge.cmd setup --lang"):
                self.dispatch(command, args)
        self.assertEqual(self.calls, [])
        (tessdata / "deu.traineddata").write_bytes(b"fixture")
        self.dispatch("extract", ["sources/T/source.pdf"])
        self.assertEqual(self.invocations(), [("extract.py", ["sources/T/source.pdf"])])

    def test_relative_tessdata_uses_project_root_from_a_subdirectory(self):
        self.file("tessdata/eng.traineddata")
        source = self.file("sources/Topic ü/label.png")
        self.app.cwd = source.parent
        self.app.env["TESSDATA_PREFIX"] = "tessdata"
        self.dispatch("detect", ["label.png", "--lang=eng"])
        self.assertEqual(self.invocations(), [("detect_labels.py", ["sources/Topic ü/label.png", "--lang", "eng"])])

    def test_colliding_source_folder_outputs_fail_before_any_write(self):
        self.file("sources/T/chapter.pdf")
        self.file("sources/T/chapter.txt")
        for command in ("extract", "prep"):
            with self.subTest(command=command), self.assertRaisesRegex(forge.UsageError, "both map"):
                self.dispatch(command, ["sources/T"])
        self.assertEqual(self.calls, [])

    def test_collisions_across_inputs_include_case_and_unicode_normalization(self):
        cases = (("chapter.pdf", "CHAPTER.txt"), ("É.pdf", "E\u0301.txt"))
        for first, second in cases:
            with self.subTest(names=(first, second)):
                self.file("sources/T/" + first)
                self.file("sources/T/" + second)
                with self.assertRaisesRegex(forge.UsageError, "both map"):
                    self.dispatch("prep", ["sources/T/" + first, "sources/T/" + second])
        self.assertEqual(self.calls, [])

    def test_finish_advisory_grounding_does_not_prevent_build_and_validate(self):
        self.cards(occlusion=True)
        self.failures["grounding_check.py"] = 1
        out, err = self.dispatch("finish", ["decks/Biologie ü/one.cards.json"])
        self.assertEqual([name for name, _ in self.invocations()], ["lint_cards.py", "grounding_check.py", "build_deck.py", "validate.py"])
        self.assertEqual(self.invocations()[-1][1], ["decks/Biologie ü/one.apkg"])
        self.assertIn("advisory", err)
        self.assertIn("both themes", out)

    def test_finish_fatal_gates_stop_before_import_and_sync(self):
        self.cards()
        for failure, count in (("lint_cards.py", 1), ("build_deck.py", 3), ("validate.py", 4), ("anki_connect.py", 5)):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.failures = {failure: 9}
                with self.assertRaises(forge.CommandFailed):
                    self.dispatch("finish", ["decks/Biologie ü/one.cards.json", "--push", "--sync"])
                self.assertEqual(len(self.calls), count)
                self.assertNotIn(("anki_connect.py", ["sync"]), self.invocations())

    def test_finish_push_prune_sync_are_forwarded_only_when_requested(self):
        self.cards()
        self.dispatch("finish", ["decks/Biologie ü/one.cards.json", "--push", "--prune", "--sync"])
        self.assertEqual(self.invocations()[-2:], [("anki_connect.py", ["push", "decks/Biologie ü/one.apkg", "--prune"]), ("anki_connect.py", ["sync"])])
        self.assertNotIn("--no-backup", str(self.calls))

    def test_invalid_finish_flags_bundle_and_options_fail_before_processing(self):
        cases = (["decks/a.json", "--sync"], ["decks/a.json", "--prune"],
                 ["decks/a.json", "decks/b.json"],
                 ["decks/a.json", "a.apkg", "b.apkg"],
                 ["decks/a.json", "--no-backup"], ["decks/a.json", "--push=true"])
        for args in cases:
            with self.subTest(args=args), self.assertRaises(forge.UsageError):
                self.dispatch("finish", args)
        self.assertEqual(self.calls, [])

    def test_anki_deck_names_html_and_timestamps_are_never_paths(self):
        name = 'C:/strange deck.pdf::Topic ü'
        self.dispatch("anki", ["export", name, "decks/out.apkg"])
        self.assertEqual(self.invocations()[-1][1], ["export", name, "decks/out.apkg"])
        html = 'Back=<img src="somewhere/image.png"><b>A & B</b>'
        self.dispatch("anki", ["update-note", "123", "--field", html])
        self.assertEqual(self.invocations()[-1][1], ["update-note", "123", "--field", html])
        self.dispatch("anki", ["mirror", name])
        self.assertEqual(self.invocations()[-1][1], ["mirror", name])

    def test_setup_and_doctor_delegate_without_other_tools(self):
        self.dispatch("setup", ["--lang", "eng+deu"])
        self.dispatch("doctor", [])
        self.assertEqual(self.invocations(), [("native_setup.py", ["setup", "--lang", "eng+deu"]), ("native_setup.py", ["doctor"])])

    def test_local_environment_helper_is_used_only_at_dispatch(self):
        self.file("tools/native_setup.py", 'def environment(root):\n    return {"ACF_TEST_ENV": str(root)}\n')
        self.app.env["PYTHONPATH"] = "unrelated-global-python"
        self.assertNotIn("ACF_TEST_ENV", self.app.env)
        self.dispatch("lint", ["decks/a.cards.json"])
        self.assertEqual(self.calls[0][1]["env"]["ACF_TEST_ENV"], str(self.root))
        self.assertNotIn("PYTHONPATH", self.calls[0][1]["env"])

    def test_default_extraction_output_cannot_follow_link_outside_project(self):
        self.file("sources/T/notes.txt")
        with tempfile.TemporaryDirectory() as outside:
            try:
                (self.root / "extracted").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("creating directory symlinks is unavailable")
            try:
                with self.assertRaises(forge.UsageError):
                    self.dispatch("extract", ["sources/T/notes.txt"])
                self.assertEqual(self.calls, [])
            finally:
                (self.root / "extracted").unlink()

    @unittest.skipUnless(os.name == "posix", "Docker wrapper execution is POSIX-only")
    def test_docker_prep_uses_existing_wrappers_without_double_indexing(self):
        self.file("sources/T/a.pdf")
        self.file("extracted/T/a.md")
        self.app.backend = "docker"
        self.dispatch("prep", ["sources/T", "--lang", "eng"])
        self.assertEqual([(Path(cmd[0]).name, cmd[1:]) for cmd, _ in self.calls], [
            ("extract.sh", ["sources/T", "--lang", "eng"]),
            ("figextract.sh", ["sources/T"]),
        ])

    def test_invalid_prep_option_or_missing_value_has_no_partial_run(self):
        for args in (["sources/T", "--lang"], ["sources/T", "--lang", "--zoom", "2"],
                     ["sources/T", "--unknown", "2"], ["sources/T", "--lang="]):
            with self.subTest(args=args), self.assertRaises(forge.UsageError):
                self.dispatch("prep", args)
        self.assertEqual(self.calls, [])

    def test_main_preserves_tool_error_status(self):
        with patch.object(forge.Forge, "dispatch", side_effect=forge.CommandFailed(23)):
            self.assertEqual(forge.main(["--backend", "native", "validate", "decks/a.apkg"]), 23)


if __name__ == "__main__":
    unittest.main()
