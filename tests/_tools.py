"""Laedt die tools/-Skripte als isolierte Module fuer die Tests.

Per importlib mit eigenem Modulnamen (`tool_<stem>`), damit
  - der Tool-Name `coverage` NICHT mit dem gleichnamigen PyPI-Paket kollidiert,
  - die Skripte ohne Installation/Pfad-Tricks importierbar sind.
Die `if __name__ == "__main__"`-Guards verhindern, dass main() beim Import laeuft.
"""
import importlib.util
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def load(stem):
    spec = importlib.util.spec_from_file_location(f"tool_{stem}", TOOLS / f"{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
