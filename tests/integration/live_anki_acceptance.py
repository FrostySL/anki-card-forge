"""Explicit phases for the optional live Windows Anki test profile.

prepare builds a unique synthetic deck without contacting Anki. After confirming
the GUI profile is test, run import --profile-confirmed test, review one basic
and one cloze card in the GUI, then run rework, push --profile-confirmed test,
and verify. Every phase after prepare requires the printed --directory. No phase
syncs, prunes, disables backups, or edits unrelated decks. Test decks stay visible.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import anki_connect as ac
import apkg_to_cards as decoder
from check_pipeline import write_diagram


def command(*args):
    result = subprocess.run([sys.executable, str(ROOT / "tools/forge.py"),
                             "--backend", "native", *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    result.check_returncode()
    return result.stdout


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def package_snapshot(path):
    conn, temporary = decoder.open_collection(str(path))
    try:
        # GUID + ordinal identify a learned card; IDs and all scheduling fields
        # must also stay fixed across the live re-import, as must its revlog.
        notes = conn.execute("select guid,id,mid,flds from notes order by guid").fetchall()
        cards = conn.execute(
            "select n.guid,c.id,c.nid,c.ord,c.type,c.queue,c.due,c.ivl,c.factor,c.reps,"
            "c.lapses,c.left,c.odue,c.odid,c.data from cards c join notes n on n.id=c.nid "
            "order by n.guid,c.ord").fetchall()
        reviews = conn.execute("select * from revlog order by id").fetchall()
        decoded, warnings = decoder.extract(conn)
        if warnings:
            raise AssertionError(f"Unexpected decode warnings: {warnings}")
        return {"notes": notes, "cards": cards, "reviews": reviews, "decks": decoded}
    finally:
        conn.close()
        os.unlink(temporary)


def owned_state(directory):
    path = directory.resolve()
    if path.parent != ROOT / "decks" or not path.name.startswith("_live-") or not path.name.endswith("_rebuild"):
        raise ValueError("Use the owned decks/_live-..._rebuild directory printed by prepare.")
    state_file = path / "state.json"
    return path, state_file, json.loads(state_file.read_text(encoding="utf-8"))


def prepare():
    run_id = uuid.uuid4().hex[:12]
    directory = ROOT / "decks" / f"_live-{run_id}_rebuild"
    directory.mkdir(parents=True)
    deck = f"Windows acceptance::{run_id}"
    media = directory / "blocks.png"
    write_diagram(media)
    basic_guid, cloze_guid = f"acf-{run_id}-basic", f"acf-{run_id}-cloze"
    cards = [
        {"type": "basic", "guid": basic_guid, "front": "What flows between these two blocks?",
         "back": f'Data.<br><img src="{media.relative_to(ROOT).as_posix()}">'},
        {"type": "basic", "reverse": True, "guid": f"acf-{run_id}-reverse", "front": "JSON",
         "back": "JavaScript Object Notation"},
        {"type": "cloze", "guid": cloze_guid,
         "text": "The {{c1::red}} block sends data to the {{c2::blue}} block."},
        {"type": "typein", "guid": f"acf-{run_id}-typein", "front": "Type the image format abbreviation.", "back": "PNG"},
    ]
    for card in cards:
        card["tags"] = ["synthetic_windows_acceptance", run_id]
    save(directory / "original.cards.json", {"deck": deck, "cards": cards})
    command("build", directory / "original.cards.json", directory / "initial.apkg")
    command("validate", directory / "initial.apkg")
    state = {"deck": deck, "phase": "prepared", "basic_guid": basic_guid, "cloze_guid": cloze_guid}
    save(directory / "state.json", state)
    print(f"Prepared {deck}. Directory: {directory}")


def import_initial(directory, state):
    assert state["phase"] == "prepared", "The initial import phase has already run."
    assert state["deck"] not in ac.invoke("deckNames"), "Refusing to overwrite an existing test deck."
    ac.push(str(directory / "initial.apkg"))
    state["phase"] = "imported"
    print("Review a basic and a cloze card in this deck in the GUI, then run rework.")


def rework(directory, state):
    assert state["phase"] == "imported", "Import the fixture and review it first."
    original = directory / "learned.apkg"
    ac.export(state["deck"], str(original))
    before = package_snapshot(original)
    assert len(before["notes"]) == 4 and len(before["cards"]) == 6, "Unexpected fixture counts."
    reviewed = {row[0] for row in before["cards"] if row[9] > 0}
    assert {state["basic_guid"], state["cloze_guid"]} <= reviewed, "Review one basic and one cloze card before rework."
    assert before["reviews"], "The exported fixture has no review history."
    save(directory / "before.json", before)
    command("decode", original, "-o", directory / "decoded")
    files = sorted((directory / "decoded").glob("*.cards.json"))
    assert len(files) == 1, "Export unexpectedly contains more than the unique test deck."
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["deck"] == state["deck"] and len(data["cards"]) == 4
    tokens_before = {}
    for card in data["cards"]:
        if card["guid"] == state["basic_guid"]:
            assert "Data." in card["back"]
            card["back"] = card["back"].replace("Data.", "A data message.", 1)
        elif card["guid"] == state["cloze_guid"]:
            tokens_before[card["guid"]] = re.findall(r"\{\{c\d+::.*?\}\}", card["text"])
            card["text"] = "<div>" + card["text"] + "</div>"
            assert re.findall(r"\{\{c\d+::.*?\}\}", card["text"]) == tokens_before[card["guid"]]
    save(files[0], data)
    # Ensure updated fields receive a later modification second than the export.
    time.sleep(1.1)
    command("build", files[0], directory / "reworked.apkg")
    output = command("diff", original, directory / "reworked.apkg", "--strict")
    assert "0 added, 0 removed, 2 changed" in output, "Rework changed more than the intended two notes."
    after = package_snapshot(directory / "reworked.apkg")
    assert {(n[0], n[2]) for n in before["notes"]} == {(n[0], n[2]) for n in after["notes"]}
    assert {(c[0], c[3]) for c in before["cards"]} == {(c[0], c[3]) for c in after["cards"]}
    command("validate", directory / "reworked.apkg")
    ac.push(str(directory / "reworked.apkg"), dry_run=True)
    state["phase"] = "rework-ready"
    state["expected_fields"] = {note[0]: note[3] for note in after["notes"]}
    print("Rework package verified and dry-run completed; push is the next explicit phase.")


def push_rework(directory, state):
    assert state["phase"] == "rework-ready", "Complete and inspect the rework phase first."
    backups_before = set(Path(ac.BACKUP_DIR).rglob("*.apkg"))
    ac.push(str(directory / "reworked.apkg"))
    backups = set(Path(ac.BACKUP_DIR).rglob("*.apkg")) - backups_before
    assert backups, "The update did not create a new automatic backup."
    state["backups"] = [str(path) for path in sorted(backups)]
    state["phase"] = "pushed"


def verify(directory, state):
    assert state["phase"] == "pushed", "Push the verified rework first."
    ac.export(state["deck"], str(directory / "after.apkg"))
    before = json.loads((directory / "before.json").read_text(encoding="utf-8"))
    after = package_snapshot(directory / "after.apkg")
    # JSON round-trip gives a uniform list representation for SQLite tuples.
    after = json.loads(json.dumps(after))
    assert before["cards"] == after["cards"], "Card identities or scheduling changed."
    assert before["reviews"] == after["reviews"], "Review history changed."
    assert [n[:3] for n in before["notes"]] == [n[:3] for n in after["notes"]], "Note identities/types changed."
    assert state["expected_fields"] == {n[0]: n[3] for n in after["notes"]}, "Imported fields differ from the verified package."
    backup_snapshots = [package_snapshot(Path(path)) for path in state["backups"]]
    assert any(json.loads(json.dumps(s))["cards"] == before["cards"] for s in backup_snapshots), \
        "Automatic backup did not preserve the learned fixture."
    save(directory / "verification.json", {"passed": True, "deck": state["deck"],
         "notes": len(after["notes"]), "cards": len(after["cards"]), "reviews": len(after["reviews"]),
         "backups": state["backups"], "sync": False, "prune": False})
    state["phase"] = "verified"
    print("PASS: intended fields updated; GUIDs, note types, card IDs/ordinals, scheduling and reviews preserved.")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "import", "rework", "push", "verify"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--profile-confirmed", choices=("test",))
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.directory:
            parser.error("prepare chooses a new unique directory; omit --directory")
        prepare()
        return
    if not args.directory:
        parser.error("--directory is required for all phases after prepare")
    if args.phase in {"import", "push"} and args.profile_confirmed != "test":
        parser.error("Confirm the selected GUI profile is test, then supply --profile-confirmed test")
    directory, state_file, state = owned_state(args.directory)
    {"import": import_initial, "rework": rework, "push": push_rework, "verify": verify}[args.phase](directory, state)
    save(state_file, state)


if __name__ == "__main__":
    main()
