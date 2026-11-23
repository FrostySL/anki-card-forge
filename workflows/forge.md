# Forge Anki cards from source material

**Input:** a source file under `sources/<topic>/`, a source folder, or an
already extracted Markdown file, plus any wishes about language, scope or count.
Use the source and wishes from the user's request.

Read `AGENTS.md` and `skills/card-authoring/SKILL.md` first and follow their rules. Task steps:

On Windows, check `.\forge.cmd doctor`, then run `.\forge.cmd setup` if needed.
Use `.\forge.cmd prep`, `finish`, `preview` and `anki` in place of the Linux
commands below. All remaining arguments and quality gates are the same.

1. If `sources/<topic>/context.md` exists (any spelling, e.g. `Kontext.md`),
   read it FIRST — it steers selection and emphasis.
2. If the `extracted/<topic>/` mirror for the source is missing or stale, run
   `./tools/prep.sh <input>`. For scanned sources, pass `--lang` for the
   source's OCR language; the requested card language is a separate choice.
3. Read the extracted `.md`. Check `<name>.figures.md` / the `· N fig.`
   markers; view figure crops under `extracted/<topic>/figures/` for anything
   spatial/visual. For every card, include a useful explanatory source graphic
   by default when available, even if the text explains the same concept.
   Use `back` for ordinary basic cards and `extra` for cloze cards so the image
   is visible after answering; keep supplementary details and citations in
   their collapsed fields. Render and crop the PDF page if extraction misses
   a diagram. Use occlusion only for spatial retrieval; skip decorative images.
4. Author the cards following `skills/card-authoring/SKILL.md` (atomic, real
   retrieval, format by knowledge type, grounding, tags, visual feedback,
   supplementary explanation/source in the collapsed box). Write
   `decks/<topic>/<name>.cards.json` — deck name `"<Topic>::<Title>"`.
5. **Separate front-only review:** follow the card-authoring skill's review pass
   for every generated question, including reversed directions and individual
   cloze/occlusion variants. Read each front without its answer or source;
   rewrite missing-context cues and book/chapter framing, then check the answer
   against the source. Keep citations in the collapsed `source` field.
6. Quality pipeline: `./tools/finish.sh decks/<topic>/<name>.cards.json`.
   Additionally run `./tools/preview.sh` and LOOK at the PNGs (light AND dark)
   for every changed image layout. Check crop completeness, readable labels,
   placement and occlusion masks. These checks do not replace the front-only
   review.
7. Report: card count per type, checks run, output path. If AnkiConnect is
   reachable (`python3 tools/anki_connect.py ping`), import via
   `finish.sh --push` when the user asked for it — sync only on explicit
   request.
