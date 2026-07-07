#!/usr/bin/env python3
"""Maps a Docker wrapper's arguments so paths resolve inside the container.

Usage (internal, called by the tools/*.sh wrappers):
    python3 _map_paths.py <PROJECT_DIR> [arg ...]

The wrappers mount PROJECT_DIR at /work and run with the container cwd at
/work. A path argument given as ABSOLUTE, or relative to a DIFFERENT cwd,
would not resolve there — the tool then fails confusingly or (for an output
path) reports success while the file is written inside the container and
lost. This rewrites every path-like argument to its PROJECT_DIR-relative form
(so it maps to /work/… in the container) and REFUSES paths that point outside
the project. Flags (-… ) and non-path values (e.g. `eng+fra`, `2.5`) pass
through unchanged.

Emits the mapped arguments NUL-terminated on stdout. Exit 2 on an outside path.
"""
import os
import sys

# Extensions the wrappers operate on — a bare name like "x.apkg" (no slash) is
# still a path. Values like "eng+fra" or "2.5" match nothing and pass through.
_PATH_EXTS = (".json", ".apkg", ".pdf", ".png", ".jpg", ".jpeg", ".md",
              ".markdown", ".txt")


def _looks_like_path(arg):
    if arg.startswith("-"):
        return False                       # a flag (e.g. --lang, -j)
    if "/" in arg or os.sep in arg:
        return True                        # decks/x.json, sources/Bio/
    if arg.lower().endswith(_PATH_EXTS):
        return True                        # bare x.apkg in the cwd
    return os.path.exists(arg)             # anything that is actually a file/dir


def map_arg(arg, root):
    """A single argument -> its PROJECT_DIR-relative form (or unchanged if not
    a path). Raises SystemExit(2) if it resolves outside the project."""
    if not _looks_like_path(arg):
        return arg
    # realpath resolves symlinks and a non-existent leaf (output paths) alike.
    abs_path = os.path.realpath(arg)
    if abs_path != root and not abs_path.startswith(root + os.sep):
        sys.stderr.write(
            f"Error: '{arg}' is outside the project ({root}).\n"
            "       The tools operate on files inside the project "
            "(sources/, decks/, extracted/, …).\n"
            "       Use a path within it, e.g. decks/<topic>/<name>.cards.json.\n"
        )
        raise SystemExit(2)
    return os.path.relpath(abs_path, root)


def main(argv):
    root = os.path.realpath(argv[0]).rstrip(os.sep)
    mapped = [map_arg(a, root) for a in argv[1:]]
    # NUL-terminate each item so the shell can read them back losslessly
    # (paths may contain spaces); empty input -> no output.
    sys.stdout.write("".join(a + "\0" for a in mapped))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("usage: _map_paths.py <PROJECT_DIR> [arg ...]\n")
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
