#!/usr/bin/env python3
"""Fast content/structure check for a cards.json (pure Python, no deps).

    python3 tools/lint_cards.py decks/script.cards.json

Reports ERRORS (blocking, exit code 1) and warnings (hints). Complements the
visual preview loop with a quick check of the content itself.
"""
import json
import os
import re
import sys

_CLOZE_RE = re.compile(r"\{\{c(\d+)::.+?\}\}", re.DOTALL)
_LONG_ANSWER = 350  # chars: above this, warn "answer may be too long"

# Allowed fields — unknown keys (typos like "explaination") are silently dropped
# by the build, and the content would be lost. Hence the warnings here.
_DECK_KEYS = {"deck", "cards"}
_COMMON_KEYS = {"type", "tags", "guid", "explanation", "source"}
_TYPE_KEYS = {
    "basic": {"front", "back", "reverse"},
    "typein": {"front", "back"},
    "cloze": {"text", "extra"},
    "occlusion": {"image", "mode", "header", "extra", "regions"},
}
_REGION_KEYS = {"label", "x", "y", "w", "h"}


def lint(cards_path):
    errors, warnings = [], []

    def err(i, msg):
        errors.append(f"  [ERROR] card {i}: {msg}")

    def warn(i, msg):
        warnings.append(f"  [warn]  card {i}: {msg}")

    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("deck"):
        errors.append("  [ERROR] 'deck' is missing or empty.")
    cards = data.get("cards") or []
    if not cards:
        errors.append("  [ERROR] no 'cards' present.")
    for key in sorted(set(data) - _DECK_KEYS):
        warnings.append(f"  [warn]  unknown field {key!r} at deck level – ignored.")

    seen_fronts = {}
    for i, card in enumerate(cards):
        ctype = card.get("type", "basic")
        if ctype in ("basic", "typein"):
            front = (card.get("front") or "").strip()
            back = (card.get("back") or "").strip()
            if not front:
                err(i, f"{ctype} without 'front'.")
            if not back:
                err(i, f"{ctype} without 'back'.")
            if front:
                seen_fronts.setdefault(front, []).append(i)
            if len(back) > _LONG_ANSWER:
                warn(i, f"answer very long ({len(back)} chars) – consider splitting.")
        elif ctype == "cloze":
            text = (card.get("text") or "").strip()
            if not text:
                err(i, "cloze without 'text'.")
            elif not _CLOZE_RE.search(text):
                err(i, "cloze 'text' contains no deletion {{c1::...}}.")
        elif ctype == "occlusion":
            img = card.get("image")
            if not img:
                err(i, "occlusion without 'image'.")
            elif not os.path.exists(img):
                err(i, f"image not found: {img}")
            regions = card.get("regions") or []
            if not regions:
                err(i, "occlusion without 'regions'.")
            for n, r in enumerate(regions):
                for key in ("x", "y", "w", "h"):
                    v = r.get(key)
                    if not isinstance(v, (int, float)):
                        err(i, f"region {n}: '{key}' missing or not a number.")
                    elif not (0 <= v <= 1):
                        warn(i, f"region {n}: '{key}'={v} outside 0..1 (fractions!).")
                x, y = r.get("x", 0), r.get("y", 0)
                w, h = r.get("w", 0), r.get("h", 0)
                if isinstance(x, (int, float)) and isinstance(w, (int, float)) and x + w > 1.001:
                    warn(i, f"region {n}: x+w={x + w:.3f} > 1 – sticks out on the right.")
                if isinstance(y, (int, float)) and isinstance(h, (int, float)) and y + h > 1.001:
                    warn(i, f"region {n}: y+h={y + h:.3f} > 1 – sticks out at the bottom.")
                if not (r.get("label") or "").strip():
                    warn(i, f"region {n}: no 'label' (answer stays empty).")
                for key in sorted(set(r) - _REGION_KEYS):
                    warn(i, f"region {n}: unknown field '{key}' – ignored.")
            mode = card.get("mode", "hide-one")
            if mode not in ("hide-one", "hide-all"):
                err(i, f"unknown mode '{mode}' (hide-one | hide-all).")
        else:
            err(i, f"unknown type '{ctype}' (basic | cloze | typein | occlusion).")

        if ctype in _TYPE_KEYS:
            for key in sorted(set(card) - _COMMON_KEYS - _TYPE_KEYS[ctype]):
                if key == "reverse":
                    warn(i, f"'reverse' only works on type 'basic' (here '{ctype}') – ignored.")
                else:
                    warn(i, f"unknown field '{key}' – silently dropped at build (typo?).")

    for front, idxs in seen_fronts.items():
        if len(idxs) > 1:
            warnings.append(f"  [warn]  duplicate question in cards {idxs}: {front[:60]!r}")

    print(f"== Lint: {cards_path} ({len(cards)} cards) ==")
    for line in errors:
        print(line)
    for line in warnings:
        print(line)
    if not errors and not warnings:
        print("  all good ✓")
    print(f"-> {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(lint(sys.argv[1]))
