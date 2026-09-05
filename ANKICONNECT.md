# AnkiConnect integration (optional)

anki-card-forge can talk to a **running Anki desktop** through the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on: import built
decks without the *File → Import* dance, export decks for a progress-preserving
rebuild, trigger AnkiWeb sync, and keep a local backup mirror of your
collection.

**All of this is opt-in.** The core pipeline — author cards, build the `.apkg`,
lint/preview/validate — works exactly the same without AnkiConnect; you simply
import the `.apkg` by double-clicking it or via **File → Import** in Anki. If
you never install the add-on, nothing in this repo will miss it.

The tool talks to the running Anki app over plain HTTP, by default at
`127.0.0.1:8765` on your machine. It does not handle AnkiWeb passwords or
provider API keys. An explicit `sync` command asks Anki to send collection
data to AnkiWeb. Your AI assistant's handling of any files it reads is
separate; see [Privacy](README.md#privacy-local-files-and-your-ai-service).

---

## Setup (once)

On native Windows, first run `.\forge.cmd setup` in the project. Use
`.\forge.cmd anki` in place of `python3 tools/anki_connect.py` in every example
below. The managed Python includes `zstandard` and connects directly to Windows
Anki; no WSL path conversion or separate Python installation is needed:

```powershell
.\forge.cmd anki ping
.\forge.cmd anki push decks\Biology\respiration.apkg --dry-run
.\forge.cmd anki export "Biology::Respiration" decks\Biology\export.apkg
```

1. Open Anki desktop.
2. **Tools → Add-ons → Get Add-ons…** (German UI: *Extras → Erweiterungen →
   Erweiterungen herunterladen…*), enter the code **`2055492159`**, confirm.
3. **Restart Anki** — the add-on only starts its local server on startup.
4. Verify:

   ```bash
   python3 tools/anki_connect.py ping
   # OK: AnkiConnect v6 reachable, permission granted.
   ```

   On the very first contact AnkiConnect may show a permission dialog inside
   Anki — click **Yes**.

Keep **Anki open** while you use the tool. HTTP commands such as `ping` need
only Python's standard library, with no Docker. Commands that inspect modern
Anki exports/backups (including the backup comparison during `push`) also need
Python `zstandard` or the `zstd` CLI in the environment running the tool.

If AnkiConnect listens somewhere else (changed add-on config, different port),
point the tool at it: `ANKICONNECT_URL=http://127.0.0.1:8765` (default).

### WSL2 project with Anki on Windows

Under [WSL's default NAT networking](https://learn.microsoft.com/en-us/windows/wsl/networking),
`127.0.0.1` from Linux refers to the Linux environment. If Anki runs on Windows,
run `tools/anki_connect.py` with **Windows Python** so it reaches the Windows
loopback server. Keep AnkiConnect at `127.0.0.1:8765`; this approach requires no
firewall or add-on binding changes.

From Bash in the WSL project directory, set `WINPY` to the WSL path of your
installed Windows `python.exe` (replace the placeholder below). Install
`zstandard` in that interpreter for modern Anki exports and backup comparisons.
Convert the script path and every package path to Windows paths with `wslpath -w`:

```bash
WINPY='/mnt/c/path/to/python.exe'
"$WINPY" -m pip install --user zstandard
ANKI_SCRIPT=$(wslpath -w "$PWD/tools/anki_connect.py")
"$WINPY" "$ANKI_SCRIPT" ping
"$WINPY" "$ANKI_SCRIPT" decks
```

Build and validate in WSL with `finish.sh` **without `--push`**, then import
separately through Windows Python:

```bash
./tools/finish.sh decks/Biology/respiration.cards.json
"$WINPY" "$ANKI_SCRIPT" push "$(wslpath -w "$PWD/decks/Biology/respiration.apkg")"
# To export an existing deck with scheduling:
"$WINPY" "$ANKI_SCRIPT" export "Biology::Respiration" "$(wslpath -w "$PWD/decks/Biology/export.apkg")"
```

Use the same Windows interpreter for `mirror`, `restore`, and other AnkiConnect
commands. Backups still live in the project's `decks/_anki-backups/` directory.
Sync remains a separate, explicit action after checking the imported deck.

## Commands

Export decoding preserves basic, reversed basic, cloze and type-in cards,
including their GUIDs and media. The repository's image-occlusion notes are
currently skipped by the decoder with a warning; do not use export → decode →
rebuild for learned image-occlusion decks. Their normal build, preview and
validation paths remain available. A mixed export must be checked for skipped
notes before any rework import or prune.

```bash
python3 tools/anki_connect.py ping                          # connectivity check
python3 tools/anki_connect.py decks                         # list all deck names
python3 tools/anki_connect.py push <file.apkg>              # import into Anki
python3 tools/anki_connect.py push <file.apkg> --dry-run    # only show what a push would do
python3 tools/anki_connect.py push <file.apkg> --prune      # ... and delete removed cards
python3 tools/anki_connect.py push <file.apkg> --no-backup  # ... without the auto-backup
python3 tools/anki_connect.py export "<Deck>" <out.apkg>    # export WITH scheduling
python3 tools/anki_connect.py sync                          # trigger AnkiWeb sync
python3 tools/anki_connect.py mirror [deck ...]             # snapshot decks locally
python3 tools/anki_connect.py update-note <nid> --field "Name=<html>"   # edit one note in place
python3 tools/anki_connect.py restore --list                # list backup snapshots
python3 tools/anki_connect.py restore [<timestamp>]         # restore and verify old content (default: newest)
```

### `ping`

Checks that Anki is running, the add-on is installed and permission is granted.
Every other command performs the same reachability check implicitly and fails
with the same guidance, so `ping` is mainly for a quick sanity check.

### `decks`

Prints every deck name in the collection, one per line. `export`, `mirror`
and the rework workflow need deck names **exactly** as Anki knows them
(including the `::` hierarchy) — this saves opening Anki just to look them up.

### `push <file.apkg>`

Imports a built package into the open collection — the automated version of
*File → Import*. Two things to know:

- **A push can only add or update, never delete.** Anki merges imports: notes
  with a known GUID and newer modification time can update fields (learning progress stays), unknown
  GUIDs become new notes. Even pushing an empty deck of the same name leaves
  your cards untouched.
- **Before the import, affected decks are backed up automatically** (see
  [Backups](#backups--restore)). Disable only deliberately with `--no-backup`.

After the import, push reports `N new note(s), M matched existing GUIDs`
(compared with the fresh backup). These are identity counts, not proof that
every matched note changed: Anki may skip older/equal note versions or note-type
conflicts. Conflicting note types need [`update-note`](#update-note-nid---field-namehtml).

`--dry-run` shows exactly that report (plus the `--prune` deletion list, if
given) **without importing anything** — the backup is still written, since it
doubles as the diff baseline. Use it to answer "what would this push change?"
before touching the collection.

`--prune` additionally deletes notes that were removed from the deck — see
[Removing cards](#removing-cards-push---prune).

### `export "<Deck>" <out.apkg>`

Exports one deck (subdecks included) **with scheduling** — equivalent to
*File → Export → .apkg, include scheduling*. This is the entry point for the
progress-preserving rebuild: feed the export to `tools/apkg_to_cards.py` to get
editable `cards.json` with the note GUIDs preserved (see README, *Updating an
already-learned deck*).

### `sync`

Triggers the same AnkiWeb sync as the sync button in Anki's toolbar — nothing
more. Sync is **never** run implicitly by any other command; push first, check
the result in Anki, then sync (that is also how `finish.sh --push --sync`
orders it).

### `mirror [deck ...]`

Local snapshot of your collection into `decks/_anki-mirror/`. Without
arguments it takes every top-level deck (subdecks ride along, empty decks are
skipped); with arguments only the named decks. Per deck you get:

- `<Deck>.apkg` — full export **with scheduling** (a real backup), and
- `<Deck>_cards/*.cards.json` — the decoded cards, GUIDs included, so the
  mirror is greppable/diffable (e.g. to check for duplicate cards before
  authoring a new deck).

The mirror is stored locally; its folder is gitignored and additionally
blocked by the commit guard. These protections prevent commits, not access
by your AI assistant or other software.

### `update-note <nid> --field "Name=<html>"`

Updates fields of **one existing note in place** — note type, GUID and
scheduling stay untouched. Use it for small, surgical edits ("add an
explanation to this one card") and especially for notes whose **note type was
not built by this repo**: a `.apkg` push cannot reach those (Anki skips
imported notes whose GUID matches but whose note type differs), an in-place
field update can.

- `nid` is the note id (visible in the mirror decode output, or via Anki's
  browser). Field names are the note type's real names (e.g. a German Basic
  clone has `Vorderseite`/`Rückseite`) — a wrong name is refused with the
  list of valid ones before anything is written.
- The containing deck is backed up first, exactly like `push`
  (`--no-backup` to skip).
- `--field` is repeatable for several fields in one call.

## Removing cards (`push --prune`)

Because imports only merge, cards you deliberately cut from a reworked deck
would linger in Anki forever. `--prune` is the one sanctioned way to remove
them:

```bash
python3 tools/anki_connect.py push decks/<topic>/<name>.apkg --prune
# or: ./tools/finish.sh decks/<topic>/<name>.cards.json --push --prune
```

What it does, in order:

1. Takes the automatic backup (prune refuses to run with `--no-backup` — the
   backup is both its diff baseline and your restore path).
2. Computes the diff **before importing anything**: notes that live in a deck
   the package writes to, but whose GUID appears nowhere in the package.
   Notes that merely moved to another deck inside the package keep their GUID
   and are kept.
3. **Refuses the entire push — nothing imported, nothing deleted — if a deck
   shares no GUID at all with the package.** That is the telltale sign of a
   rebuild that lost the GUIDs; pruning would replace the whole deck and wipe
   its learning progress. Fix the rebuild instead (`tools/apkg_to_cards.py`
   preserves GUIDs).
4. Imports the package, then deletes exactly the diffed notes — each one is
   listed in the output.

Made a mistake? Run `restore <snapshot>`: deleted notes return with their
saved scheduling; surviving notes recover old content while keeping their
current learning progress. A plain push of an older backup can be skipped by Anki.

## Backups & restore

Every `push` (unless `--no-backup`) backs up existing destination decks and
the actual current decks of matching GUIDs, including notes moved to another
deck or cards split across decks. AnkiConnect does not expose GUIDs in its note
lookup API, so the tool scans temporary exports of all top-level decks first.
This adds export time for large collections; scan files stay local and are
removed, and only affected decks are retained as backups:

```
decks/_anki-backups/<YYYYMMDD-HHMMSS-nanoseconds-unique>/<Deck>.apkg
```

- Stored locally and gitignored; the commit guard also blocks committing them.
- Each snapshot has a unique directory and becomes available only after every
  export succeeds. Failed or in-progress snapshots never replace completed ones.
- The **10 newest complete** snapshots are kept; older ones are pruned only
  after the new snapshot is complete. Legacy timestamp folders remain readable.
- **Use `restore` for old content.** It stages the selected snapshot before
  taking a fresh backup, so retention cannot delete its inputs mid-restore:

  ```bash
  python3 tools/anki_connect.py restore --list        # what snapshots exist?
  python3 tools/anki_connect.py restore               # restore the NEWEST snapshot
  python3 tools/anki_connect.py restore 20260707-100305   # or a specific one
  ```

  A disposable package copy receives newer note modification times so Anki
  actually accepts older backed-up content. The original backup stays unchanged.
  Afterwards, a fresh export verifies every restored GUID, field, tag and card
  ordinal, and checks that existing card scheduling and review history stayed
  unchanged. Success
  is reported only when these checks pass. Missing notes return with the
  snapshot's scheduling; existing notes retain their current progress.
  Modern compressed exports are staged in archive framing supported by
  AnkiConnect, including their media; no snapshot files are rewritten in place.

  Restore refuses changed note types, field layouts or card ordinals before
  importing, because those changes can affect existing cards and their progress.
  Notes added since the snapshot remain, and deck placement and note-type
  styling are not rolled back. For structural or full collection recovery,
  use Anki's own collection backups. Restoring content always makes a fresh
  pre-restore backup and never syncs automatically.

Independent of this repo, Anki keeps its own automatic collection backups
(*File → Restore from backup*; on Linux under
`~/.local/share/Anki2/<profile>/backups/`) — that is the safety net of last
resort, covering also everything you do manually in Anki.

## Safeguards (design)

The tool is built so that a slip — yours or the AI's — cannot destroy a
collection:

| Risk | Guard |
|---|---|
| Deleting decks/notes via the API | `invoke()` only accepts a small allowlist of actions (`SAFE_ACTIONS`); `deleteDecks`, `deleteNotes` & co. are refused before any request is sent. Override only via `ANKICONNECT_ALLOW_UNSAFE=1`, which nothing in this repo sets. |
| Bad content overwriting good cards | GUID-aware backups before every push; `restore` forces old content to import and verifies the result. |
| "Empty deck in → empty deck out" | Structurally impossible: imports merge, and prune ignores decks that have no cards in the package. |
| Rebuild lost the GUIDs → prune would wipe progress | Zero-overlap refusal aborts the push before the import. |
| Broken state reaching AnkiWeb/phone | Sync only ever runs as an explicit command, after the import can be checked. |

For the rules the AI itself follows (never `--no-backup`/`--prune`/`sync`
unasked, never weaken the allowlist), see [AGENTS.md](AGENTS.md).

## Typical workflows

**New deck, straight into Anki (and phone):**

```bash
./tools/finish.sh decks/Biology/respiration.cards.json --push          # build+checks+import
# check the deck in Anki, then, if wanted:
python3 tools/anki_connect.py sync
```

**Rework a learned deck — including removing cards:**

```bash
python3 tools/anki_connect.py export "Biology::Respiration" export.apkg
python3 tools/apkg_to_cards.py export.apkg -o decks/Biology/respiration_rebuild
# edit the cards.json (keep the guid fields!), then:
./tools/build.sh decks/Biology/respiration_rebuild/*.cards.json rebuilt.apkg
python3 tools/anki_connect.py push rebuilt.apkg --prune
```

**Periodic local backup of everything:**

```bash
python3 tools/anki_connect.py mirror
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Connection refused` on every command | Anki is not running, or it was not restarted after installing the add-on. Open/restart Anki. |
| Still unreachable after restart | Is the add-on really installed? **Tools → Add-ons** should list "AnkiConnect". Quick check without this tool: open `http://127.0.0.1:8765` in a browser while Anki runs — it should answer `AnkiConnect`. |
| `permission denied` | AnkiConnect is waiting for you to confirm a permission dialog inside the Anki window — click **Yes**, retry. |
| `Prune refused: … 0 shared GUIDs` | Your rebuilt deck carries fresh GUIDs instead of the originals. Rebuild from an export via `tools/apkg_to_cards.py` (preserves GUIDs) — do not force the prune. |
| `sync` fails | Anki is not logged in to AnkiWeb (Anki: sync button → log in), or a full-sync decision is pending in the GUI — resolve it there once. |
| Non-default port/host | Set `ANKICONNECT_URL` (and check the add-on's config in Anki). Slow machines: raise `ANKICONNECT_TIMEOUT` (seconds, default 60). |
