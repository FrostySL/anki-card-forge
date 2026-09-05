"""Portable file stems for exported decks; Anki's deck names stay unchanged."""
import hashlib
import re
import unicodedata


def safe_stem(name):
    stem = re.sub(r"[^\w.+-]+", "_", name).strip("_ .") or "deck"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", stem, re.I):
        stem = "_" + stem
    if len(stem.encode("utf-8")) > 180:
        stem = stem.encode("utf-8")[:160].decode("utf-8", errors="ignore")
        stem += "_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return stem


def collision_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def unique_stems(names):
    out, used = {}, set()
    for name in names:
        stem = safe_stem(name)
        candidate, number = stem, 1
        while collision_key(candidate) in used:
            number += 1
            candidate = f"{stem}_{number}"
        used.add(collision_key(candidate))
        out[name] = candidate
    return out


def unique_media_names(names):
    """Keep ordinary Anki media names, remapping names Windows cannot store."""
    out, used = {}, set()
    for name in names:
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(" .") or "media"
        if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", filename, re.I):
            filename = "_" + filename
        stem, dot, extension = filename.rpartition(".")
        if not stem or not dot:
            stem, extension = filename, ""
        else:
            extension = "." + extension
        if len(filename.encode("utf-8")) > 220:
            # An implausibly long extension is still part of the path limit.
            extension = extension.encode("utf-8")[:30].decode("utf-8", errors="ignore")
            stem = stem.encode("utf-8")[:160].decode("utf-8", errors="ignore")
            stem += "_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        candidate, number = stem + extension, 1
        while collision_key(candidate) in used:
            number += 1
            candidate = f"{stem}_{number}{extension}"
        used.add(collision_key(candidate))
        out[name] = candidate
    return out
