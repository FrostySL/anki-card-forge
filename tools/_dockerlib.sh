#!/usr/bin/env bash
# Shared helper for the Docker wrapper scripts (build/extract/figextract/
# detect/preview/validate). Sourced, not executed.
#
# map_paths "$@"  ->  sets the global array MAPPED to the arguments with every
# path rewritten PROJECT_DIR-relative (so it resolves at /work in the
# container); aborts with exit 2 if an argument points outside the project.
# Requires PROJECT_DIR to be set by the caller. Portable to bash 3.2 (macOS):
# no `mapfile`, and the empty-array expansion is guarded at the call site with
# ${MAPPED[@]+"${MAPPED[@]}"}.

map_paths() {
  local tmp
  tmp="$(mktemp)"
  if ! python3 "$PROJECT_DIR/tools/_map_paths.py" "$PROJECT_DIR" "$@" >"$tmp"; then
    rm -f "$tmp"
    exit 2
  fi
  MAPPED=()
  while IFS= read -r -d '' item; do
    MAPPED+=("$item")
  done <"$tmp"
  rm -f "$tmp"
}
