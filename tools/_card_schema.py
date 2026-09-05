"""Shared JSON shape/type checks, before builders or linters consume a deck.

Content checks (empty answers, cloze syntax, missing images) remain in the
linter. These checks prevent malformed JSON from crashing those checks or
silently changing the requested card type.
"""
import math


TEXT_FIELDS = ("front", "back", "text", "extra", "header", "explanation", "more")
_REQUIRED = {"basic": ("front", "back"), "typein": ("front", "back"),
             "cloze": ("text",), "occlusion": ("image", "regions")}


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def schema_errors(data):
    errors = []
    if not isinstance(data, dict):
        return ["deck must be a JSON object."]
    if "deck" not in data or data["deck"] == "":
        errors.append("'deck' is missing or empty.")
    elif not isinstance(data["deck"], str):
        errors.append("'deck' must be a string.")
    if "description" in data and not isinstance(data["description"], str):
        errors.append("'description' must be a string (HTML allowed).")
    if "cards" not in data:
        errors.append("no 'cards' present.")
    cards = data.get("cards", [])
    if not isinstance(cards, list):
        errors.append("'cards' must be a list of card objects.")
        return errors
    for i, card in enumerate(cards):
        prefix = f"card {i}: "
        if not isinstance(card, dict):
            errors.append(prefix + "card must be a JSON object.")
            continue
        ctype = card.get("type", "basic")
        required = _REQUIRED.get(ctype, ()) if isinstance(ctype, str) else ()
        for key in required:
            if key not in card:
                errors.append(prefix + f"{ctype} without '{key}'.")
        for key in (*TEXT_FIELDS, "source", "image", "mode", "type"):
            if key in card and not isinstance(card[key], str):
                errors.append(prefix + f"'{key}' must be a string.")
        if "reverse" in card and not isinstance(card["reverse"], bool):
            errors.append(prefix + "'reverse' must be a boolean (true or false).")
        if "guid" in card and (
                not isinstance(card["guid"], str) or not card["guid"].strip()):
            errors.append(prefix + "'guid' must be a non-empty string.")
        if "tags" in card and (not isinstance(card["tags"], list)
                                or not all(isinstance(t, str) for t in card["tags"])):
            errors.append(prefix + "'tags' must be a list of strings.")
        if "regions" not in card:
            continue
        if not isinstance(card["regions"], list):
            errors.append(prefix + "'regions' must be a list of region objects.")
            continue
        for n, region in enumerate(card["regions"]):
            rprefix = prefix + f"region {n}: "
            if not isinstance(region, dict):
                errors.append(rprefix + "must be an object with x/y/w/h/label.")
                continue
            if "label" in region and not isinstance(region["label"], str):
                errors.append(rprefix + "'label' must be a string.")
            for key in ("x", "y", "w", "h"):
                value = region.get(key)
                if not _finite_number(value):
                    errors.append(rprefix + f"'{key}' must be a finite number.")
    return errors


def validate_schema(data):
    """Raise one useful error before any card fields are rendered or mutated."""
    errors = schema_errors(data)
    if errors:
        raise ValueError("Invalid cards JSON:\n  " + "\n  ".join(errors))
