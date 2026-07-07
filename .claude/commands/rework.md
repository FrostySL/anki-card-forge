---
description: Rework an already-learned deck WITHOUT losing progress (GUID-preserving)
argument-hint: <Anki deck name or exported .apkg> [what to change]
---

Rework, keeping the learning progress: $ARGUMENTS

Follow CLAUDE.md "Changing an existing/learned deck" exactly — short version:

1. Get a FRESH export with scheduling — never rebuild from a stale
   repo cards.json: `python3 tools/anki_connect.py export "<Deck>" <tmp>.apkg`
   (or ask the user for File → Export → .apkg with scheduling).
2. Decode with GUIDs + media preserved:
   `python3 tools/apkg_to_cards.py <export>.apkg -o decks/<topic>/<name>_rebuild`.
   Heed the foreign-note-type warnings: such notes can ONLY be changed via
   `update-note`, never by rebuilding (would duplicate them).
3. Edit the cards.json — only the requested changes. Cloze: keep the
   `{{cN::…}}` tokens byte-identical (ord = cN−1 hangs off them). The decoded
   fields already contain the "details & source" box — do NOT add
   `explanation`/`source` on top.
4. Rebuild: `./tools/build.sh decks/<topic>/<name>_rebuild/*.cards.json "<out>.apkg"`.
5. Verify BEFORE any push:
   `python3 tools/deck_diff.py <export>.apkg <out>.apkg --strict`
   — the diff must show exactly the intended changes and ZERO cloze-number
   warnings. Then `./tools/validate.sh <out>.apkg`.
6. Import updates notes in place (same GUIDs): push via AnkiConnect or manual
   import with "Update notes". `--prune` only if the user asked to REMOVE
   cards; sync only on explicit request.
