#!/usr/bin/env bash
# Schnelle Testsuite der stdlib-Logik-Tools (lint, grounding, coverage, figindex).
# Reines Python (unittest) – KEIN Docker, KEINE pip-Installation noetig.
#
#   ./tools/test.sh                 # alle Tests
#   ./tools/test.sh -v              # ausfuehrlich
#
# Der Build-Smoke-Test (build_deck.py) braucht genanki und ueberspringt sich auf dem
# Host; im Build-Container laeuft er mit:
#   docker run --rm -v "$PWD":/work --entrypoint python anki-karten \
#       -m unittest discover -s /work/tests
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 -m unittest discover -s "$PROJECT_DIR/tests" -p "test_*.py" "$@"
