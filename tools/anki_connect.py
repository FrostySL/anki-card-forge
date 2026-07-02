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
    python3 tools/anki_connect.py push <file.apkg>
    python3 tools/anki_connect.py export "<Deck::Name>" <out.apkg>
    python3 tools/anki_connect.py sync
    python3 tools/anki_connect.py mirror [deck ...]

Endpoint overridable via ANKICONNECT_URL (default http://127.0.0.1:8765).
Pure local HTTP — no credentials, no Docker; the .apkg build itself is
unaffected and still goes through Docker as usual.
"""
import argparse
import json
import os
import re
import sys
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


def invoke(action, **params):
    """Calls one AnkiConnect action, returns its `result`.

    Raises AnkiConnectError if Anki/AnkiConnect is unreachable or the response
    envelope carries a non-null `error`.
    """
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


def push(apkg_path):
    """Imports a built .apkg into Anki's collection (importPackage)."""
    if not os.path.isfile(apkg_path):
        raise FileNotFoundError(apkg_path)
    invoke("importPackage", path=os.path.abspath(apkg_path))
    print(f"OK: imported {apkg_path} into Anki.")


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
    """apkg -> cards.json via apkg_to_cards (same tools/ folder, lazy import)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import apkg_to_cards

    con, tmp = apkg_to_cards.open_collection(apkg_path)
    try:
        by_deck, warnings = apkg_to_cards.extract(con)
    finally:
        con.close()
        os.unlink(tmp)
    files = apkg_to_cards.write_cards_json(by_deck, outdir)
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
            push(args.apkg)
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
