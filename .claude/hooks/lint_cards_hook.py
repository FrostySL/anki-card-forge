#!/usr/bin/env python3
"""PostToolUse hook: lint a cards.json right after it was written.

Wired up in .claude/settings.json (matcher Write|Edit). Reads the hook event
from stdin; if the written file is a *.cards.json, tools/lint_cards.py runs
immediately. Exit 2 feeds the lint output back to Claude as feedback — the
structure check happens at write time instead of first failing at the
finish.sh gate. Any other file: exit 0, no-op.

Stdlib only, no dependencies — safe to run on every Write/Edit.
"""
import json
import os
import subprocess
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    path = (event.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".cards.json") or not os.path.isfile(path):
        return 0
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "tools", "lint_cards.py"), path],
        capture_output=True, text=True, cwd=root)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        return 2  # blocking feedback: Claude sees the lint errors right away
    return 0


if __name__ == "__main__":
    sys.exit(main())
