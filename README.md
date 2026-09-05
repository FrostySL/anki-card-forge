# anki-card-forge

[![CI](https://github.com/FrostySL/anki-card-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/FrostySL/anki-card-forge/actions/workflows/ci.yml)

Turn **lecture scripts, books, slides and notes** into high-quality **Anki
flashcards** — together with an AI assistant of your choice.
The workflow is **AI-provider independent**, works for **any subject**, and
produces cards in **any language you ask for**.

<p align="center">
  <img src="docs/img/example-review.gif" width="760"
       alt="Reviewing a generated deck in Anki: basic cards and image-occlusion cards on a circuit diagram">
</p>

<p align="center"><i>A deck forged from the Wikipedia article on electric current,
in review — including image-occlusion cards on the article's circuit diagram.
This example was recorded with Claude Code.
<a href="#example-one-prompt-start-to-finish">Made with one prompt ↓</a></i></p>

## The idea

You drop a file into `sources/<topic>/` and ask your AI assistant to make cards
from it. The assistant reads the source, writes card JSON following the shared
`card-authoring` methodology, and checks its work. The local tools extract
sources, render previews, and pack the JSON into a ready-to-import `.apkg`
using [`genanki`](https://github.com/kerrickstaley/genanki).

**The repository makes no LLM API calls and requires no provider API key.**
Choose the assistant, model, and any credentials or subscription in your own
AI tool. The interface between the assistant and the build pipeline is ordinary
files and shell commands; switching providers does not change the card format
or Python/Docker tools.

```
sources/<topic>/script.pdf  →  (your assistant authors card JSON)  →  decks/<topic>/script.apkg  →  import into Anki
```

What makes the cards good rather than just numerous:

- **Evidence-based card rules** — atomicity, active retrieval, no hint leaks,
  format by knowledge type (see [the methodology](skills/card-authoring/SKILL.md), with sources).
- **Grounding check** — a heuristic flags answers that may lack support in the
  source text; the assistant reviews those flags against the source.
- **Visual self-review** — cards are rendered as PNGs (light **and** Anki night
  mode) and inspected before delivery; image-occlusion masks are checked visually.
- **Real-engine validation** — every `.apkg` is imported and rendered with Anki's
  actual backend before it is handed to you.

## Example: one prompt, start to finish

The deck in the GIF above was made like this — a real, unedited session
recorded with Claude Code. The screenshots document that example; the shared
workflow below can be used with other assistants.

**1. Get a source.** Anything that fits in a PDF or text file. Here: the
Wikipedia article [Electric current](https://en.wikipedia.org/wiki/Electric_current)
as PDF, plus the article's circuit diagram in high resolution (a CC0 file from
Wikimedia Commons) for the image-occlusion cards.

![The Electric current Wikipedia article, opened as PDF](docs/img/example-1-source-pdf.png)

**2. Drop it into `sources/<topic>/`:**

![The PDF placed at sources/Physics/electric_current.pdf](docs/img/example-2-sources-folder.png)

**3. Ask.** In this recording, one sentence in the Claude Code chat:

![Prompt: Make 10 English Anki cards from sources/Physics/electric_current.pdf with image occlusion. Import the deck into Anki via AnkiConnect.](docs/img/example-3-prompt.png)

**4. Claude does the rest** — extracts the PDF, authors the cards following the
methodology, places the occlusion masks on the circuit diagram, runs the whole
quality pipeline on its own work, and (since AnkiConnect was installed) imports
the finished deck straight into Anki. Expect this to take a while — several
minutes even for a small deck; the time goes into the self-checks, not just
the writing:

![Claude's final report: 10 cards built, checked and imported into Anki](docs/img/example-4-result.png)

**5. Study.** That is the GIF at the top: 7 basic cards plus 3 image-occlusion
cards masking *v*, *i* and *R* on the circuit — fresh out of the forge.

## Requirements

- **[Anki](https://apps.ankiweb.net/)** (the flashcard app you study in — desktop,
  or AnkiMobile/AnkiDroid) to import and review the generated decks
- **An AI assistant** that can read and write project files and run shell
  commands. Image viewing is needed for visual source material, image-occlusion
  cards, and visual preview checks; if unavailable, inspect those images
  yourself and do not treat the visual review as complete.
- **Windows 11 x64:** a writable project folder and internet for the first
  `forge.cmd setup`. Python, OCR, Chromium and formula assets are installed
  locally. Git, Docker, WSL and administrator rights are not required.
- **Linux / WSL2:** Git, Bash, Python 3.10+ and Docker with a running daemon.
- *Optional:* the **AnkiConnect** add-on (code `2055492159`) to push decks into
  Anki without the manual import dance — see [ANKICONNECT.md](ANKICONNECT.md).
  Everything works without it; it just saves clicks.

On Windows, dependencies live in `.forge/` and `.venv/`. After setup, processing
local sources and rendering formulas work offline. Native Linux, macOS and
Windows ARM64 setup are outside the initial supported scope.
On Linux, the main build, extraction, and rendering dependencies live inside Docker.
Host-side lint, grounding, and coverage checks use Python's standard library.
Reading modern Anki exports/backups additionally needs Python `zstandard` or
the `zstd` CLI; see [AnkiConnect setup](ANKICONNECT.md#setup-once).
A chat assistant without file/shell access can still help author JSON, but you
must save the files and run the tools yourself.

### Docker on Linux and WSL2

You can install **Docker Engine directly in Linux**, including Ubuntu inside
WSL2; Docker Desktop is optional. Follow the official
[Docker Engine installation for Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
and [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)
so your normal user can run Docker. Run this project's Bash, Python, and Docker
build commands inside that Linux environment, from the project directory.
Before running `setup.sh`, this must succeed without `sudo`:

```bash
docker info
```

With [systemd enabled in WSL2](https://learn.microsoft.com/en-us/windows/wsl/systemd)
and the Docker service enabled, Docker starts when the Ubuntu distribution
starts. This does not launch Ubuntu at Windows startup or keep WSL running
indefinitely. If Anki runs on Windows while the project runs in WSL, use the
[Windows Anki connection instructions](ANKICONNECT.md#wsl2-project-with-anki-on-windows).

## Quick start

### Windows 11 x64

Clone the repository, or download its ZIP from GitHub and extract it. Open the
folder in your AI assistant and ask it to run setup, or use PowerShell:

```powershell
.\forge.cmd setup
.\forge.cmd doctor
.\forge.cmd prep sources\Biology
.\forge.cmd preview decks\Biology\respiration.cards.json
.\forge.cmd finish decks\Biology\respiration.cards.json
# Optional, with Anki and AnkiConnect open:
.\forge.cmd anki ping
```

Setup downloads pinned components, checks their integrity, and runs synthetic
functional checks. Repeating it reuses installed components; `setup --offline`
uses only local files and caches. `doctor` checks without downloading or
installing. Add OCR languages with `setup --lang fra`; English and German are
included by default. Keep the project in a reasonably short writable path.

Use quoted paths when they contain spaces. Wildcards such as
`decks\Biology\*.cards.json` are expanded by the launcher. Media paths *inside
card JSON* stay relative to the project and use `/` on both platforms.
Keep `.forge/` and `.venv/` local; recreate them with setup after moving to
another machine. See [Windows setup details](docs/cross-platform-setup.md)
and [acceptance tests](tests/integration/README.md).

### Linux / WSL2

```bash
git clone https://github.com/FrostySL/anki-card-forge
cd anki-card-forge
./tools/setup.sh          # checks Docker/Python, enables the commit guard,
                          # builds the image, proves it on the example deck
```

`setup.sh` is the one-command health check ("doctor"): it does the two
easy-to-forget one-offs (commit guard, builder image) and builds the bundled
example deck end-to-end, so the first five minutes finish with a visible
success. Prefer to do it by hand? `docker build -t anki-cards .` and
`git config core.hooksPath .githooks` are the only required steps.

1. Put a source into `sources/<topic>/` (PDF, text, Markdown …) — one subfolder
   per topic, e.g. `sources/Biology/`.
2. Open the project in your AI assistant and give it the portable start prompt
   below. This explicitly loads the guide even if the assistant does not
   automatically read `AGENTS.md`.
3. The assistant produces `decks/Biology/respiration.apkg` after running the
   quality checks.
4. **Import into Anki:** double-click the `.apkg`, or in Anki open **File → Import**
   and pick it. The cards land in a deck named after the topic (e.g. `Biology`),
   ready to study — scheduling, subdecks and styling are already baked in. On phones,
   sync the desktop collection to AnkiWeb and the deck appears in AnkiMobile/AnkiDroid.
   (Tired of the import dialog? The optional [AnkiConnect route](ANKICONNECT.md)
   imports and syncs for you.)

### What to tell your AI assistant

Copy this prompt into a new conversation with your assistant. Replace the
example source path with your own file and add any wishes about language,
scope, or card count. This explicitly tells the assistant which instructions
to read, so the workflow does not depend on automatic instruction discovery:

```text
Read AGENTS.md, skills/card-authoring/SKILL.md, and workflows/forge.md first.
Follow those instructions to create Anki cards from
sources/Biology/respiration.pdf, run the quality checks, and produce the
finished .apkg.
```

On Linux, the larger images (preview/OCR, source extraction) are built
automatically the first time the corresponding `tools/*.sh` runs.

The remaining examples use the Linux commands. On Windows, use `forge.cmd`
with the same arguments: `prep`, `finish`, `extract`, `figextract`, `figindex`,
`detect`, `lint`, `grounding`, `coverage`, `build`, `preview`, `validate`,
`decode`, `diff`, `anki` and `test`. For example, `python3 tools/deck_diff.py`
becomes `.\forge.cmd diff`, and `./tools/build.sh` becomes `.\forge.cmd build`.

For HTML field arguments with embedded quotes or `&`, invoke `& .\forge.ps1`
directly in PowerShell instead of the CMD entry point. It preserves literal
arguments and keeps managed environment settings in a child process; see the
[PowerShell example and execution-policy notes](docs/cross-platform-setup.md).

### Shared guide, skill, and workflows

[AGENTS.md](AGENTS.md) is the provider-neutral project guide and card JSON
reference. [skills/card-authoring/SKILL.md](skills/card-authoring/SKILL.md)
contains the authoring rules, with their evidence in
[research.md](skills/card-authoring/research.md). These are ordinary Markdown
files: an assistant can read and follow them without a skill registry or
provider-specific installation.

Use [workflows/forge.md](workflows/forge.md) for new cards and
[workflows/rework.md](workflows/rework.md) for existing decks. For example:

> Read `AGENTS.md`, `skills/card-authoring/SKILL.md`, and
> `workflows/rework.md`. Rework my exported deck `sources/Biology/export.apkg`
> while preserving its note GUIDs and learning progress.

**Optional Claude Code integration:** The adapters in `.claude/` point to
the shared instructions. Claude Code users can keep using
`/forge sources/<topic>/<file>` and `/rework`; the optional
`.claude/settings.json` hook adds automatic lint feedback after card edits.
Other assistants run the same checks through the documented shell commands.

> **Re-importing a newer version of a deck?** If you have already studied it, keep
> your progress by giving cards stable GUIDs — see
> [Updating an already-learned deck](#updating-an-already-learned-deck-without-losing-progress).
> A plain rebuild otherwise creates fresh cards and resets scheduling.

### Any topic, any language

The project is deliberately generic — biology, law, math, software engineering,
history: if it fits in a PDF or text file, it can become cards. Cards default to
the language of your source material. Want something else? Just tell your assistant:

> "Make the cards from sources/Histoire/revolution.pdf — cards in French, please."

For scanned PDFs in other languages, add the Tesseract language pack to
`Dockerfile.extract` and pass `--lang` (e.g. `./tools/extract.sh … --lang eng+fra`).

Optionally place a `context.md` next to your sources (what the material is for,
where the focus lies, what the exam covers) — the assistant reads it first and weights
the cards accordingly.

## Saving tokens: run the extraction toolchain yourself

Your assistant normally runs the whole pipeline for you. The **source
preparation** step (PDF → Markdown + figure crops) is pure tooling — no AI
involved — and you can run it yourself before starting the chat to avoid
spending tokens on tool orchestration:

```bash
./tools/prep.sh sources/<topic>/            # whole folder, or a single PDF
```

This produces, per source file:

- `extracted/<topic>/<name>.md` — machine-readable Markdown with page markers
  (`<!-- p. 12 -->`), scanned pages OCR'd and marked `(OCR)`,
- `extracted/<topic>/<name>.figures.md` — an index of the figures per page,
- `extracted/<topic>/figures/<name>_p<page>_<i>.png` — cropped figures (for
  image-occlusion cards and cheap visual checks).

Then tell your assistant *"the sources are already prepared — make cards from
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
making the question easier. Full card JSON format: [AGENTS.md](AGENTS.md).

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

**Entirely optional** — without it you import the `.apkg` by double-click /
*File → Import*, and nothing else in this repo changes. With the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed
(code `2055492159`, then restart Anki), finished decks go straight into your
collection over **local HTTP** by default, without passing AnkiWeb
credentials to the tool. Explicit AnkiWeb sync sends collection data to
AnkiWeb:

```bash
python3 tools/anki_connect.py ping                    # is Anki + add-on reachable?
python3 tools/anki_connect.py decks                   # list all deck names
python3 tools/anki_connect.py push decks/<topic>/<name>.apkg   # import a built deck
python3 tools/anki_connect.py push <name>.apkg --dry-run       # what WOULD change?
python3 tools/anki_connect.py export "<Deck>" out.apkg # export WITH scheduling
python3 tools/anki_connect.py sync                    # trigger AnkiWeb sync
python3 tools/anki_connect.py mirror                  # local backup of all decks
python3 tools/anki_connect.py update-note <nid> --field "Back=..."   # edit one note in place
python3 tools/anki_connect.py restore [--list]        # push a backup snapshot back
```

`./tools/finish.sh … --push [--prune] [--sync]` chains it into the build:
validate, import, optionally remove cards you cut from the deck, optionally
sync to AnkiWeb/phone.

Safety comes built in: destructive API actions are locked out entirely, every
push backs up the affected decks first (`decks/_anki-backups/`, restore =
push the backup), removing cards only happens via the explicit `--prune` with
several guards, and sync never runs implicitly.

**Full documentation — setup, all commands, backups & restore, safeguards,
workflows, troubleshooting: [ANKICONNECT.md](ANKICONNECT.md).**

## Updating an already-learned deck (without losing progress)

Learning progress hangs off the Anki note GUID. To restructure cards you have
already been studying:

```bash
# 1. In Anki: File → Export → .apkg (with scheduling) — or, with AnkiConnect:
python3 tools/anki_connect.py export "<Deck>" export.apkg
# 2. Back to editable JSON, GUIDs preserved (modern exports need zstd):
python3 tools/apkg_to_cards.py export.apkg -o decks/<topic>/<name>_rebuild
# 3. Edit the cards.json, then rebuild — re-import UPDATES instead of duplicating:
./tools/build.sh decks/<topic>/<name>_rebuild/*.cards.json "restructured.apkg"
# 4. Verify before importing: exactly the intended changes, no cloze breakage?
python3 tools/deck_diff.py export.apkg restructured.apkg --strict
```

The decoder keeps the third `More` field of type-in and reversed basic notes
in `more`, including existing details/source HTML. Keep it separate from `back`.
It refuses to write incomplete JSON when occlusion notes or unsupported field/
deck layouts would be lost. Edit those notes, and foreign note types, in Anki or
with `anki update-note`; rebuilding them as another type cannot update them safely.

The package diff checks every raw note and field, including occlusion and
foreign types. Strict mode rejects cloze/card-ordinal or note-type/field-layout
changes and ambiguous comparisons. Review reported additions and removals too;
they do not by themselves fail strict mode.

Details (cloze pitfalls, CSS updates): [AGENTS.md](AGENTS.md).

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
| `tools/apkg_to_cards.py` | `.apkg` → `cards.json` back, GUIDs **and media** preserved (edit learned decks without losing progress) |
| `tools/deck_diff.py` | diff two deck versions by note GUID: added/removed/changed notes, cloze-safety warnings — verify a rework **before** pushing it |
| `tools/anki_connect.py` | optional: drive a running Anki via the AnkiConnect add-on — `push` (`--dry-run`)/`export`/`sync`/`mirror`/`decks`/`restore`, local HTTP, no credentials ([docs](ANKICONNECT.md)) |
| `tools/setup.sh` | one-command setup + health check for a fresh clone (Docker/Python, commit guard, builder image, example-deck smoke test) |
| `tools/test.sh` | test suite of the logic tools (stdlib `unittest`, no Docker/pip) |

## Folder structure

```
sources/<topic>/           your source files (local, not versioned)
extracted/<topic>/         Markdown extracts + figure crops (local, via prep.sh)
decks/<topic>/             generated .cards.json + .apkg (local; only the example in the repo)
tools/                     preparation, build, checks — see the tools table
tests/                     stdlib test suite of the logic tools
skills/card-authoring/     shared card methodology + research (ordinary Markdown)
workflows/                 provider-neutral forge + rework instructions
.claude/                   optional Claude Code adapters: skill, slash commands,
                           cards.json lint hook (settings.json — delete to opt out)
.githooks/                 pre-commit guard for the public repo
docs/img/                  images/GIF for this README (recordings stay local)
reference/                 local Anki reference clones (not in the repo, see reference/README.md)
AGENTS.md                  shared project guide (workflow + card format)
ANKICONNECT.md             optional AnkiConnect integration (push/export/sync/mirror)
```

## Privacy: local files and your AI service

Sources, extracts, and generated decks are stored locally and excluded from
Git via `.gitignore`. The **commit guard** (`.githooks/pre-commit`, enabled
with `git config core.hooksPath .githooks`) additionally blocks commits that
would add personal material (PDFs, `.apkg`, files under `sources/`,
`extracted/`, `decks/`) — even with `git add -f`. Its shared path allowlist lives
in `tools/check_repo_files.py`; CI checks the same policy against all tracked
files. The repository contains the tools, methodology, and one example deck.

These Git protections prevent accidental commits; they do not control what
your AI assistant sends to its model provider. Source text, images, and cards
that a cloud assistant reads may be sent to that service, depending on its
settings and data policy. Choose an appropriate service for your material.
A local model is also an option when your agent tooling supports it and the
required file, shell, and image capabilities.

AnkiConnect talks to the local Anki app by default. An explicitly requested
AnkiWeb sync transfers collection data to AnkiWeb.

## Contributing

For changes to the tools or documentation, see [CONTRIBUTING.md](CONTRIBUTING.md)
for the branch → pull request → checked squash merge workflow and relevant tests.

## License

[MIT](LICENSE). This project contains **no** Anki source code; it produces
`.apkg` files via [`genanki`](https://github.com/kerrickstaley/genanki) (MIT).
Anki itself is AGPL-3.0 licensed and not included here.
