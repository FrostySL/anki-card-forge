# anki-card-forge

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

- **[Anki](https://apps.ankiweb.net/)** (the flashcard app you study in — desktop,
  or AnkiMobile/AnkiDroid) to import and review the generated decks
- **[Claude Code](https://claude.com/claude-code)** (the AI that writes the cards)
- **Docker** (packs cards into `.apkg`, renders previews, runs OCR)
- *Optional:* the **AnkiConnect** add-on (code `2055492159`) to push decks into
  Anki without the manual import dance — see
  [Optional: drive Anki directly](#optional-drive-anki-directly-ankiconnect)

Nothing else — all Python dependencies live inside the Docker images.

## Quick start

```bash
git clone https://github.com/FrostySL/anki-card-forge
cd anki-card-forge
docker build -t anki-cards .             # slim builder image (one-off)
git config core.hooksPath .githooks      # commit guard (see below, one-off)
```

1. Put a source into `sources/<topic>/` (PDF, text, Markdown …) — one subfolder
   per topic, e.g. `sources/Biology/`.
2. Ask Claude in the chat: **"Create Anki cards from sources/Biology/respiration.pdf."**
3. Claude produces `decks/Biology/respiration.apkg`.
4. **Import into Anki:** double-click the `.apkg`, or in Anki open **File → Import**
   and pick it. The cards land in a deck named after the topic (e.g. `Biology`),
   ready to study — scheduling, subdecks and styling are already baked in. On phones,
   sync the desktop collection to AnkiWeb and the deck appears in AnkiMobile/AnkiDroid.

The larger images (preview/OCR, source extraction) are built automatically the
first time the corresponding `tools/*.sh` runs.

> **Re-importing a newer version of a deck?** If you have already studied it, keep
> your progress by giving cards stable GUIDs — see
> [Updating an already-learned deck](#updating-an-already-learned-deck-without-losing-progress).
> A plain rebuild otherwise creates fresh cards and resets scheduling.

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

## Optional: drive Anki directly (AnkiConnect)

With the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on,
finished decks go straight into your collection — no *File → Import* dance.
Everything runs over local HTTP (`127.0.0.1:8765`): **no AnkiWeb credentials,
nothing leaves your machine**, and the core pipeline works fine without it.

One-off setup: in Anki, **Tools → Add-ons → Get Add-ons…**, enter code
`2055492159`, restart Anki. Then, with Anki running:

```bash
python3 tools/anki_connect.py ping                    # is Anki + add-on reachable?
python3 tools/anki_connect.py push decks/<topic>/<name>.apkg   # import a built deck
python3 tools/anki_connect.py export "<Deck>" out.apkg # export WITH scheduling
python3 tools/anki_connect.py sync                    # trigger AnkiWeb sync
python3 tools/anki_connect.py mirror                  # local backup of all decks
```

- `./tools/finish.sh … --push` imports the freshly built `.apkg` right after
  validation; add `--sync` to also push it to AnkiWeb (and your phone).
- `export` pulls a deck **with scheduling** — the automated entry into the
  [progress-preserving rebuild](#updating-an-already-learned-deck-without-losing-progress)
  below.
- `mirror` snapshots every deck into `decks/_anki-mirror/` as `.apkg` **plus**
  decoded, greppable `cards.json` (GUIDs included). The mirror is gitignored —
  it stays a local backup and never lands in the repo.

Built-in safeguards:

- **Nothing destructive is callable.** The tool only allows a small safe list of
  AnkiConnect actions (import, export, sync, deck listing); deleting decks or
  notes through it is locked out by design. A plain import can never delete
  anything either — Anki merges, so even pushing an empty deck of the same name
  leaves your cards untouched.
- **Automatic backup before every push.** An import overwrites the fields of
  same-GUID notes, so `push` first exports every affected existing deck (with
  scheduling) to `decks/_anki-backups/<timestamp>/` (gitignored, newest 10
  kept). Something went wrong? Push the backup `.apkg` to restore the previous
  content. Skip with `--no-backup`.
- **Removing cards is explicit and reversible.** Because imports only merge,
  cards you cut from a reworked deck would linger in Anki forever. The one
  sanctioned way to remove them is `push --prune`: it deletes exactly the notes
  whose GUIDs vanished from the package, lists each one, requires the fresh
  backup as its diff baseline and restore path, and refuses outright if a deck
  shares **no** GUID with the package (the telltale sign of a rebuild that lost
  its GUIDs — pruning then would wipe the deck's learning progress).
- **Sync never happens implicitly** — only via an explicit `sync` /
  `finish.sh --sync`, so nothing broken propagates to AnkiWeb or your phone
  before you have seen the import result.

## Updating an already-learned deck (without losing progress)

Learning progress hangs off the Anki note GUID. To restructure cards you have
already been studying:

```bash
# 1. In Anki: File → Export → .apkg (with scheduling) — or, with AnkiConnect:
python3 tools/anki_connect.py export "<Deck>" export.apkg
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
| `tools/finish.sh` | shortcut: lint + grounding (+ coverage) + build + validate in one; `--push [--sync]` sends the result into Anki |
| `tools/apkg_to_cards.py` | `.apkg` → `cards.json` back, GUIDs preserved (edit learned decks without losing progress) |
| `tools/anki_connect.py` | optional: drive a running Anki via the AnkiConnect add-on — `push`/`export`/`sync`/`mirror`, local HTTP, no credentials |
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
