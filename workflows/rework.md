# Rework an existing deck while preserving learning progress

**Input:** an Anki deck name or a fresh exported `.apkg` with scheduling,
plus the changes requested by the user.

Read `AGENTS.md`, especially "Changing an existing/learned deck" and the
AnkiConnect safeguards, and `skills/card-authoring/SKILL.md` first. Task steps:

On native Windows, use `.\forge.cmd anki`, `decode`, `build`, `diff` and
`validate` instead of the Python/shell commands below. Run `.\forge.cmd setup`
if `.\forge.cmd doctor` reports missing components. The decoder refuses to
write partial JSON when image-occlusion notes or unsupported field/deck layouts
would be lost. Keep the original package and edit those notes in Anki or through
`update-note`; do not rebuild them as another note type. Mirrors may contain a
partial JSON index with warnings; their original `.apkg` remains the complete backup.

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
   `explanation`/`source` on top. For type-in and reversed basic notes, preserve
   the raw third field as `more`; do not append it to `back` (which becomes the
   question on the reverse card).
4. Rebuild: `./tools/build.sh decks/<topic>/<name>_rebuild/*.cards.json "<out>.apkg"`.
5. Verify BEFORE any push:
   `python3 tools/deck_diff.py <export>.apkg <out>.apkg --strict`
   — the diff compares every package note and raw field, including occlusion
   and foreign types. It must show exactly the intended additions/removals/edits
   and ZERO cloze or safety warnings. Strict mode also rejects note-type,
   field-layout and card-ordinal changes and ambiguous comparisons. Added or
   removed notes are reported but do not by themselves fail the gate.
   Then `./tools/validate.sh <out>.apkg`.
6. Import updates notes in place (same GUIDs): push via AnkiConnect or manual
   import with "Update notes". `--prune` only if the user asked to REMOVE
   cards; sync only on explicit request.
