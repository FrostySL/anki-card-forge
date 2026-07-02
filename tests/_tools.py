"""Loads the tools/ scripts as isolated modules for the tests.

Via importlib with a dedicated module name (`tool_<stem>`), so that
  - the tool name `coverage` does NOT collide with the PyPI package of the same name,
  - the scripts are importable without installation/path tricks.
The `if __name__ == "__main__"` guards prevent main() from running on import.
"""
import importlib.util
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def load(stem):
    spec = importlib.util.spec_from_file_location(f"tool_{stem}", TOOLS / f"{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
