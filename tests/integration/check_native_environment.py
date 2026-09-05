"""Assert managed dependency provenance in a fresh Python process (Windows)."""
import argparse
import ctypes
import importlib
import json
from pathlib import Path
import sys


def under(path, directory):
    return Path(path).resolve().is_relative_to(directory.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    env = root / ".venv"
    assert under(sys.executable, env), f"Unmanaged interpreter: {sys.executable}"
    assert under(sys.base_prefix, root / ".forge"), f"Unmanaged base Python: {sys.base_prefix}"
    modules = {}
    for name in ("genanki", "pymupdf", "pymupdf4llm", "onnxruntime", "PIL", "playwright", "anki.collection", "zstandard"):
        module = importlib.import_module(name)
        assert module.__file__ and under(module.__file__, env), f"Unmanaged {name}: {module.__file__}"
        modules[name] = module.__file__
    runtimes = {}
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel.GetModuleHandleW.restype = ctypes.c_void_p
        kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
        kernel.GetModuleFileNameW.restype = ctypes.c_ulong
        for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
            handle = kernel.GetModuleHandleW(name)
            assert handle, f"Runtime was not loaded: {name}"
            path = ctypes.create_unicode_buffer(32768)
            assert kernel.GetModuleFileNameW(handle, path, len(path)), f"Cannot inspect {name}"
            assert under(path.value, root / ".forge") or under(path.value, env), \
                f"Native dependency came from the host: {name}: {path.value}"
            runtimes[name] = path.value
    report = {"executable": sys.executable, "base_prefix": sys.base_prefix,
              "modules": modules, "runtime_dlls": runtimes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS: interpreter, native packages and loaded VC runtimes belong to this project")


if __name__ == "__main__":
    main()
