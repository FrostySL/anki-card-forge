#!/usr/bin/env bash
# One-shot setup + health check ("doctor") for a fresh clone.
#
#   ./tools/setup.sh
#
# Verifies the toolchain, does the two easy-to-forget one-offs (commit guard,
# builder image), and proves the pipeline end-to-end on the bundled example
# deck — so the first five minutes end with a visible success instead of the
# first failure mid-task. Idempotent: safe to re-run.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
info() { printf '  \033[34m•\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

echo "== anki-card-forge setup =="

# 1) Prerequisites -----------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found — install Python 3.10+."
ok "python3: $(python3 --version 2>&1)"

command -v docker >/dev/null 2>&1 || die "docker not found — install Docker (packs cards into .apkg)."
if ! docker info >/dev/null 2>&1; then
  die "Docker is installed but the daemon is not reachable — start Docker and re-run."
fi
ok "docker: daemon reachable"

# 2) Commit guard (privacy-critical one-off) ---------------------------------
current_hookpath="$(git config --get core.hooksPath || true)"
if [ "$current_hookpath" = ".githooks" ]; then
  ok "commit guard already active (core.hooksPath = .githooks)"
else
  git config core.hooksPath .githooks
  ok "commit guard enabled (core.hooksPath -> .githooks) — blocks committing personal material"
fi

# 3) Logic tests (stdlib, no Docker) -----------------------------------------
if ./tools/test.sh >/tmp/acf_setup_test.log 2>&1; then
  ok "test suite green ($(grep -oE 'Ran [0-9]+ tests' /tmp/acf_setup_test.log | tail -1))"
else
  cat /tmp/acf_setup_test.log >&2
  die "test suite failed (see output above)."
fi
rm -f /tmp/acf_setup_test.log

# 4) Builder image + example deck smoke test ---------------------------------
if docker image inspect anki-cards >/dev/null 2>&1; then
  ok "builder image 'anki-cards' present"
else
  info "building the slim builder image (one-off)…"
  docker build -q -t anki-cards "$PROJECT_DIR" >/dev/null
  ok "builder image 'anki-cards' built"
fi

info "building the bundled example deck…"
# The output path must be RELATIVE to the project: build.sh mounts PROJECT_DIR
# at /work in the container, so an absolute host path resolves to a
# non-existent location inside it (and a /tmp path would be written in the
# container and lost). We are cd'd into PROJECT_DIR, so a relative path works
# on both sides. decks/*.apkg is gitignored -> nothing tracked is left behind.
smoke_apkg="decks/.setup-smoke.apkg"
trap 'rm -f "$PROJECT_DIR/$smoke_apkg"' EXIT
if ./tools/build.sh decks/example.cards.json "$smoke_apkg" >/dev/null 2>&1 && [ -f "$smoke_apkg" ]; then
  ok "example deck built ($(du -h "$smoke_apkg" | cut -f1)) — the card JSON -> .apkg path works"
else
  die "building the example deck failed — check 'docker build -t anki-cards .'"
fi

echo ""
echo "Setup complete. Next: drop a source into sources/<topic>/ and ask Claude"
echo "to make cards from it (or run  /forge sources/<topic>/<file>  in Claude Code)."
