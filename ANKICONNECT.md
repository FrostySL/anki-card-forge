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

Why AnkiConnect (and not a headless AnkiWeb login)? Everything runs as plain
HTTP against `127.0.0.1:8765` on your own machine: **no password, no API key,
no cloud** — the only thing the tool can talk to is the Anki window you have
open. That is the right trust model for a public repo.

---

## Setup (once)

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

No Docker, no pip: `tools/anki_connect.py` is pure Python stdlib. The only
runtime requirement is that **Anki is open** while you use it.

If AnkiConnect listens somewhere else (changed add-on config, different port),
point the tool at it: `ANKICONNECT_URL=http://127.0.0.1:8765` (default).

## Commands

```bash
python3 tools/anki_connect.py ping                          # connectivity check
python3 tools/anki_connect.py push <file.apkg>              # import into Anki
python3 tools/anki_connect.py push <file.apkg> --prune      # ... and delete removed cards
python3 tools/anki_connect.py push <file.apkg> --no-backup  # ... without the auto-backup
python3 tools/anki_connect.py export "<Deck>" <out.apkg>    # export WITH scheduling
python3 tools/anki_connect.py sync                          # trigger AnkiWeb sync
python3 tools/anki_connect.py mirror [deck ...]             # snapshot decks locally
```

### `ping`

Checks that Anki is running, the add-on is installed and permission is granted.
Every other command performs the same reachability check implicitly and fails
with the same guidance, so `ping` is mainly for a quick sanity check.

### `push <file.apkg>`

Imports a built package into the open collection — the automated version of
*File → Import*. Two things to know:

- **A push can only add or update, never delete.** Anki merges imports: notes
  with a known GUID get their fields updated (learning progress stays), unknown
  GUIDs become new notes. Even pushing an empty deck of the same name leaves
  your cards untouched.
- **Before the import, affected decks are backed up automatically** (see
  [Backups](#backups--restore)). Disable only deliberately with `--no-backup`.

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

The mirror folder is gitignored and additionally blocked by the commit guard —
it stays on your machine.

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

Made a mistake? Push the backup: the deleted notes come back **with their
scheduling**, and the surviving notes revert to their previous content.

## Backups & restore

Every `push` (unless `--no-backup`) first exports each deck that exists in
Anki *and* is touched by the package:

```
decks/_anki-backups/<YYYYMMDD-HHMMSS>/<Deck>.apkg     # with scheduling
```

- Gitignored — backups never leave your machine.
- The **10 newest** timestamp folders are kept, older ones are pruned
  automatically.
- **Restore = push the backup:**

  ```bash
  python3 tools/anki_connect.py push decks/_anki-backups/<timestamp>/<Deck>.apkg
  ```

  Same-GUID notes revert to the backed-up content; notes deleted by a prune
  are re-created with their scheduling.

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
| Bad content overwriting good cards | Auto-backup of affected decks before every push; restore by pushing the backup. |
| "Empty deck in → empty deck out" | Structurally impossible: imports merge, and prune ignores decks that have no cards in the package. |
| Rebuild lost the GUIDs → prune would wipe progress | Zero-overlap refusal aborts the push before the import. |
| Broken state reaching AnkiWeb/phone | Sync only ever runs as an explicit command, after the import can be checked. |

For the rules the AI itself follows (never `--no-backup`/`--prune`/`sync`
unasked, never weaken the allowlist), see `CLAUDE.md`.

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
