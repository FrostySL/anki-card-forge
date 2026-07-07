---
description: Forge Anki cards from a source (full pipeline, quality-checked)
argument-hint: <sources/<topic>/file.pdf | folder | extracted .md> [wishes, e.g. language/count]
---

Create Anki cards from: $ARGUMENTS

Follow the workflow in CLAUDE.md exactly — short version:

1. If `sources/<topic>/context.md` exists (any spelling, e.g. `Kontext.md`),
   read it FIRST — it steers selection and emphasis.
2. If the `extracted/<topic>/` mirror for the source is missing or stale, run
   `./tools/prep.sh <input>` (routes `--lang` to OCR if the user asked for
   another language).
3. Read the extracted `.md`. Check `<name>.figures.md` / the `· N fig.`
   markers; view figure crops under `extracted/<topic>/figures/` for anything
   spatial/visual and decide about occlusion cards. No image may be
   overlooked.
4. Author the cards following the card-authoring skill (atomic, real
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
