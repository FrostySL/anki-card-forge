"""Exercise the actual inbox-PowerShell launcher from a tiny clean Windows copy."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = Path(os.environ.get("SystemRoot", "C:/Windows"))
POWERSHELL = WINDOWS / "System32/WindowsPowerShell/v1.0/powershell.exe"
CMD = WINDOWS / "System32/cmd.exe"


@unittest.skipUnless(os.name == "nt" and POWERSHELL.is_file(), "Windows inbox PowerShell is required")
class WindowsBootstrap(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="acf-bootstrap-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Anki Test ä"
        (self.root / "tools").mkdir(parents=True)
        for name in ("forge.cmd", "tools/bootstrap.ps1", "tools/runtime-manifest.json"):
            shutil.copyfile(ROOT / name, self.root / name)
        self.env = {key: value for key, value in os.environ.items() if not re.match(
            r"^(UV_|PYTHON|PLAYWRIGHT_|ACF_|PIP_|VIRTUAL_ENV$|TESSDATA_PREFIX$|TESSERACT_|NODE_|npm_)",
            key, re.IGNORECASE)}
        # Hosted Windows places Docker in System32, so that directory must not
        # enter the child search path. Required inbox tools use absolute paths.
        self.env["PATH"] = str(POWERSHELL.parent)
        # No project helper or parent interpreter can be discovered by the child.
        for name in ("python", "python3", "py", "uv", "docker", "git", "tesseract"):
            self.assertIsNone(shutil.which(name, path=self.env["PATH"]), name)

    def launch(self, *arguments):
        # cmd /s /c needs an outer quote pair around the entire invocation as
        # well as the executable's quote pair when its path contains spaces.
        invocation = subprocess.list2cmdline([str(self.root / "forge.cmd"), *arguments])
        return subprocess.run(f'"{CMD}" /d /s /c "{invocation}"', cwd=self.root,
                              env=self.env, capture_output=True, text=True,
                              encoding="utf-8", timeout=30)

    def assert_clean(self):
        self.assertFalse((self.root / ".forge").exists())
        self.assertFalse((self.root / ".venv").exists())

    def test_cold_doctor_json_is_read_only(self):
        result = self.launch("doctor", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report["ready"], False)
        self.assertIn("Managed runtime is missing", report["error"])
        self.assertIn("forge.cmd setup", report["error"])
        self.assert_clean()

    def test_cold_command_explains_setup_without_downloading(self):
        result = self.launch("build", "decks/example cards ä.cards.json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Managed runtime is missing", result.stdout)
        self.assertIn("forge.cmd setup", result.stdout)
        self.assertNotIn("Downloading", result.stdout)
        self.assert_clean()

    def test_cold_help_lists_diff_and_test_without_setup(self):
        result = self.launch("--help")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Commands:", result.stdout)
        self.assertRegex(result.stdout, r"\bdiff\b")
        self.assertRegex(result.stdout, r"\btest\b")
        self.assert_clean()

    def test_cold_offline_setup_stops_at_cache_miss(self):
        result = self.launch("setup", "--offline")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        manifest = json.loads((self.root / "tools/runtime-manifest.json").read_text(encoding="utf-8"))
        self.assertIn("Offline setup needs cached asset: " + manifest["assets"]["uv"]["filename"], result.stdout)
        self.assertIn("Run setup once with internet access", result.stdout)
        self.assertNotIn("Downloading", result.stdout)
        self.assertEqual(list((self.root / ".forge/cache/downloads").iterdir()), [])
        self.assertFalse((self.root / ".forge/python").exists())
        self.assertFalse((self.root / ".forge/uv").exists())
        self.assertFalse((self.root / ".venv").exists())

    def acceptance_fixture(self):
        driver = self.root / "tests/integration/windows_acceptance.ps1"
        driver.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "tests/integration/windows_acceptance.ps1", driver)
        # Stop immediately after preflight; these tests must never install tools.
        (self.root / "forge.cmd").write_bytes(
            b'@echo off\r\necho called>"%~dp0setup-called.txt"\r\nexit /b 23\r\n')
        reports = Path(self.temporary.name) / "reports"
        return driver, reports

    def test_acceptance_preflight_excludes_system32_and_tolerates_case_variant_environment(self):
        driver, reports = self.acceptance_fixture()
        self.env["FORGE_DUPLICATE"] = "first"
        self.env["forge_duplicate"] = "second"
        result = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 str(driver), "-ReportDir", str(reports)], cwd=self.root, env=self.env,
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Cold setup failed: 23", result.stdout + result.stderr)
        self.assertTrue((self.root / "setup-called.txt").is_file())
        before = json.loads((reports / "before.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(before["path"], str(POWERSHELL.parent))
        self.assertTrue(all(not commands for commands in before["tools"].values()), before)
        self.assert_clean()

    def test_acceptance_still_rejects_host_command_and_retains_resolution(self):
        driver, reports = self.acceptance_fixture()
        wrapper = self.root / "probe.ps1"
        wrapper.write_text("function docker { throw 'Host tool must never be called' }\n"
                           "& (Join-Path $PSScriptRoot 'tests/integration/windows_acceptance.ps1') "
                           "-ReportDir (Join-Path (Split-Path $PSScriptRoot -Parent) 'reports')\n",
                           encoding="utf-8-sig")
        result = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                                cwd=self.root, env=self.env, capture_output=True, text=True,
                                encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unexpectedly resolves host tools: docker", result.stdout + result.stderr)
        self.assertFalse((self.root / "setup-called.txt").exists())
        before = json.loads((reports / "before.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(before["tools"]["docker"][0]["command_type"], "Function")
        self.assert_clean()

    def test_child_environment_tolerates_case_variant_inherited_keys(self):
        # Windows process blocks can contain both spellings, e.g. after CMD.
        # PowerShell 5's Env: enumeration fails on this valid inherited block.
        self.env["FORGE_DUPLICATE"] = "first"
        self.env["forge_duplicate"] = "second"
        self.env["UV_INDEX_URL"] = "https://example.invalid"
        script = self.root / "tools" / "check-environment.ps1"
        script.write_text("""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$tree = [Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot 'bootstrap.ps1'), [ref]$tokens, [ref]$errors)
$definition = $tree.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Set-ChildEnvironment'
}, $true)
Invoke-Expression $definition.Extent.Text
$projectRoot = Split-Path -Parent $PSScriptRoot
$managedRoot = Join-Path $projectRoot '.forge'
$manifest = @{ tesseract_version = 'fixture' }
Set-ChildEnvironment
if ([Environment]::GetEnvironmentVariable('UV_INDEX_URL')) { throw 'Inherited uv override survived' }
if ($env:PYTHONUTF8 -ne '1') { throw 'Managed environment was not applied' }
Write-Output 'PASS: duplicate-case environment'
""", encoding="utf-8-sig")
        result = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                cwd=self.root, env=self.env, capture_output=True, text=True,
                                encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: duplicate-case environment", result.stdout)
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
