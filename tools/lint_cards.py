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
from _card_media import local_image_sources
from _card_schema import TEXT_FIELDS, schema_errors

_CLOZE_RE = re.compile(r"\{\{c(\d+)::.+?\}\}", re.DOTALL)
_LONG_ANSWER = 350  # chars: above this, warn "answer may be too long"

# Allowed fields — unknown keys (typos like "explaination") are silently dropped
# by the build, and the content would be lost. Hence the warnings here.
_DECK_KEYS = {"deck", "cards", "description"}
_COMMON_KEYS = {"type", "tags", "guid", "explanation", "source"}
_TYPE_KEYS = {
    "basic": {"front", "back", "reverse", "more"},
    "typein": {"front", "back", "more"},
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

    shape_errors = schema_errors(data)
    if shape_errors:
        print(f"== Lint: {cards_path} ==")
        for message in shape_errors:
            print(f"  [ERROR] {message}")
        print(f"-> {len(shape_errors)} errors, 0 warnings")
        return 1

    cards = data["cards"]
    if not cards:
        errors.append("  [ERROR] no 'cards' present.")
    for key in sorted(set(data) - _DECK_KEYS):
        warnings.append(f"  [warn]  unknown field {key!r} at deck level – ignored.")

    seen_fronts = {}
    seen_guids = {}
    for i, card in enumerate(cards):
        guid = card.get("guid")
        if guid is not None:
            seen_guids.setdefault(guid, []).append(i)
        ctype = card.get("type", "basic")
        if ctype in ("basic", "typein"):
            front = card["front"].strip()
            back = card["back"].strip()
            if not front:
                err(i, f"{ctype} without 'front'.")
            if not back:
                err(i, f"{ctype} without 'back'.")
            if front:
                seen_fronts.setdefault(front, []).append(i)
            if len(back) > _LONG_ANSWER:
                warn(i, f"answer very long ({len(back)} chars) – consider splitting.")
        elif ctype == "cloze":
            text = card["text"].strip()
            if not text:
                err(i, "cloze without 'text'.")
            else:
                nums = {int(m.group(1)) for m in _CLOZE_RE.finditer(text)}
                if not nums:
                    err(i, "cloze 'text' contains no deletion {{c1::...}}.")
                elif 0 in nums:
                    # genanki/Anki build NO card for c0 — the note would exist
                    # without a single card and slip through validate unseen.
                    err(i, "cloze uses {{c0::...}} — numbering starts at c1; "
                           "no card would be generated for c0.")
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
                    v = r[key]
                    if not (0 <= v <= 1):
                        warn(i, f"region {n}: '{key}'={v} outside 0..1 (fractions!).")
                x, y, w, h = r["x"], r["y"], r["w"], r["h"]
                if x + w > 1.001:
                    warn(i, f"region {n}: x+w={x + w:.3f} > 1 – sticks out on the right.")
                if y + h > 1.001:
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

        for key in TEXT_FIELDS:
            val = card.get(key)
            if isinstance(val, str):
                for path in local_image_sources(val):
                    if not os.path.exists(path):
                        err(i, f"'{key}': <img> not found: {path}")

        if ctype in _TYPE_KEYS:
            for key in sorted(set(card) - _COMMON_KEYS - _TYPE_KEYS[ctype]):
                if key == "reverse":
                    warn(i, f"'reverse' only works on type 'basic' (here '{ctype}') – ignored.")
                else:
                    warn(i, f"unknown field '{key}' – silently dropped at build (typo?).")

    for front, idxs in seen_fronts.items():
        if len(idxs) > 1:
            warnings.append(f"  [warn]  duplicate question in cards {idxs}: {front[:60]!r}")

    for guid, idxs in seen_guids.items():
        if len(idxs) > 1:
            # Same GUID twice in one package: Anki keeps only one note on import,
            # the others silently vanish (their content is lost).
            errors.append(f"  [ERROR] duplicate guid {guid!r} in cards {idxs} — "
                          "Anki would import only one of them, the rest are lost.")

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
