"""Network-free checks for the download and extraction trust boundaries."""
import base64
import hashlib
from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from _tools import load

assets = load("runtime_assets")
native = load("native_setup")


class RuntimeAssets(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="acf-assets-")
        self.addCleanup(self.temporary.cleanup)
        # Windows TEMP may use an 8.3 alias; production helpers return resolved
        # paths, so comparisons must use the same filesystem identity.
        self.root = Path(self.temporary.name).resolve()
        self.payload = b"verified runtime fixture\n"
        self.asset = {"filename": "fixture.zip", "url": "https://example.invalid/fixture.zip",
                      "sha256": hashlib.sha256(self.payload).hexdigest()}

    def wheel_fixture(self):
        site = self.root / ".venv" / "Lib" / "site-packages"
        metadata = site / "demo-1.0.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n", encoding="utf-8")
        module = site / "demo.py"
        module.write_bytes(self.payload)
        digest = base64.urlsafe_b64encode(hashlib.sha256(self.payload).digest()).rstrip(b"=").decode("ascii")
        (metadata / "RECORD").write_text(f"demo.py,sha256={digest},{len(self.payload)}\n"
                                       "demo-1.0.dist-info/RECORD,,\n"
                                       "__pycache__/demo.pyc,,\n", encoding="utf-8")
        return module, metadata

    def test_wheel_record_verifies_payload_and_ignores_generated_bytecode(self):
        self.wheel_fixture()
        self.assertEqual(native.package_integrity(self.root), {"checked": 1, "damaged": {}})

    def test_wheel_record_detects_same_size_corruption_and_missing_module(self):
        module, _ = self.wheel_fixture()
        module.write_bytes(b"x" * len(self.payload))
        self.assertIn("hash mismatch", native.package_integrity(self.root)["damaged"]["demo"][0])
        module.unlink()
        self.assertIn("Missing", native.package_integrity(self.root)["damaged"]["demo"][0])

    def test_wheel_missing_record_is_damaged(self):
        _, metadata = self.wheel_fixture()
        (metadata / "RECORD").unlink()
        self.assertIn("RECORD is missing", native.package_integrity(self.root)["damaged"]["demo"][0])

    def test_package_repair_reinstalls_only_damaged_package_offline(self):
        before = {"checked": 2, "damaged": {"demo": ["missing module"]}}
        after = {"checked": 2, "damaged": {}}
        with patch.object(native, "ROOT", self.root), patch.object(native.sys, "platform", "win32"), \
             patch.object(native, "package_integrity", side_effect=[before, after]), \
             patch.object(native, "environment", return_value={}), patch.object(native, "_run") as run:
            self.assertEqual(native.repair_packages(offline=True), 0)
        arguments = run.call_args.args[0]
        self.assertIn("--offline", arguments)
        self.assertEqual(arguments[arguments.index("--reinstall-package") + 1], "demo")
        self.assertNotIn("--reinstall", arguments)
        run.assert_called_once()

    def test_package_repair_healthy_repeat_does_not_invoke_uv(self):
        with patch.object(native.sys, "platform", "win32"), \
             patch.object(native, "package_integrity", return_value={"checked": 2, "damaged": {}}), \
             patch.object(native, "_run", side_effect=AssertionError("unnecessary reinstall")):
            self.assertEqual(native.repair_packages(offline=True), 0)

    def test_offline_reuses_only_verified_cache_without_network(self):
        target = self.root / self.asset["filename"]
        target.write_bytes(self.payload)
        with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("network")):
            self.assertEqual(assets.fetch_asset(self.asset, self.root, offline=True), target)
            target.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "damaged"):
                assets.fetch_asset(self.asset, self.root, offline=True)

    def test_offline_cache_miss_never_requests_network(self):
        with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(RuntimeError, "Offline setup needs"):
                assets.fetch_asset(self.asset, self.root, offline=True)

    def test_download_is_verified_before_publication(self):
        with patch.object(assets.urllib.request, "urlopen", return_value=io.BytesIO(b"tampered")):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                assets.fetch_asset(self.asset, self.root)
        self.assertFalse((self.root / self.asset["filename"]).exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_online_repairs_damaged_cache_atomically(self):
        target = self.root / self.asset["filename"]
        target.write_bytes(b"damaged")
        with patch.object(assets.urllib.request, "urlopen", return_value=io.BytesIO(self.payload)):
            self.assertEqual(assets.fetch_asset(self.asset, self.root), target)
        self.assertEqual(target.read_bytes(), self.payload)

    def test_failed_network_keeps_existing_cache_and_cleans_partial(self):
        target = self.root / self.asset["filename"]
        target.write_bytes(b"damaged")
        with patch.object(assets.urllib.request, "urlopen", side_effect=OSError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "Download failed"):
                assets.fetch_asset(self.asset, self.root)
        self.assertEqual(target.read_bytes(), b"damaged")
        self.assertEqual([p.name for p in self.root.iterdir()], [self.asset["filename"]])

    def test_language_git_identity_covers_header_size_and_bytes(self):
        path = self.root / "fra.traineddata"
        path.write_bytes(self.payload)
        identity = hashlib.sha1(f"blob {len(self.payload)}\0".encode() + self.payload).hexdigest()
        specification = {"git_blob_sha1": identity, "size": len(self.payload)}
        assets.verify_asset(path, specification)
        path.write_bytes(b"x" * len(self.payload))
        with self.assertRaisesRegex(ValueError, "Git object mismatch"):
            assets.verify_asset(path, specification)

    def test_assets_without_digest_or_https_are_rejected(self):
        path = self.root / "asset"
        path.write_bytes(self.payload)
        with self.assertRaisesRegex(ValueError, "expected content digest"):
            assets.verify_asset(path, {})
        self.asset["url"] = "http://example.invalid/insecure.zip"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            assets.fetch_asset(self.asset, self.root)

    def test_archive_paths_cannot_escape_on_windows_or_posix(self):
        for name in ("../escape", "..\\escape", "/absolute", "C:/escape", "C:\\escape", "nested/../../escape"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                assets.archive_target(self.root, name)
        self.assertEqual(assets.archive_target(self.root, "safe/sub/file"), self.root / "safe/sub/file")

    def test_zip_rejects_path_traversal_and_symlinks(self):
        for name, symbolic in (("../outside", False), ("link", True)):
            archive = self.root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as package:
                entry = zipfile.ZipInfo(name)
                if symbolic:
                    entry.create_system = 3
                    entry.external_attr = (0o120777 << 16)
                package.writestr(entry, b"target")
            with self.subTest(name=name), self.assertRaises(ValueError):
                assets.extract_zip(archive, self.root / "out")

    def test_tar_rejects_links_even_outside_selected_prefix(self):
        archive = self.root / "bad.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            entry = tarfile.TarInfo("excluded/link")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../../outside"
            package.addfile(entry)
        with self.assertRaisesRegex(ValueError, "Unsupported archive entry"):
            assets.extract_tar(archive, self.root / "out", prefix="package/")

    def test_mathjax_keeps_dynamic_extensions_and_license_offline(self):
        archive = self.root / "fixture.tgz"
        with tarfile.open(archive, "w:gz") as package:
            for name in ("package/es5/tex-svg.js", "package/es5/input/tex/extensions/cancel.js", "package/LICENSE"):
                entry = tarfile.TarInfo(name)
                entry.size = len(self.payload)
                package.addfile(entry, io.BytesIO(self.payload))
        specification = {"filename": archive.name, "url": "https://example.invalid/fixture.tgz",
                         "sha256": assets.sha256_file(archive)}
        manifest = {"assets": {"mathjax": specification}}
        destination = self.root / "mathjax"
        with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("network")):
            result = assets.ensure_mathjax(destination, cache_dir=self.root, offline=True, manifest=manifest)
            self.assertEqual(result, destination / "es5")
            self.assertTrue((result / "input/tex/extensions/cancel.js").is_file())
            self.assertTrue((destination / "LICENSE").is_file())
            self.assertEqual(assets.ensure_mathjax(destination, cache_dir=self.root, offline=True, manifest=manifest), result)

    def test_unknown_language_fails_before_network_or_path_creation(self):
        manifest = assets.load_manifest()
        for language in ("../outside", "not-a-language"):
            with self.subTest(language=language), self.assertRaisesRegex(ValueError, "Unknown OCR language"):
                assets.language_asset(language, manifest)
        french = assets.language_asset("fra", manifest)
        self.assertIn(manifest["tessdata_commit"], french["url"])
        self.assertRegex(french["git_blob_sha1"], r"^[0-9a-f]{40}$")

    def test_manifest_pins_every_asset_and_default_model(self):
        manifest = assets.load_manifest()
        for name, specification in manifest["assets"].items():
            with self.subTest(asset=name):
                self.assertRegex(specification["sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(specification["url"].startswith("https://"))
        for language in manifest["default_languages"]:
            self.assertRegex(manifest["languages"][language]["sha256"], r"^[0-9a-f]{64}$")

    def test_environment_is_child_only_and_has_no_download_side_effects(self):
        before = dict(os.environ)
        with patch.object(native.runtime_assets.urllib.request, "urlopen", side_effect=AssertionError("network")):
            env = native.environment(native.ROOT)
        self.assertEqual(dict(os.environ), before)
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertTrue((native.ROOT / env["TESSDATA_PREFIX"]).is_relative_to(native.ROOT / ".forge"))
        self.assertTrue(Path(env["ACF_MATHJAX_DIR"]).is_relative_to(native.ROOT / ".forge"))
        self.assertEqual(Path(env["UV_PROJECT_ENVIRONMENT"]), native.ROOT / ".venv")

    @unittest.skipUnless(os.name == "nt", "Windows Tesseract needs ASCII model arguments")
    def test_windows_unicode_root_keeps_model_argument_ascii_and_relative(self):
        root = self.root / "Anki Test ä 日本語"
        (root / "tools").mkdir(parents=True)
        manifest = assets.load_manifest()
        (root / "tools/runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        env = native.environment(root)
        argument = env["TESSDATA_PREFIX"]
        self.assertTrue(argument.isascii())
        self.assertFalse(Path(argument).is_absolute())
        self.assertEqual(root / argument,
                         root / ".forge/tools" / f"tesseract-{manifest['tesseract_version']}" / "tessdata")

    def test_offline_browser_repair_refuses_network_when_cache_is_missing(self):
        browsers = self.root / "browsers"
        with patch.object(native, "_browser_executable", return_value=browsers / "chromium/chrome.exe"), \
                patch.object(native, "_browser_identity", return_value="pinned"), \
                patch.object(native.runtime_assets, "fetch_asset", side_effect=RuntimeError("Offline setup needs cached asset")) as fetch, \
                patch.object(native, "_run", side_effect=AssertionError("install")):
            with self.assertRaisesRegex(RuntimeError, "Offline setup needs cached asset"):
                native._ensure_browser({"PLAYWRIGHT_BROWSERS_PATH": str(browsers)}, offline=True, log=io.StringIO())
            self.assertTrue(fetch.call_args.kwargs["offline"])

    def test_offline_browser_reuses_verified_files_and_checks_launch(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "chrome.exe").write_bytes(self.payload)
        browsers = self.root / "browsers"
        assets._publish(stage, browsers, "pinned")
        with patch.object(native, "_browser_executable", return_value=browsers / "chrome.exe"), \
                patch.object(native, "_browser_identity", return_value="pinned"), \
                patch.object(native, "_run", side_effect=AssertionError("install")), \
                patch.object(native, "_launch_browser", return_value="148.0") as launch:
            native._ensure_browser({"PLAYWRIGHT_BROWSERS_PATH": str(browsers)}, offline=True, log=io.StringIO())
            launch.assert_called_once()

    def test_online_browser_repair_forces_reinstall_and_records_new_inventory(self):
        browsers = self.root / "browsers"
        browsers.mkdir()
        executable = browsers / "chrome.exe"
        executable.write_bytes(b"damaged")
        def repair(arguments, env, log):
            self.assertIn("--force", arguments)
            self.assertEqual(env["PLAYWRIGHT_DOWNLOAD_HOST"], "http://127.0.0.1:1234")
            self.assertEqual(fetch.call_count, 4, "Every archive must verify before installation")
            executable.write_bytes(self.payload)
        with patch.object(native, "_browser_executable", return_value=executable), \
                patch.object(native, "_browser_identity", return_value="pinned"), \
                patch.object(native.runtime_assets, "fetch_asset", return_value=executable) as fetch, \
                patch.object(native, "browser_cache_server", return_value=nullcontext("http://127.0.0.1:1234")), \
                patch.object(native, "_run", side_effect=repair), \
                patch.object(native, "_launch_browser", return_value="148.0"):
            native._ensure_browser({"PLAYWRIGHT_BROWSERS_PATH": str(browsers)}, offline=False, log=io.StringIO())
        self.assertTrue(assets._ready(browsers, "pinned", ["chrome.exe"]))

    def test_bad_browser_archive_cannot_reach_installer(self):
        browsers = self.root / "browsers"
        with patch.object(native, "_browser_executable", return_value=browsers / "chrome.exe"), \
                patch.object(native, "_browser_identity", return_value="pinned"), \
                patch.object(native.runtime_assets, "fetch_asset", side_effect=ValueError("SHA-256 mismatch")), \
                patch.object(native, "_run", side_effect=AssertionError("installer ran")):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                native._ensure_browser({"PLAYWRIGHT_BROWSERS_PATH": str(browsers)}, offline=False, log=io.StringIO())

    def test_browser_server_binds_loopback_and_only_serves_exact_manifest_paths(self):
        archive = self.root / "browser.zip"
        archive.write_bytes(self.payload)
        with patch.object(native, "ThreadingHTTPServer") as server_type, patch.object(native.threading, "Thread"):
            server_type.return_value.server_port = 1234
            with native.browser_cache_server({"/builds/browser.zip": archive}) as endpoint:
                self.assertEqual(endpoint, "http://127.0.0.1:1234")
                self.assertEqual(server_type.call_args.args[0], ("127.0.0.1", 0))
                handler_type = server_type.call_args.args[1]
                for path, allowed in (("/builds/browser.zip", True), ("/../browser.zip", False),
                                      ("/builds/browser.zip?other", False), ("/", False)):
                    handler = object.__new__(handler_type)
                    handler.path = path
                    handler.wfile = io.BytesIO()
                    with patch.object(handler, "send_response") as success, \
                            patch.object(handler, "send_error") as error, \
                            patch.object(handler, "send_header"), patch.object(handler, "end_headers"):
                        handler.do_GET()
                        if allowed:
                            success.assert_called_once_with(200)
                            self.assertEqual(handler.wfile.getvalue(), self.payload)
                        else:
                            error.assert_called_once_with(404)
                            self.assertEqual(handler.wfile.getvalue(), b"")
            server_type.return_value.shutdown.assert_called_once()
            server_type.return_value.server_close.assert_called_once()

    def test_managed_environment_removes_inherited_download_and_node_overrides(self):
        poisoned = {"UV_INDEX_URL": "https://example.invalid", "PLAYWRIGHT_DOWNLOAD_HOST": "https://example.invalid",
                    "PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST": "https://example.invalid", "NODE_OPTIONS": "--require bad.js",
                    "npm_config_playwright_download_host": "https://example.invalid", "HTTPS_PROXY": "http://proxy.invalid"}
        with patch.dict(os.environ, poisoned):
            env = native.environment(native.ROOT)
            for name in poisoned:
                if name == "HTTPS_PROXY":
                    self.assertEqual(env[name], poisoned[name])
                else:
                    self.assertNotIn(name.upper(), {key.upper() for key in env})


if __name__ == "__main__":
    unittest.main()
