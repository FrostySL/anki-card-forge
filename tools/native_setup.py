#!/usr/bin/env python3
"""Managed Windows setup and read-only diagnostics. No work happens on import."""
import argparse
import base64
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit

import runtime_assets


ROOT = Path(__file__).resolve().parents[1]


def environment(root):
    """Return child-only settings; never install, touch files, or change os.environ."""
    root = Path(root).resolve()
    manifest = runtime_assets.load_manifest(root / "tools" / "runtime-manifest.json")
    managed = root / ".forge"
    windows = os.name == "nt"
    scripts = root / ".venv" / ("Scripts" if windows else "bin")
    tesseract = managed / "tools" / f"tesseract-{manifest['tesseract_version']}"
    result = dict(os.environ)
    for name in list(result):
        if (name.upper().startswith(("UV_", "PLAYWRIGHT_", "NPM_CONFIG_PLAYWRIGHT_", "NPM_PACKAGE_CONFIG_PLAYWRIGHT_"))
                or name.upper() in ("NODE_OPTIONS", "NODE_PATH")):
            result.pop(name)
    result.pop("PYTHONHOME", None)
    result.pop("PYTHONPATH", None)
    result.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "VIRTUAL_ENV": str(root / ".venv"),
        "UV_PROJECT_ENVIRONMENT": str(root / ".venv"),
        "UV_CACHE_DIR": str(managed / "cache" / "uv"),
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_LINK_MODE": "copy",
        "PLAYWRIGHT_BROWSERS_PATH": str(managed / "browsers"),
        "TESSDATA_PREFIX": str(tesseract / "tessdata"),
        "ACF_MATHJAX_DIR": str(managed / "assets" / f"mathjax-{manifest['mathjax_version']}" / "es5"),
        "PATH": os.pathsep.join((str(scripts), str(tesseract), str(managed / "python"), result.get("PATH", ""))),
    })
    return result


def _capture(arguments, env, *, timeout=60):
    result = subprocess.run(list(map(str, arguments)), cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{Path(arguments[0]).name} exited {result.returncode}: {result.stdout.strip()}")
    return result.stdout.strip()


def _browser_executable(env):
    # Ask the pinned Playwright package in a child: no inherited/global browser.
    code = ("from playwright.sync_api import sync_playwright; "
            "p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()")
    return Path(_capture([sys.executable, "-c", code], env).splitlines()[-1])


def _browser_identity():
    specification = Path(importlib.metadata.distribution("playwright").locate_file(
        "playwright/driver/package/browsers.json"))
    digest = runtime_assets.sha256_file(specification)
    manifest = runtime_assets.load_manifest()
    if digest != manifest["browser"]["specification_sha256"]:
        raise RuntimeError("The installed Playwright browser specification differs from the pinned manifest.")
    archives = ":".join(manifest["assets"][name]["sha256"] for name in manifest["browser"]["assets"])
    return "playwright-" + importlib.metadata.version("playwright") + ":" + digest + ":" + archives


def _launch_browser(env):
    code = ("from playwright.sync_api import sync_playwright; "
            "p=sync_playwright().start(); b=p.chromium.launch(); "
            "print(b.version); b.close(); p.stop()")
    return _capture([sys.executable, "-c", code], env)


def _record_browser_inventory(directory, identity):
    directory = Path(directory).resolve()
    files = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected browser runtime symlink: {path}")
        if path.is_file() and path.name not in (".asset.json", ".asset.json.part"):
            files[path.relative_to(directory).as_posix()] = runtime_assets.sha256_file(path)
    part = directory / ".asset.json.part"
    part.write_text(json.dumps({"schema": 1, "identity": identity, "files": files}) + "\n", encoding="utf-8")
    os.replace(part, directory / ".asset.json")


@contextmanager
def browser_cache_server(files):
    """Expose only preverified archives to the pinned installer over loopback.

    Playwright still owns its platform-specific extraction/layout/markers. Its
    downloader can only reach these exact local URLs during installation; it
    never downloads an unchecked browser archive from an external host.
    """
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = urlsplit(self.path)
            path = files.get(request.path)
            if path is None or request.query or request.fragment:
                self.send_error(404)
                return
            try:
                with Path(path).open("rb") as source:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Length", str(os.fstat(source.fileno()).st_size))
                    self.end_headers()
                    shutil.copyfileobj(source, self.wfile)
            except (OSError, BrokenPipeError):
                self.close_connection = True

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _ensure_browser(env, *, offline, log):
    directory = Path(env["PLAYWRIGHT_BROWSERS_PATH"])
    executable = _browser_executable(env)
    identity = _browser_identity()
    relative = executable.relative_to(directory).as_posix()
    complete = runtime_assets._ready(directory, identity, [relative])
    if complete:
        try:
            _launch_browser(env)
            return
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            complete = False
    manifest = runtime_assets.load_manifest()
    cache = ROOT / ".forge" / "cache" / "downloads"
    files = {}
    # Every download is complete and matches the committed SHA-256 before the
    # installer runs or any executable from the archive can be launched.
    for name in manifest["browser"]["assets"]:
        asset = manifest["assets"][name]
        files[asset["installer_path"]] = runtime_assets.fetch_asset(asset, cache, offline=offline)
    arguments = [sys.executable, "-m", "playwright", "install", "chromium"]
    if executable.exists():
        arguments.insert(-1, "--force")
    with browser_cache_server(files) as endpoint:
        install_env = dict(env)
        install_env["PLAYWRIGHT_DOWNLOAD_HOST"] = endpoint
        install_env["PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST"] = endpoint
        # Local cache requests must not be routed through a user proxy.
        install_env["NO_PROXY"] = "127.0.0.1,localhost"
        install_env["no_proxy"] = "127.0.0.1,localhost"
        _run(arguments, install_env, log)
    _launch_browser(env)
    _record_browser_inventory(directory, identity)


def _run(arguments, env, log):
    command = list(map(str, arguments))
    label = "+ " + subprocess.list2cmdline(command)
    print(label, flush=True)
    log.write(label + "\n")
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        status = process.wait()
    if status:
        raise RuntimeError(f"{Path(command[0]).name} failed with exit code {status}; see {log.name}")


def package_integrity(root=ROOT):
    """Verify immutable installed wheel payloads, including transitive packages.

    RECORD itself and generated bytecode intentionally have no expected hashes.
    uv checks missing distribution metadata; this additionally catches a removed
    module/DLL when an otherwise healthy .dist-info directory still exists.
    """
    venv = (Path(root) / ".venv").resolve()
    site = venv / "Lib" / "site-packages"
    damaged = {}
    checked = 0
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        checked += 1
        label = "<invalid-metadata>"
        problems = []
        try:
            name = distribution.metadata.get("Name", "")
            if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                label = name
            record = distribution.read_text("RECORD")
            if not record:
                problems.append("The installed wheel RECORD is missing or empty.")
            # Distribution.files filters nonexistent files on recent Python;
            # parse RECORD directly so missing modules are actually detected.
            for row in csv.reader((record or "").splitlines()):
                if len(row) != 3:
                    raise ValueError("Invalid RECORD row")
                entry, recorded_hash, recorded_size = row
                if not recorded_hash or entry.lower().endswith(".pyc"):
                    continue
                algorithm, separator, expected = recorded_hash.partition("=")
                if not separator or not expected:
                    raise ValueError(f"Invalid RECORD digest: {entry}")
                path = Path(distribution.locate_file(entry)).resolve()
                if not path.is_relative_to(venv) or not path.is_file():
                    problems.append(f"Missing or invalid installed path: {entry}")
                elif recorded_size and path.stat().st_size != int(recorded_size):
                    problems.append(f"Installed size mismatch: {entry}")
                else:
                    digest = runtime_assets._file_digest(path, algorithm).digest()
                    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
                    if encoded != expected:
                        problems.append(f"Installed hash mismatch: {entry}")
                if len(problems) >= 5:
                    break
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            problems.append(f"Cannot verify installed wheel RECORD: {error}")
        if label == "<invalid-metadata>":
            problems.append("The installed distribution metadata has no valid package name.")
        if problems:
            damaged[label] = problems
    return {"checked": checked, "damaged": damaged}


def repair_packages(*, offline=False):
    if sys.platform != "win32":
        raise RuntimeError("Managed package repair is only supported by the Windows bootstrap.")
    report = package_integrity()
    if not report["damaged"]:
        print(f"Verified {report['checked']} installed Python package payloads.")
        return 0
    command = [ROOT / ".forge" / "uv" / "uv.exe", "sync", "--locked", "--no-config",
               "--python", ROOT / ".forge" / "python" / "python.exe", "--no-python-downloads"]
    if "<invalid-metadata>" in report["damaged"]:
        command.append("--reinstall")
    else:
        for name in sorted(report["damaged"]):
            command.extend(["--reinstall-package", name])
    if offline:
        command.append("--offline")
    logs = ROOT / ".forge" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with (logs / f"package-repair-{timestamp}.log").open("w", encoding="utf-8") as log:
        log.write(json.dumps(report, indent=2) + "\n")
        print("Repairing installed Python packages: " + ", ".join(sorted(report["damaged"])), flush=True)
        _run(command, environment(ROOT), log)
    repaired = package_integrity()
    if repaired["damaged"]:
        raise RuntimeError("Installed package repair did not pass verification: " + json.dumps(repaired["damaged"]))
    print(f"Verified {repaired['checked']} installed Python package payloads after repair.")
    return 0


def diagnose(root=ROOT, *, require_state=True):
    # Only the Windows managed interpreter runs diagnostics; importing the
    # module for Linux's stdlib tests must still work on Python 3.10.
    import tomllib

    root = Path(root).resolve()
    env = environment(root)
    manifest = runtime_assets.load_manifest(root / "tools" / "runtime-manifest.json")
    managed = root / ".forge"
    issues = []
    report = {
        "ready": False,
        "root": str(root),
        "platform": {"system": platform.system(), "machine": platform.machine(),
                     "windows_build": sys.getwindowsversion().build if sys.platform == "win32" else None},
        "python": {"executable": sys.executable, "base_executable": getattr(sys, "_base_executable", ""),
                   "prefix": sys.prefix, "version": platform.python_version()},
        "paths": {"managed_root": str(managed), "venv": str(root / ".venv"),
                  "uv": str(managed / "uv" / "uv.exe"),
                  "base_python": str(managed / "python" / "python.exe"),
                  "tesseract": str(Path(env["TESSDATA_PREFIX"]).parent / "tesseract.exe"),
                  "tessdata": env["TESSDATA_PREFIX"], "browsers": env["PLAYWRIGHT_BROWSERS_PATH"],
                  "mathjax": env["ACF_MATHJAX_DIR"]},
        "versions": {}, "packages": {}, "languages": [], "issues": issues,
        "manifest_sha256": runtime_assets.sha256_file(root / "tools" / "runtime-manifest.json"),
        "lock_sha256": runtime_assets.sha256_file(root / "uv.lock") if (root / "uv.lock").is_file() else None,
    }
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        issues.append("The managed native runtime currently supports Windows 11 x64.")
    if platform.python_version() != manifest["python_version"]:
        issues.append(f"Expected Python {manifest['python_version']}; run forge.cmd setup.")
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        issues.append("This process is not using the project's .venv interpreter; use forge.cmd.")
    with (root / "pyproject.toml").open("rb") as stream:
        requirements = tomllib.load(stream)["project"]["dependencies"]
    for requirement in requirements:
        name, expected = requirement.split("==", 1)
        try:
            actual = importlib.metadata.version(name)
            report["packages"][name] = actual
            if actual != expected:
                issues.append(f"{name}: expected {expected}, found {actual}.")
        except importlib.metadata.PackageNotFoundError:
            issues.append(f"Python package is missing: {name}.")
    report["package_integrity"] = package_integrity(root)
    for name, problems in report["package_integrity"]["damaged"].items():
        issues.append(f"{name}: installed package payload is damaged ({problems[0]}). Run forge.cmd setup to repair it.")
    for name, arguments in (
        ("uv", [report["paths"]["uv"], "--version"]),
        ("tesseract", [report["paths"]["tesseract"], "--version"]),
    ):
        try:
            report["versions"][name] = _capture(arguments, env).splitlines()[0]
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            issues.append(f"{name}: {error}")
    if not runtime_assets._ready(Path(report["paths"]["tesseract"]).parent,
                                 manifest["assets"]["tesseract"]["sha256"], ["tesseract.exe", "libtesseract-5.dll"]):
        issues.append("Tesseract's installed file inventory is incomplete or changed; rerun setup to repair it.")
    try:
        output = _capture([report["paths"]["tesseract"], "--tessdata-dir", env["TESSDATA_PREFIX"], "--list-langs"], env)
        report["languages"] = output.splitlines()[1:]
        for language in manifest["default_languages"]:
            if language not in report["languages"]:
                issues.append(f"OCR language is missing: {language}.")
        for language in report["languages"]:
            runtime_assets.verify_asset(Path(env["TESSDATA_PREFIX"]) / (language + ".traineddata"),
                                        runtime_assets.language_asset(language, manifest))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        issues.append(f"OCR language check: {error}")
    try:
        browser = _browser_executable(env)
        report["paths"]["chromium"] = str(browser)
        if not browser.is_file() or not browser.resolve().is_relative_to(managed.resolve()):
            issues.append("The project-managed Chromium executable is missing.")
        else:
            report["versions"]["chromium"] = _launch_browser(env)
            relative = browser.relative_to(Path(env["PLAYWRIGHT_BROWSERS_PATH"])).as_posix()
            if not runtime_assets._ready(Path(env["PLAYWRIGHT_BROWSERS_PATH"]), _browser_identity(), [relative]):
                issues.append("Chromium's installed file inventory is incomplete or changed; rerun setup online to repair it.")
    except (OSError, RuntimeError, subprocess.TimeoutExpired, IndexError) as error:
        issues.append(f"Chromium check: {error}")
    if not runtime_assets._ready(Path(env["ACF_MATHJAX_DIR"]).parent, manifest["assets"]["mathjax"]["sha256"],
                                 ["es5/tex-svg.js", "LICENSE"]):
        issues.append("Local MathJax is missing or changed; rerun setup to repair offline formula previews.")
    for folder in (managed / "python", root / ".venv" / "Scripts"):
        for dll in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            if not (folder / dll).is_file():
                issues.append(f"App-local Microsoft runtime is missing: {folder / dll}")
    state_file = managed / "setup-state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        report["last_setup"] = state
        if require_state and (state.get("manifest_sha256") != report["manifest_sha256"]
                              or state.get("lock_sha256") != report["lock_sha256"]
                              or state.get("root") != str(root)):
            issues.append("Setup state is outdated or the project moved; rerun forge.cmd setup.")
    except (OSError, ValueError):
        if require_state:
            issues.append("No successful full setup is recorded; run forge.cmd setup.")
    report["ready"] = not issues
    return report


def setup(args):
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Native setup currently supports Windows 11 x64. Use the existing Docker workflow elsewhere.")
    manifest = runtime_assets.load_manifest()
    managed = ROOT / ".forge"
    if not (managed / "python" / "python.exe").is_file() or Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("Start setup with .\\forge.cmd setup so the verified Python runtime is bootstrapped first.")
    languages = set(manifest["default_languages"])
    try:
        prior_state = json.loads((managed / "setup-state.json").read_text(encoding="utf-8"))
        languages.update(prior_state.get("languages", []))
    except (OSError, ValueError):
        pass
    for specification in args.lang or []:
        languages.update(language for language in specification.split("+") if language)
    # Validate names before fetching anything.
    for language in languages:
        runtime_assets.language_asset(language, manifest)
    logs = managed / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"setup-{timestamp}.log"
    env = environment(ROOT)
    with log_path.open("w", encoding="utf-8") as log:
        print(f"Setting up Windows tools. Log: {log_path}", flush=True)
        git = shutil.which("git", path=env["PATH"])
        if git and (ROOT / ".git").exists():
            _run([git, "config", "core.hooksPath", ".githooks"], env, log)
        tesseract = runtime_assets.ensure_tesseract(managed, offline=args.offline, manifest=manifest)
        runtime_assets.ensure_languages(tesseract, languages, managed / "cache" / "downloads",
                                       offline=args.offline, manifest=manifest)
        runtime_assets.ensure_mathjax(managed / "assets" / f"mathjax-{manifest['mathjax_version']}",
                                      cache_dir=managed / "cache" / "downloads", offline=args.offline, manifest=manifest)
        _ensure_browser(env, offline=args.offline, log=log)
        report = diagnose(require_state=False)
        if report["issues"]:
            raise RuntimeError("Runtime checks failed:\n- " + "\n- ".join(report["issues"]))
        for check in ("build", "visual"):
            _run([sys.executable, ROOT / "tests" / "integration" / "check_pipeline.py",
                  check, "--backend", "native"], env, log)
        state = {
            "schema": 1, "completed_at": datetime.now(timezone.utc).isoformat(),
            "root": str(ROOT), "python": sys.executable, "python_version": platform.python_version(),
            "manifest_sha256": report["manifest_sha256"], "lock_sha256": report["lock_sha256"],
            "languages": report["languages"], "checks": {"runtime": "passed", "build": "passed", "visual": "passed"},
            "offline": args.offline, "log": str(log_path),
        }
        temporary = managed / "setup-state.json.part"
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, managed / "setup-state.json")
        notices = ["Downloaded locally from upstream; no third-party binaries are part of this repository."]
        notices += [f"{name}: {asset['license']}\n  Source: {asset['source']}\n  SHA-256: {asset['sha256']}"
                    for name, asset in manifest["assets"].items()]
        notices.append(f"OCR models: Apache-2.0; https://github.com/tesseract-ocr/tessdata_fast/tree/{manifest['tessdata_commit']}")
        (managed / "THIRD-PARTY-NOTICES.txt").write_text("\n\n".join(notices) + "\n", encoding="utf-8")
    print("Setup passed: OCR, offline formula preview, package build and real Anki validation.", flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup_parser = commands.add_parser("setup", help="Complete managed runtime and run the pipeline checks")
    setup_parser.add_argument("--offline", action="store_true", help="Use already installed or verified cached assets only")
    setup_parser.add_argument("--lang", action="append", help="Add OCR languages, e.g. eng+deu+fra (repeatable)")
    doctor_parser = commands.add_parser("doctor", help="Read-only runtime and executable provenance checks")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    repair_parser = commands.add_parser("repair-packages", help="Internal bootstrap step: verify and repair installed wheel payloads")
    repair_parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            return setup(args)
        if args.command == "repair-packages":
            return repair_packages(offline=args.offline)
        report = diagnose()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Managed runtime ready." if report["ready"] else "Managed runtime needs setup:")
            for issue in report["issues"]:
                print(f"- {issue}")
            print(f"Python: {report['python']['executable']}")
            print(f"OCR languages: {', '.join(report['languages']) or 'none'}")
        return 0 if report["ready"] else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Native setup error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
