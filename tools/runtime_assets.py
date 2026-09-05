#!/usr/bin/env python3
"""Fetch pinned runtime assets; importing this module never downloads anything.

Archives are verified before extraction/execution. Installers are opened as
archives, never installed. All modifications stay in explicitly supplied local
runtime/cache directories. The MathJax helper also works in the preview image.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile


MANIFEST_PATH = Path(__file__).with_name("runtime-manifest.json")


def load_manifest(path=MANIFEST_PATH):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path):
    return _file_digest(path, "sha256").hexdigest()


def _file_digest(path, algorithm):
    # Keep the stdlib-only Linux test/tools baseline (Python 3.10).
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest


def verify_asset(path, asset):
    """Raise on a changed payload, including extra language Git blob identities."""
    path = Path(path)
    if "size" in asset and path.stat().st_size != asset["size"]:
        raise ValueError(f"Size mismatch for {path.name}")
    if "sha256" in asset and sha256_file(path) != asset["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path.name}")
    if "sha512_base64" in asset:
        digest = _file_digest(path, "sha512").digest()
        if base64.b64encode(digest).decode("ascii") != asset["sha512_base64"]:
            raise ValueError(f"SHA-512 mismatch for {path.name}")
    if "git_blob_sha1" in asset:
        digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode("ascii"))
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != asset["git_blob_sha1"]:
            raise ValueError(f"Pinned Git object mismatch for {path.name}")
    if not any(key in asset for key in ("sha256", "sha512_base64", "git_blob_sha1")):
        raise ValueError("Runtime assets must have an expected content digest")


def fetch_asset(asset, cache_dir, *, offline=False):
    """Download atomically; reuse only a cache entry whose content still matches."""
    cache = Path(cache_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    name = asset["filename"]
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
        raise ValueError("Asset cache filenames must be single safe path components")
    destination = cache / name
    if destination.is_file():
        try:
            verify_asset(destination, asset)
            return destination
        except ValueError:
            if offline:
                raise ValueError(f"Cached asset is damaged: {destination}; rerun setup online") from None
    elif offline:
        raise RuntimeError(f"Offline setup needs cached asset {name}; run setup online once")
    if not asset["url"].startswith("https://"):
        raise ValueError("Runtime asset downloads require HTTPS")
    descriptor, partial_name = tempfile.mkstemp(prefix=name + ".part-", dir=cache)
    partial = Path(partial_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            print(f"Downloading {name}...", flush=True)
            request = urllib.request.Request(asset["url"], headers={"User-Agent": "anki-card-forge-setup/1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, output)
        verify_asset(partial, asset)
        os.replace(partial, destination)
    except (OSError, urllib.error.URLError) as error:
        raise RuntimeError(f"Download failed for {name}: {error}. Rerun setup to retry.") from error
    finally:
        partial.unlink(missing_ok=True)
    return destination


def archive_target(destination, name):
    """Normalize ZIP/TAR names safely even when tested on a non-Windows host."""
    name = name.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or ".." in parts or any(":" in part for part in parts):
        raise ValueError(f"Unsafe archive path: {name!r}")
    root = Path(destination).resolve()
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Archive path escapes destination: {name!r}")
    return target


def extract_zip(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            target = archive_target(destination, entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError(f"Archive symlinks are not allowed: {entry.filename}")
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


def extract_tar(archive, destination, *, prefix=""):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as package:
        for entry in package:
            # Validate even excluded entries, and never materialize archive links.
            archive_target(destination, entry.name)
            if not entry.isfile() and not entry.isdir():
                raise ValueError(f"Unsupported archive entry: {entry.name}")
            if prefix and not entry.name.startswith(prefix):
                continue
            name = entry.name[len(prefix):]
            if not name:
                continue
            target = archive_target(destination, name)
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.extractfile(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


def _ready(destination, identity, required):
    stamp = Path(destination) / ".asset.json"
    try:
        installed = json.loads(stamp.read_text(encoding="utf-8"))
        files = installed.get("files")
        if (installed.get("schema") != 1 or installed["identity"] != identity or not isinstance(files, dict)
                or not files or not all(name in files for name in required)):
            return False
        # Check the payload, not only the marker: a deleted dynamic JS component
        # or dependent DLL must be repairable by rerunning setup from its cache.
        # Added OCR models are verified separately by ensure_languages().
        for name, digest in files.items():
            target = archive_target(destination, name)
            if target.is_symlink() or not target.is_file() or sha256_file(target) != digest:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def staging_directory(parent, prefix):
    # tempfile.mkdtemp() requests mode 0700. Recent Windows Python enforces that
    # as a private ACL, which survives rename and prevents assistant sandbox
    # processes from using the installed tools. These are public runtime assets:
    # inherit the ordinary project-directory permissions, just like downloads.
    path = Path(parent) / (prefix + uuid.uuid4().hex)
    path.mkdir()
    return path


def _publish(stage, destination, identity):
    """Publish a complete version; retain an older/incomplete tree for diagnosis."""
    stage, destination = Path(stage).resolve(), Path(destination).resolve()
    if stage.parent != destination.parent:
        raise ValueError("Staging and destination must share a managed parent")
    files = {}
    for path in sorted(stage.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Runtime payload symlinks are not allowed: {path}")
        if path.is_file() and path.name != ".asset.json":
            files[path.relative_to(stage).as_posix()] = sha256_file(path)
    (stage / ".asset.json").write_text(json.dumps({"schema": 1, "identity": identity, "files": files}) + "\n", encoding="utf-8")
    old = None
    if destination.exists():
        old = staging_directory(destination.parent, destination.name + "-previous-")
        old.rmdir()
        os.replace(destination, old)
    try:
        os.replace(stage, destination)
    except OSError:
        if old is not None and not destination.exists():
            os.replace(old, destination)
        raise


def _run_archive_tool(executable, archive, destination):
    result = subprocess.run([str(executable), "x", str(archive), f"-o{destination}", "-y"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", check=False)
    if result.returncode:
        raise RuntimeError(f"Archive extraction failed ({result.returncode}):\n{result.stdout}")


def ensure_tesseract(managed_root, *, offline=False, manifest=None):
    manifest = manifest or load_manifest()
    managed = Path(managed_root).resolve()
    tools = managed / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    cache = managed / "cache" / "downloads"
    destination = tools / f"tesseract-{manifest['tesseract_version']}"
    tess_asset = manifest["assets"]["tesseract"]
    if _ready(destination, tess_asset["sha256"], ["tesseract.exe", "libtesseract-5.dll"]):
        return destination
    sevenzip = tools / f"7zip-{manifest['sevenzip_version']}"
    sevenzip_asset = manifest["assets"]["sevenzip"]
    if not _ready(sevenzip, sevenzip_asset["sha256"], ["7z.exe", "7z.dll"]):
        sevenzr_file = fetch_asset(manifest["assets"]["sevenzr"], cache, offline=offline)
        sevenzip_file = fetch_asset(sevenzip_asset, cache, offline=offline)
        stage = staging_directory(tools, "7zip-stage-")
        _run_archive_tool(sevenzr_file, sevenzip_file, stage)
        if not (stage / "7z.exe").is_file() or not (stage / "7z.dll").is_file():
            raise RuntimeError(f"Unexpected 7-Zip archive layout; retained at {stage}")
        _publish(stage, sevenzip, sevenzip_asset["sha256"])
    installer = fetch_asset(tess_asset, cache, offline=offline)
    stage = staging_directory(tools, "tesseract-stage-")
    # Do not execute the installer: its NSIS payload includes all runtime DLLs.
    _run_archive_tool(sevenzip / "7z.exe", installer, stage)
    if not (stage / "tesseract.exe").is_file() or not (stage / "libtesseract-5.dll").is_file():
        raise RuntimeError(f"Unexpected Tesseract archive layout; retained at {stage}")
    _publish(stage, destination, tess_asset["sha256"])
    return destination


def language_asset(language, manifest):
    try:
        identity = manifest["languages"][language]
    except KeyError:
        raise ValueError(f"Unknown OCR language {language!r}; use a code from the pinned tessdata_fast models") from None
    commit = manifest["tessdata_commit"]
    return dict(identity,
                filename=f"tessdata-{language.replace('/', '_')}-{commit[:12]}.traineddata",
                url=f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{commit}/{language}.traineddata")


def ensure_languages(tesseract_dir, languages, cache_dir, *, offline=False, manifest=None):
    manifest = manifest or load_manifest()
    tessdata = Path(tesseract_dir) / "tessdata"
    tessdata.mkdir(parents=True, exist_ok=True)
    for language in sorted(set(languages)):
        asset = language_asset(language, manifest)
        target = archive_target(tessdata, language + ".traineddata")
        if target.is_file():
            try:
                verify_asset(target, asset)
                continue
            except ValueError:
                pass
        cached = fetch_asset(asset, cache_dir, offline=offline)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".traineddata.part")
        shutil.copyfile(cached, temporary)
        os.replace(temporary, target)
    return tessdata


def ensure_mathjax(destination, *, cache_dir=None, offline=False, manifest=None):
    manifest = manifest or load_manifest()
    destination = Path(destination).resolve()
    asset = manifest["assets"]["mathjax"]
    if _ready(destination, asset["sha256"], ["es5/tex-svg.js", "LICENSE"]):
        return destination / "es5"
    cached = fetch_asset(asset, cache_dir or destination.parent / ".downloads", offline=offline)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = staging_directory(destination.parent, "mathjax-stage-")
    extract_tar(cached, stage, prefix="package/")
    if not (stage / "es5" / "tex-svg.js").is_file() or not (stage / "LICENSE").is_file():
        raise RuntimeError(f"Unexpected MathJax archive layout; retained at {stage}")
    _publish(stage, destination, asset["sha256"])
    return destination / "es5"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    mathjax = commands.add_parser("ensure-mathjax", help="Install verified local MathJax for previews")
    mathjax.add_argument("--dest", required=True, type=Path, help="Parent directory of the resulting es5/ tree")
    mathjax.add_argument("--cache-dir", type=Path)
    mathjax.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(ensure_mathjax(args.dest, cache_dir=args.cache_dir, offline=args.offline))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Runtime asset error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
