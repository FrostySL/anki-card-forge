"""Windows filename edge cases must not silently overwrite exported content."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from _tools import load

filenames = load("_filenames")
decode = load("apkg_to_cards")
guard = load("check_repo_files")


class TestPortableFilenames(unittest.TestCase):
    def test_reserved_names_and_long_unicode(self):
        for name in ("CON", "con.txt", "LPT1", "COM¹", "NUL"):
            self.assertTrue(filenames.safe_stem(name).startswith("_"))
        self.assertLess(len(filenames.safe_stem("Ä" * 200).encode("utf-8")), 180)
        self.assertNotEqual(filenames.safe_stem("Ä" * 200), filenames.safe_stem("Ä" * 201))

    def test_deck_exports_keep_content_with_case_and_normalization_collisions(self):
        names = ["Bio", "bio", "A::B", "A B", "CON", "Ä", "A\u0308"]
        by_deck = {name: [{"guid": str(i), "type": "basic", "front": name, "back": "A"}]
                   for i, name in enumerate(names)}
        with tempfile.TemporaryDirectory() as directory:
            files = decode.write_cards_json(by_deck, directory)
            self.assertEqual(len(files), len(names))
            self.assertEqual(len({filenames.collision_key(Path(f).name) for f, _, _ in files}), len(names))
            for path, deck, count in files:
                self.assertEqual(count, 1)
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                self.assertEqual(data, {"deck": deck, "cards": by_deck[deck]})

    def test_media_remapping_preserves_bytes_and_references(self):
        names = ["Fig.png", "fig.png", "CON.png", "normal image.png"]
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "test.apkg"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("media", json.dumps(dict(enumerate(names))))
                for i, name in enumerate(names):
                    archive.writestr(str(i), name.encode())
            mapping = decode.extract_media(package, Path(directory) / "decoded")
            self.assertEqual(set(mapping), set(names))
            self.assertEqual(len({filenames.collision_key(p) for p in mapping.values()}), len(names))
            for name, path in mapping.items():
                self.assertEqual(Path(path).read_bytes(), name.encode())
            self.assertEqual(Path(mapping["normal image.png"]).name, "normal image.png")
            deck = {"Test": [{"back": '<img src="CON.png"> <img src="fig.png">'}]}
            # Decoded media belongs to the current project. The OS temporary
            # directory can live on another Windows drive than the checkout.
            previous_cwd = os.getcwd()
            try:
                os.chdir(directory)
                self.assertEqual(decode.rewrite_media_srcs(deck, mapping), 2)
            finally:
                os.chdir(previous_cwd)
            self.assertIn("_CON.png", deck["Test"][0]["back"])
            self.assertIn("decoded/media/", deck["Test"][0]["back"])
            self.assertNotIn("\\", deck["Test"][0]["back"])

    def test_runtime_directories_cannot_be_published(self):
        for name in (".forge/uv/uv.exe", ".FORGE/cache/item", ".venv/pyvenv.cfg"):
            self.assertIn("must stay local", guard.blocked_reason(name))

    def test_long_media_extensions_fit_the_filesystem(self):
        name = "x." + "Ä" * 260
        self.assertLess(len(filenames.unique_media_names([name])[name].encode("utf-8")), 220)

    def test_duplicate_media_basenames_fail_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "duplicate.apkg"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("media", json.dumps({"0": "a/fig.png", "1": "b/fig.png"}))
                archive.writestr("0", b"first")
                archive.writestr("1", b"second")
            outdir = Path(directory) / "decoded"
            with self.assertRaisesRegex(ValueError, "identical base names"):
                decode.extract_media(package, outdir)
            self.assertFalse(outdir.exists())


if __name__ == "__main__":
    unittest.main()
