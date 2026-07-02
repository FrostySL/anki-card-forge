#!/usr/bin/env bash
# Fast test suite for the stdlib logic tools (lint, grounding, coverage, figindex).
# Pure Python (unittest) — NO Docker, NO pip install needed.
#
#   ./tools/test.sh                 # all tests
#   ./tools/test.sh -v              # verbose
#
# The build smoke test (build_deck.py) needs genanki and skips itself on the
# host; inside the build container it runs with:
#   docker run --rm -v "$PWD":/work --entrypoint python anki-cards \
#       -m unittest discover -s /work/tests
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 -m unittest discover -s "$PROJECT_DIR/tests" -p "test_*.py" "$@"
