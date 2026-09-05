"""Loads the tools/ scripts as isolated modules for the tests.

Via importlib with a dedicated module name (`tool_<stem>`), so that
  - the tool name `coverage` does NOT collide with the PyPI package of the same name,
  - the scripts are importable without installation/path tricks.
The `if __name__ == "__main__"` guards prevent main() from running on import.
"""
import importlib.util
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def load(stem):
    spec = importlib.util.spec_from_file_location(f"tool_{stem}", TOOLS / f"{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    # Standalone tools can import their shared siblings just as they do when
    # run with `python tools/name.py`.
    sys.path.insert(0, str(TOOLS))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod
