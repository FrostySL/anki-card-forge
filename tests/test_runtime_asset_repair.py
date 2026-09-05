"""Offline runtime repair and safe publication, using tiny local archives."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from _tools import load

assets = load("runtime_assets")


class TestRuntimeAssetRepair(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="acf-asset-repair-")
        self.addCleanup(self.temp.cleanup)
        # Resolve Windows TEMP's possible 8.3 alias before path comparisons or
        # injected rename failures compare against production's resolved paths.
        self.root = Path(self.temp.name).resolve()

    def fixture(self):
        cache = self.root / "cache"
        cache.mkdir()
        archive = cache / "mathjax.tgz"
        with tarfile.open(archive, "w:gz") as package:
            for name, content in (("package/LICENSE", b"synthetic license"),
                                  ("package/es5/tex-svg.js", b"main script"),
                                  ("package/es5/input/tex/extensions/cancel.js", b"dynamic component")):
                info = tarfile.TarInfo(name)
                info.size = len(content)
                package.addfile(info, io.BytesIO(content))
        asset = {"filename": archive.name, "sha256": assets.sha256_file(archive),
                 "url": "https://example.invalid/synthetic-mathjax.tgz"}
        return cache, {"assets": {"mathjax": asset}}

    def test_offline_setup_repairs_missing_and_corrupt_dynamic_components(self):
        cache, manifest = self.fixture()
        destination = self.root / "mathjax"
        with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")):
            scripts = assets.ensure_mathjax(destination, cache_dir=cache, offline=True, manifest=manifest)
            extension = scripts / "input/tex/extensions/cancel.js"
            extension.unlink()
            assets.ensure_mathjax(destination, cache_dir=cache, offline=True, manifest=manifest)
            self.assertEqual(extension.read_bytes(), b"dynamic component")
            extension.write_bytes(b"corrupt script")
            assets.ensure_mathjax(destination, cache_dir=cache, offline=True, manifest=manifest)
            self.assertEqual(extension.read_bytes(), b"dynamic component")
            with patch.object(assets, "fetch_asset", side_effect=AssertionError("unchanged install must be reused")):
                assets.ensure_mathjax(destination, cache_dir=cache, offline=True, manifest=manifest)

    def test_added_language_file_does_not_invalidate_installed_payload(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "tesseract.exe").write_bytes(b"synthetic executable")
        destination = self.root / "tesseract"
        assets._publish(stage, destination, "expected")
        (destination / "eng.traineddata").write_bytes(b"separately verified model")
        self.assertTrue(assets._ready(destination, "expected", ["tesseract.exe"]))
        (destination / "tesseract.exe").write_bytes(b"damaged")
        self.assertFalse(assets._ready(destination, "expected", ["tesseract.exe"]))

    def test_publication_failure_restores_previous_working_install(self):
        destination = self.root / "installed"
        destination.mkdir()
        (destination / "payload").write_bytes(b"previous installation")
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "payload").write_bytes(b"new installation")
        original_replace = assets.os.replace

        def fail_stage(source, target):
            if Path(source) == stage:
                raise PermissionError("simulated file lock")
            return original_replace(source, target)

        with patch.object(assets.os, "replace", side_effect=fail_stage):
            with self.assertRaises(PermissionError):
                assets._publish(stage, destination, "new")
        self.assertEqual((destination / "payload").read_bytes(), b"previous installation")
        self.assertEqual((stage / "payload").read_bytes(), b"new installation")

    def test_failed_request_construction_closes_partial_file_before_cleanup(self):
        asset = {"filename": "tiny.zip", "sha256": hashlib.sha256(b"expected").hexdigest(),
                 "url": "https://example.invalid/tiny.zip"}
        cache = self.root / "cache"
        with patch.object(assets.urllib.request, "Request", side_effect=ValueError("bad request")):
            with self.assertRaisesRegex(ValueError, "bad request"):
                assets.fetch_asset(asset, cache)
        self.assertEqual(list(cache.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
