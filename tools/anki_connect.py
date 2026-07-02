#!/usr/bin/env python3
"""Talks to a running Anki desktop via the AnkiConnect add-on (stdlib only, no
dependencies) — push a built .apkg straight into Anki, export a deck back out
(for the GUID-preserving rebuild), or trigger sync.

Requires:
  - Anki desktop running.
  - The AnkiConnect add-on installed (code 2055492159: Tools -> Add-ons ->
    Get Add-ons... -> 2055492159 -> restart Anki).

Usage:
    python3 tools/anki_connect.py ping
    python3 tools/anki_connect.py push <file.apkg> [--no-backup] [--prune]
    python3 tools/anki_connect.py export "<Deck::Name>" <out.apkg>
    python3 tools/anki_connect.py sync
    python3 tools/anki_connect.py mirror [deck ...]

Endpoint overridable via ANKICONNECT_URL (default http://127.0.0.1:8765).
Pure local HTTP — no credentials, no Docker; the .apkg build itself is
unaffected and still goes through Docker as usual.

Safeguards:
  - Only a small allowlist of AnkiConnect actions is callable (SAFE_ACTIONS);
    destructive ones (deleteDecks, deleteNotes, ...) are locked out.
  - `push` first backs up every affected existing deck (with scheduling) to
    decks/_anki-backups/<timestamp>/ — restore by pushing the backup .apkg.
  - A plain import never deletes anything (Anki merges). Removing cards from a
    reworked deck requires the explicit `push --prune`, which deletes exactly
    the notes whose GUIDs vanished from the package — listed one by one, only
    with a fresh backup, and refused entirely if a deck shares no GUID with
    the package (symptom of a rebuild that lost the GUIDs).
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request

URL = os.environ.get("ANKICONNECT_URL", "http://127.0.0.1:8765")
TIMEOUT = float(os.environ.get("ANKICONNECT_TIMEOUT", "60"))

HELP = (
    "Is Anki running with the AnkiConnect add-on installed?\n"
    "  1. Anki desktop must be open.\n"
    "  2. Install add-on code 2055492159 (Tools -> Add-ons -> Get Add-ons...),\n"
    "     then restart Anki.\n"
    f"  3. AnkiConnect must be reachable at {URL} (override via ANKICONNECT_URL)."
)


class AnkiConnectError(RuntimeError):
    pass


# Everything this tool needs — and nothing more. AnkiConnect also exposes
# destructive actions (deleteDecks, deleteNotes, ...); those are deliberately
# locked so no code path (or typo) can ever wipe someone's collection through
# this tool. Conscious override only: ANKICONNECT_ALLOW_UNSAFE=1.
SAFE_ACTIONS = {
    "version", "requestPermission", "deckNames",
    "importPackage", "exportPackage", "sync",
}


def invoke(action, **params):
    """Calls one AnkiConnect action, returns its `result`.

    Only actions in SAFE_ACTIONS are allowed (guard against destructive API
    calls). Raises AnkiConnectError if Anki/AnkiConnect is unreachable or the
    response envelope carries a non-null `error`.
    """
    if action not in SAFE_ACTIONS and not os.environ.get("ANKICONNECT_ALLOW_UNSAFE"):
        raise AnkiConnectError(
            f"Action '{action}' is not on this tool's safe list "
            f"({', '.join(sorted(SAFE_ACTIONS))}). Destructive AnkiConnect actions "
            "are deliberately locked; set ANKICONNECT_ALLOW_UNSAFE=1 only if you "
            "know exactly what you are doing."
        )
    return _call(action, params)


def _call(action, params):
    """The raw HTTP call, without the SAFE_ACTIONS guard — only invoke() and
    the tightly guarded prune path may use this directly."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise AnkiConnectError(f"Could not reach AnkiConnect at {URL} ({e}).\n{HELP}") from e
    if not isinstance(body, dict) or "error" not in body or "result" not in body:
        raise AnkiConnectError(f"Unexpected AnkiConnect response: {body!r}")
    if body["error"] is not None:
        raise AnkiConnectError(f"AnkiConnect action '{action}' failed: {body['error']}")
    return body["result"]


def ping():
    """Connectivity + permission check (also the recommended first call)."""
    result = invoke("requestPermission")
    if result.get("permission") != "granted":
        raise AnkiConnectError(
            "AnkiConnect permission denied — a dialog may be waiting in Anki; "
            "click 'Yes' to allow this connection, then retry.\n" + HELP
        )
    print(f"OK: AnkiConnect v{result.get('version')} reachable, permission granted.")
    return result


def _apkg_to_cards():
    """The sibling apkg_to_cards module (same tools/ folder, lazy import)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import apkg_to_cards
    return apkg_to_cards


BACKUP_DIR = os.path.join("decks", "_anki-backups")
BACKUP_KEEP = 10


def _decks_in_apkg(apkg_path):
    """Deck names that actually hold cards in the .apkg (what a push touches).
    Deliberately ignores card-less deck entries (e.g. the 'Default' stub
    genanki writes into every package)."""
    atc = _apkg_to_cards()
    con, tmp = atc.open_collection(apkg_path)
    try:
        _ntype, decks, _schema = atc._maps(con)
        dids = {row[0] for row in con.execute("SELECT DISTINCT did FROM cards")}
    finally:
        con.close()
        os.unlink(tmp)
    return {decks[d] for d in dids if d in decks}


def _covering(deck_names):
    """Minimal covering set: drops decks whose ancestor is also in the set
    (exporting a parent deck already includes its subdecks)."""
    names = set(deck_names)
    return sorted(
        name for name in names
        if not any("::".join(name.split("::")[:i]) in names
                   for i in range(1, len(name.split("::"))))
    )


def _prune_backups(keep=BACKUP_KEEP):
    """Keeps only the newest `keep` timestamped backup folders."""
    if not os.path.isdir(BACKUP_DIR):
        return
    stamps = sorted(d for d in os.listdir(BACKUP_DIR)
                    if os.path.isdir(os.path.join(BACKUP_DIR, d)))
    for d in stamps[:-keep] if keep else stamps:
        shutil.rmtree(os.path.join(BACKUP_DIR, d))


def _backup_decks(deck_names):
    """Exports decks (WITH scheduling) into a timestamped backup folder.
    Restore = push the backup .apkg again (GUIDs -> notes revert).
    Returns the list of written .apkg paths."""
    outdir = os.path.join(BACKUP_DIR, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for deck in deck_names:
        path = os.path.join(outdir, _safe_name(deck) + ".apkg")
        invoke("exportPackage", deck=deck, path=os.path.abspath(path), includeSched=True)
        print(f"Backup: '{deck}' -> {path}")
        paths.append(path)
    _prune_backups()
    return paths


def _package_guids(apkg_path):
    """All note GUIDs in an .apkg."""
    atc = _apkg_to_cards()
    con, tmp = atc.open_collection(apkg_path)
    try:
        return {g for (g,) in con.execute("SELECT guid FROM notes")}
    finally:
        con.close()
        os.unlink(tmp)


def _notes_with_decks(apkg_path):
    """{guid: (note id, deck name, first field)} of an .apkg. Note ids in an
    Anki export are the live collection's ids -> usable for deleteNotes."""
    atc = _apkg_to_cards()
    con, tmp = atc.open_collection(apkg_path)
    try:
        _ntype, decks, _schema = atc._maps(con)
        note_deck = {nid: decks.get(did, "Default")
                     for nid, did in con.execute("SELECT nid, MIN(did) FROM cards GROUP BY nid")}
        out = {}
        for nid, guid, flds in con.execute("SELECT id, guid, flds FROM notes"):
            out[guid] = (nid, note_deck.get(nid, "Default"), flds.split(atc.FIELD_SEP)[0])
    finally:
        con.close()
        os.unlink(tmp)
    return out


_TAG_RE = re.compile(r"<[^>]+>")


def _snippet(html_text, limit=60):
    text = " ".join(_TAG_RE.sub(" ", html_text).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _orphans(anki_notes, package_guids, package_decks):
    """Notes a prune-push may delete: they live in a deck the package writes to,
    but their GUID appears nowhere in the package (= card was removed in the
    rework; a note merely MOVED to another package deck keeps its GUID and is
    kept).

    Refuses when a deck shares NO GUID with the package at all — the typical
    symptom of a rebuild that lost the GUIDs; pruning then would replace the
    whole deck and wipe its learning progress.
    """
    by_deck = {}
    for guid, (nid, deck, front) in anki_notes.items():
        if deck in package_decks:
            by_deck.setdefault(deck, []).append((guid, nid, front))
    orphans = []
    for deck, notes in sorted(by_deck.items()):
        gone = [(nid, deck, _snippet(front))
                for guid, nid, front in notes if guid not in package_guids]
        if gone and len(gone) == len(notes):
            raise AnkiConnectError(
                f"Prune refused: not a single card of deck '{deck}' matches the "
                "package (0 shared GUIDs). That usually means the rebuild lost "
                "the note GUIDs — pruning would replace the whole deck and wipe "
                "its learning progress. Rebuild with preserved GUIDs "
                "(tools/apkg_to_cards.py) and try again. Nothing was imported."
            )
        orphans += gone
    return orphans


def push(apkg_path, backup=True, prune=False):
    """Imports a built .apkg into Anki's collection (importPackage).

    Safety net: same-GUID notes get their fields OVERWRITTEN by the import, so
    by default every deck that exists in Anki AND is part of the package is
    exported to decks/_anki-backups/<timestamp>/ first (gitignored, newest
    10 kept). Disable consciously with backup=False / --no-backup.

    prune=True (--prune): an import can never REMOVE notes — cards taken out
    of a reworked deck would linger in Anki forever. Prune deletes exactly
    those leftovers (GUID diff against the fresh backup), computed BEFORE the
    import so a refusal aborts the push untouched. Requires the backup.
    """
    if not os.path.isfile(apkg_path):
        raise FileNotFoundError(apkg_path)
    if prune and not backup:
        raise AnkiConnectError(
            "--prune needs the automatic backup as its diff baseline (and as "
            "the restore path) — do not combine it with --no-backup."
        )
    backup_paths = []
    orphans = []
    if backup:
        existing = set(invoke("deckNames"))
        package_decks = _decks_in_apkg(apkg_path)
        affected = _covering(package_decks & existing)
        if affected:
            backup_paths = _backup_decks(affected)
        else:
            print("Backup: no existing deck affected, nothing to save.")
        if prune and backup_paths:
            anki_notes = {}
            for path in backup_paths:
                anki_notes.update(_notes_with_decks(path))
            orphans = _orphans(anki_notes, _package_guids(apkg_path), package_decks)

    invoke("importPackage", path=os.path.abspath(apkg_path))
    print(f"OK: imported {apkg_path} into Anki.")

    if prune:
        if not orphans:
            print("Prune: no removed cards, nothing to delete.")
            return
        print(f"Prune: deleting {len(orphans)} note(s) that were removed from the package:")
        for _nid, deck, front in orphans:
            print(f"  - [{deck}] {front}")
        # deliberate bypass of the SAFE_ACTIONS guard: exactly these listed
        # notes, diffed against the backup taken seconds ago (= restore path).
        _call("deleteNotes", {"notes": [nid for nid, _, _ in orphans]})
        print(f"Prune: done. Restore if needed: push the backup from {os.path.dirname(backup_paths[0])}/")


def export(deck_name, out_path):
    """Exports a deck to .apkg WITH scheduling (for the GUID-preserving rebuild)."""
    abs_path = os.path.abspath(out_path)
    out_dir = os.path.dirname(abs_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    invoke("exportPackage", deck=deck_name, path=abs_path, includeSched=True)
    print(f"OK: exported '{deck_name}' -> {out_path} (with scheduling).")


def sync():
    """Triggers the same AnkiWeb sync as the GUI's sync button."""
    invoke("sync")
    print("OK: sync triggered.")


MIRROR_DIR = os.path.join("decks", "_anki-mirror")


def _safe_name(deck_name):
    # Same sanitizing as apkg_to_cards.write_cards_json -> consistent file names.
    return re.sub(r"[^\w.+-]+", "_", deck_name).strip("_")


def _decode_apkg(apkg_path, outdir):
    """apkg -> cards.json via apkg_to_cards."""
    atc = _apkg_to_cards()
    con, tmp = atc.open_collection(apkg_path)
    try:
        by_deck, warnings = atc.extract(con)
    finally:
        con.close()
        os.unlink(tmp)
    files = atc.write_cards_json(by_deck, outdir)
    return files, warnings


def mirror(deck_names=None):
    """Mirrors Anki decks into the repo: decks/_anki-mirror/<deck>.apkg (with
    scheduling — a real backup, rebuild-ready) plus decoded cards.json per deck
    (greppable/diffable). Everything under decks/ is gitignored -> the mirror
    stays uncommitted; the commit guard blocks it as well.
    """
    if not deck_names:
        # Top-level decks only: exporting a parent includes its subdecks.
        deck_names = sorted({name.split("::")[0] for name in invoke("deckNames")})
    os.makedirs(MIRROR_DIR, exist_ok=True)

    ok, failed = [], []
    for deck in deck_names:
        safe = _safe_name(deck)
        apkg_path = os.path.join(MIRROR_DIR, safe + ".apkg")
        try:
            invoke("exportPackage", deck=deck, path=os.path.abspath(apkg_path), includeSched=True)
            files, warnings = _decode_apkg(apkg_path, os.path.join(MIRROR_DIR, safe + "_cards"))
        except (AnkiConnectError, RuntimeError, OSError) as e:
            # e.g. a filtered deck — skip, keep mirroring the rest.
            failed.append((deck, str(e)))
            continue
        total = sum(n for _, _, n in files)
        if total == 0:  # empty deck (e.g. unused default deck): no point keeping it
            os.unlink(apkg_path)
            shutil.rmtree(os.path.join(MIRROR_DIR, safe + "_cards"), ignore_errors=True)
            failed.append((deck, "empty deck, nothing to mirror"))
            continue
        ok.append((deck, apkg_path, total))
        for w in warnings:
            print(f"  warning ({deck}): {w}")

    for deck, apkg_path, total in ok:
        print(f"OK: '{deck}' -> {apkg_path} ({total} notes decoded)")
    for deck, msg in failed:
        print(f"SKIPPED: '{deck}' — {msg}", file=sys.stderr)
    if not ok:
        raise AnkiConnectError("No deck could be mirrored.")
    print(f"Mirror: {len(ok)} deck(s) in {MIRROR_DIR}/ (gitignored, stays local).")


def main(argv):
    ap = argparse.ArgumentParser(
        description="Push/export/sync Anki decks via the local AnkiConnect add-on."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="check that Anki + AnkiConnect are reachable")

    p_push = sub.add_parser("push", help="import a built .apkg into Anki")
    p_push.add_argument("apkg", help="path to the .apkg to import")
    p_push.add_argument("--no-backup", action="store_true",
                        help="skip the automatic backup of affected decks")
    p_push.add_argument("--prune", action="store_true",
                        help="after the import, delete notes that were removed "
                             "from the package (GUID diff; needs the backup)")

    p_export = sub.add_parser("export", help="export a deck to .apkg (with scheduling)")
    p_export.add_argument("deck", help="Anki deck name, e.g. 'Biology::Respiration'")
    p_export.add_argument("out", help="target .apkg path")

    sub.add_parser("sync", help="trigger AnkiWeb sync")

    p_mirror = sub.add_parser(
        "mirror", help="mirror Anki decks into decks/_anki-mirror/ (.apkg + cards.json)"
    )
    p_mirror.add_argument("decks", nargs="*",
                          help="deck names (default: all top-level decks)")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "ping":
            ping()
        elif args.cmd == "push":
            push(args.apkg, backup=not args.no_backup, prune=args.prune)
        elif args.cmd == "export":
            export(args.deck, args.out)
        elif args.cmd == "sync":
            sync()
        elif args.cmd == "mirror":
            mirror(args.decks)
    except AnkiConnectError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: file not found: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
