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
# Local <img src="..."> in text fields (embedded by the build; must exist).
_IMG_SRC_RE = re.compile(r"""<img\b[^>]*?\bsrc=(["'])(?!data:|https?:|//)([^"']+)\1""", re.IGNORECASE)
_TEXT_FIELDS = ("front", "back", "text", "extra", "header", "explanation")
_LONG_ANSWER = 350  # chars: above this, warn "answer may be too long"

# Allowed fields — unknown keys (typos like "explaination") are silently dropped
# by the build, and the content would be lost. Hence the warnings here.
_DECK_KEYS = {"deck", "cards", "description"}
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

    def str_field(card, i, key):
        """String value of card[key] ('' if absent). A non-string value becomes
        an [ERROR] instead of an AttributeError traceback further down —
        exactly the broken JSON this linter exists to catch."""
        val = card.get(key)
        if val is None:
            return ""
        if not isinstance(val, str):
            err(i, f"'{key}' must be a string, got {type(val).__name__}.")
            return ""
        return val

    with open(cards_path, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("deck"):
        errors.append("  [ERROR] 'deck' is missing or empty.")
    if "description" in data and not isinstance(data["description"], str):
        errors.append("  [ERROR] 'description' must be a string (HTML allowed).")
    cards = data.get("cards") or []
    if not cards:
        errors.append("  [ERROR] no 'cards' present.")
    for key in sorted(set(data) - _DECK_KEYS):
        warnings.append(f"  [warn]  unknown field {key!r} at deck level – ignored.")

    seen_fronts = {}
    seen_guids = {}
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            err(i, f"card must be a JSON object, got {type(card).__name__}.")
            continue
        guid = card.get("guid")
        if guid is not None:
            if not isinstance(guid, str) or not guid.strip():
                err(i, "'guid' must be a non-empty string.")
            else:
                seen_guids.setdefault(guid, []).append(i)
        tags = card.get("tags")
        if tags is not None and (
                not isinstance(tags, list)
                or not all(isinstance(t, str) for t in tags)):
            err(i, "'tags' must be a list of strings — a bare string would "
                   "end up as single-character tags in Anki.")
        ctype = card.get("type", "basic")
        if ctype in ("basic", "typein"):
            front = str_field(card, i, "front").strip()
            back = str_field(card, i, "back").strip()
            if not front:
                err(i, f"{ctype} without 'front'.")
            if not back:
                err(i, f"{ctype} without 'back'.")
            if front:
                seen_fronts.setdefault(front, []).append(i)
            if len(back) > _LONG_ANSWER:
                warn(i, f"answer very long ({len(back)} chars) – consider splitting.")
        elif ctype == "cloze":
            text = str_field(card, i, "text").strip()
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
                if not isinstance(r, dict):
                    err(i, f"region {n}: must be an object with x/y/w/h/label.")
                    continue
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

        for key in _TEXT_FIELDS:
            val = card.get(key)
            if isinstance(val, str):
                for m in _IMG_SRC_RE.finditer(val):
                    if not os.path.exists(m.group(2)):
                        err(i, f"'{key}': <img> not found: {m.group(2)}")

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
