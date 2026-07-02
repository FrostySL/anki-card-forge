# Anki-Karten

Turn **lecture scripts, books, slides and notes** into high-quality **Anki
flashcards** — together with [Claude Code](https://claude.com/claude-code).
Works for **any subject** and produces cards in **any language you ask for**.

## The idea

The AI is Claude itself: you drop a file into `sources/<topic>/`, tell Claude in
the chat *"make cards from this"*, Claude reads the file, writes the cards
following an evidence-based methodology (the `card-authoring` skill), checks its
own work, and a small Docker container packs everything into a ready-to-import
`.apkg` file. **No external LLM call, no API key** — Docker only does the dumb
"card JSON → `.apkg`" part via the [`genanki`](https://github.com/kerrickstaley/genanki)
library.

```
sources/<topic>/script.pdf  →  (Claude reads + authors cards)  →  decks/<topic>/script.apkg  →  import into Anki
```

What makes the cards good rather than just numerous:

- **Evidence-based card rules** — atomicity, active retrieval, no hint leaks,
  format by knowledge type (see `.claude/skills/card-authoring/`, with sources).
- **Grounding check** — a heuristic verifies that every answer actually appears
  in the source text, so invented "facts" surface before you learn them.
- **Visual self-review** — cards are rendered as PNGs (light **and** Anki night
  mode) and inspected before delivery; image-occlusion masks are checked visually.
- **Real-engine validation** — every `.apkg` is imported and rendered with Anki's
  actual backend before it is handed to you.

## Requirements

- **[Claude Code](https://claude.com/claude-code)** (the AI that writes the cards)
- **Docker** (packs cards into `.apkg`, renders previews, runs OCR)

Nothing else — all Python dependencies live inside the Docker images.

## Quick start

```bash
git clone https://github.com/FrostySL/Anki-Karten
cd Anki-Karten
docker build -t anki-cards .             # slim builder image (one-off)
git config core.hooksPath .githooks      # commit guard (see below, one-off)
```

1. Put a source into `sources/<topic>/` (PDF, text, Markdown …) — one subfolder
   per topic, e.g. `sources/Biology/`.
2. Ask Claude in the chat: **"Create Anki cards from sources/Biology/respiration.pdf."**
3. Claude produces `decks/Biology/respiration.apkg`.
4. Import into Anki via **File → Import** (or double-click).

The larger images (preview/OCR, source extraction) are built automatically the
first time the corresponding `tools/*.sh` runs.

### Any topic, any language

The project is deliberately generic — biology, law, math, software engineering,
history: if it fits in a PDF or text file, it can become cards. Cards default to
the language of your source material. Want something else? Just tell Claude:

> "Make the cards from sources/Histoire/revolution.pdf — cards in French, please."

For scanned PDFs in other languages, add the Tesseract language pack to
`Dockerfile.extract` and pass `--lang` (e.g. `./tools/extract.sh … --lang eng+fra`).

Optionally place a `context.md` next to your sources (what the material is for,
where the focus lies, what the exam covers) — Claude reads it first and weights
the cards accordingly.

## Saving tokens: run the extraction toolchain yourself

Claude normally runs the whole pipeline for you. But the **source preparation**
step (PDF → Markdown + figure crops) is pure tooling — no AI involved — and you
can run it yourself before starting the chat, so Claude doesn't spend tokens
babysitting Docker:

```bash
./tools/prep.sh sources/<topic>/            # whole folder, or a single PDF
```

This produces, per source file:

- `extracted/<topic>/<name>.md` — machine-readable Markdown with page markers
  (`<!-- p. 12 -->`), scanned pages OCR'd and marked `(OCR)`,
- `extracted/<topic>/<name>.figures.md` — an index of the figures per page,
- `extracted/<topic>/figures/<name>_p<page>_<i>.png` — cropped figures (for
  image-occlusion cards and cheap visual checks).

Then tell Claude *"the sources are already prepared — make cards from
extracted/<topic>/…"* and it skips straight to reading and authoring. Everything
else (lint, grounding, preview, build, validate) is also runnable by hand — see
the tools table below.

## Card types

- **basic** — question/answer (with `reverse: true` also both directions).
- **cloze** — fill-in-the-blank `{{c1::…}}`.
- **typein** — type the answer, Anki compares (for exact spellings).
- **occlusion** — image with hidden regions (anatomy, diagrams …), self-rendered
  HTML/CSS overlay that works in every Anki version.

On **every** card, optionally a collapsed "Details & source" box
(`explanation` + `source`) — elaborative feedback after the retrieval, without
making the question easier. Full card JSON format: [CLAUDE.md](CLAUDE.md).

```json
{
  "deck": "Biology::Cellular respiration",
  "cards": [
    { "type": "basic",
      "front": "Where in the cell does cellular respiration take place?",
      "back": "In the mitochondria.",
      "source": "script p. 12", "tags": ["bio"] }
  ]
}
```

## The quality pipeline

Every deck runs through this loop before it is called done:

| Step | Tool | What it catches |
|---|---|---|
| Lint | `tools/lint_cards.py` | empty fields, missing deletions, bad occlusion coordinates, duplicate questions, typo'd field names |
| Grounding | `tools/grounding_check.py` | answers not backed by the source text (hallucinations), wrong page citations |
| Coverage | `tools/coverage.py` | near-duplicate cards across files, source pages without any card |
| Preview | `tools/preview.sh` | layout problems, misplaced occlusion masks, night-mode readability |
| Validate | `tools/validate.sh` | import errors, render errors, empty cards — in the real Anki engine |

Shortcut: `./tools/finish.sh decks/<topic>/<name>.cards.json` runs
lint + grounding + build + validate in one go; give it several `cards.json`
plus a target `.apkg` and it bundles a whole topic (and adds the coverage check).

## Updating an already-learned deck (without losing progress)

Learning progress hangs off the Anki note GUID. To restructure cards you have
already been studying:

```bash
# 1. In Anki: File → Export → .apkg (with scheduling)
# 2. Back to editable JSON, GUIDs preserved (stdlib, no Docker):
python3 tools/apkg_to_cards.py export.apkg -o decks/<topic>/<name>_rebuild
# 3. Edit the cards.json, then rebuild — re-import UPDATES instead of duplicating:
./tools/build.sh decks/<topic>/<name>_rebuild/*.cards.json "restructured.apkg"
```

Details (cloze pitfalls, CSS updates): [CLAUDE.md](CLAUDE.md).

## Tools

| Tool | Purpose |
|---|---|
| `tools/prep.sh` | prepare a source in one step: `extract` + figure index + `figextract` |
| `tools/extract.sh` | PDF → Markdown (parallel OCR for scans; incl. figure index via `figindex.py`) |
| `tools/figextract.sh` | crop figures out of the PDF → PNG crops + manifest |
| `tools/detect.sh` | OCR (Tesseract): detect label boxes for image occlusion |
| `tools/lint_cards.py` | fast content/structure check (pure Python, no Docker) |
| `tools/grounding_check.py` | anti-hallucination: are the answers really in the source text? |
| `tools/coverage.py` | near-duplicates + source-page coverage across a whole topic |
| `tools/build.sh` | card JSON → `.apkg` (genanki); also bundles several JSONs into one file |
| `tools/preview.sh` | cards → PNG previews, light + night mode (headless Chromium) |
| `tools/validate.sh` | check the `.apkg` in the real Anki engine (import + render) |
| `tools/finish.sh` | shortcut: lint + grounding (+ coverage) + build + validate in one |
| `tools/apkg_to_cards.py` | `.apkg` → `cards.json` back, GUIDs preserved (edit learned decks without losing progress) |
| `tools/test.sh` | test suite of the logic tools (stdlib `unittest`, no Docker/pip) |

## Folder structure

```
sources/<topic>/           your source files (local, not versioned)
extracted/<topic>/         Markdown extracts + figure crops (local, via prep.sh)
decks/<topic>/             generated .cards.json + .apkg (local; only the example in the repo)
tools/                     preparation, build, checks — see the tools table
tests/                     stdlib test suite of the logic tools
.claude/skills/card-authoring/  evidence-based methodology for writing cards
.githooks/                 pre-commit guard for the public repo
reference/                 local Anki reference clones (not in the repo, see reference/README.md)
CLAUDE.md                  the project guide Claude follows (workflow + card format)
```

## Privacy: your material stays local

Your sources, extracts and generated decks never leave your machine — they are
excluded via `.gitignore`, and a **commit guard** (`.githooks/pre-commit`,
enabled with `git config core.hooksPath .githooks`) additionally blocks commits
that would add personal material (PDFs, `.apkg`, files under `sources/`,
`extracted/`, `decks/`) — even with `git add -f`. The repo itself contains only
the tools, the methodology and one example deck.

## License

[MIT](LICENSE). This project contains **no** Anki source code; it produces
`.apkg` files via [`genanki`](https://github.com/kerrickstaley/genanki) (MIT).
Anki itself is AGPL-3.0 licensed and not included here.
