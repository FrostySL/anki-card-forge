# Forge Anki cards from source material

**Input:** a source file under `sources/<topic>/`, a source folder, or an
already extracted Markdown file, plus any wishes about language, scope or count.
Use the source and wishes from the user's request.

Read `AGENTS.md` and `skills/card-authoring/SKILL.md` first and follow their rules. Task steps:

1. If `sources/<topic>/context.md` exists (any spelling, e.g. `Kontext.md`),
   read it FIRST — it steers selection and emphasis.
2. If the `extracted/<topic>/` mirror for the source is missing or stale, run
   `./tools/prep.sh <input>`. For scanned sources, pass `--lang` for the
   source's OCR language; the requested card language is a separate choice.
3. Read the extracted `.md`. Check `<name>.figures.md` / the `· N fig.`
   markers; view figure crops under `extracted/<topic>/figures/` for anything
   spatial/visual and decide about occlusion cards. No image may be
   overlooked.
4. Author the cards following `skills/card-authoring/SKILL.md` (atomic, real
   retrieval, format by knowledge type, grounding, tags,
   explanation/source in the collapsed box). Write
   `decks/<topic>/<name>.cards.json` — deck name `"<Topic>::<Title>"`.
5. Quality pipeline: `./tools/finish.sh decks/<topic>/<name>.cards.json`.
   For occlusion cards additionally `./tools/preview.sh` and LOOK at the
   PNGs (light AND dark) until the masks sit right.
6. Report: card count per type, checks run, output path. If AnkiConnect is
   reachable (`python3 tools/anki_connect.py ping`), import via
   `finish.sh --push` when the user asked for it — sync only on explicit
   request.
