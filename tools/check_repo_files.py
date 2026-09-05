#!/usr/bin/env python3
"""Block newly tracked personal material in the public repository.

Both the local commit hook and CI use this allowlist. Existing tracked files
may be modified or deleted; additions, copies and rename destinations must
pass the staged/diff guard. The --tracked mode checks every tracked path;
--base checks changes since base and head's merge base, as a pull request does.
This path guard cannot detect private text in allowed files.
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys


ALLOWED_PATTERNS = (
    "tools/*", "tests/*", ".claude/*", ".github/*", ".githooks/*",
    "skills/card-authoring/*.md", "workflows/forge.md", "workflows/rework.md",
    "reference/README.md", "sources/.gitkeep", "decks/.gitkeep",
    "decks/example.cards.json", "docs/*.md", "docs/img/*.png", "docs/img/*.gif",
)
BLOCKED_SUFFIXES = (".pdf", ".apkg", ".colpkg")


def blocked_reason(path):
    if path.lower().endswith(BLOCKED_SUFFIXES):
        return "PDFs/Anki packages do not belong in the public repo."
    if "/" not in path or any(fnmatch.fnmatchcase(path, p) for p in ALLOWED_PATTERNS):
        return None
    return "path is not on the allowlist (personal sources, extracts and decks stay local)."


def git_output(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"git exited with status {result.returncode}")
    return result.stdout


def resolve_commit(ref):
    # Resolve first so a supplied ref cannot be interpreted as a diff option.
    return git_output("rev-parse", "--verify", "--end-of-options",
                      ref + "^{commit}").decode("ascii").strip()


def changed_paths(*, staged=False, tracked=False, base=None, head="HEAD"):
    if tracked:
        output = git_output("ls-files", "--full-name", "-z", "--", ":/")
        return [os.fsdecode(path) for path in output.split(b"\0") if path]
    args = ["diff", "--name-only", "-z", "--diff-filter=ACR", "--find-renames",
            "--no-relative", "--no-ext-diff"]
    if staged:
        args.append("--cached")
    else:
        args.append(f"{resolve_commit(base)}...{resolve_commit(head)}")
    output = git_output(*args, "--")
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="check staged additions and renames")
    mode.add_argument("--tracked", action="store_true", help="check the complete tracked file snapshot")
    mode.add_argument("--base", help="base commit/ref for a PR-style merge-base diff")
    parser.add_argument("--head", default="HEAD", help="head commit/ref (default: HEAD)")
    args = parser.parse_args(argv)
    if not args.base and args.head != "HEAD":
        parser.error("--head requires --base")
    try:
        paths = changed_paths(staged=args.staged, tracked=args.tracked,
                              base=args.base, head=args.head)
    except (OSError, RuntimeError) as exc:
        print(f"Repository file guard could not run: {exc}", file=sys.stderr)
        return 2
    blocked = [(path, blocked_reason(path)) for path in paths]
    blocked = [(path, reason) for path, reason in blocked if reason]
    for path, reason in blocked:
        # Escaping control characters keeps unusual Git filenames unambiguous.
        print(f"BLOCKED: {json.dumps(path, ensure_ascii=True)} — {reason}", file=sys.stderr)
    if blocked:
        print("Repository file guard failed. If the files are intended for the public repo, "
              "extend the allowlist in tools/check_repo_files.py after checking their content.",
              file=sys.stderr)
        return 1
    print(f"Repository file guard passed ({len(paths)} paths checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
