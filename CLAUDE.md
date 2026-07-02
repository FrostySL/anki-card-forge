# anki-card-forge — project guide (for Claude)

This project turns **source files into Anki flashcards**.
**Claude (me) is the AI** that authors the card content — there is **no**
external LLM call and no API key. Docker only does the dumb
"card JSON → `.apkg`" part via the `genanki` library.

## Card language

**Cards are written in the language of the source material by default** (that is
also what the `card-authoring` skill's retrieval rules assume). If the user asks
for a different language — e.g. *"make the cards in German"*, *"cartes en
français"* — write all card text (fronts, backs, explanations) in that language
and keep domain terms as the source uses them. The user can simply say so in the
chat; nothing needs to be configured. For scanned PDFs, pass the matching OCR
language to the extractor (`./tools/extract.sh … --lang eng+fra`; add missing
Tesseract language packs in `Dockerfile.extract`).

## Folders

| Folder | Purpose |
|---|---|
| `sources/<topic>/` | Sources **per topic** in their own subfolder (e.g. `sources/Biology/`, `sources/Math/`, `sources/SoftwareEngineering/`). PDFs/texts/Markdown. Optionally a **`context.md`** (tolerate other spellings/languages, e.g. `Kontext.md` — when in doubt `ls sources/<topic>/`) with context about the topic (what it is, why it's needed, focus, exam relevance) — read it **before** building cards. |
| `decks/<topic>/` | Mirrors the topics: generated `.cards.json` **and** `.apkg` live in the same topic folder (e.g. `decks/Biology/`). |
| `extracted/<topic>/` | **Machine-readable Markdown extracts** of the sources (via `tools/extract.sh`), mirrored by topic (e.g. `extracted/Biology/cellular_respiration.md`). This is where I read/cite efficiently instead of from the PDF. Per file there is a **`<name>.figures.md`** (figure index: "Fig. N — p. P: title"); page markers show the figure count (`<!-- p. 12 · 2 fig. -->`). **The images themselves are not in the `.md`** — either view the real page of the PDF via the Read tool (`pages="<p>"`) **or** use the crops cut by `figextract.sh` under **`figures/<name>_p<page>_<i>.png`** (manifest `<name>.figures.json`: page, bbox 0..1, kind). Gitignored (derived, reproducible). |
| `tools/` | `build_deck.py` (JSON→apkg), `build.sh` (wrapper), `extract.py`/`extract.sh` (PDF→Markdown, OCR fallback), `figindex.py` (figure index, stdlib), `figextract.py`/`figextract.sh` (crop figures from PDFs → PNG crops), `preview.py`/`preview.sh` (cards→PNG), `detect_labels.py`/`detect.sh` (OCR→exact boxes), `lint_cards.py` (structure check), `grounding_check.py` (check cards against the source text), `coverage.py` (duplicates + coverage across all cards.json), `validate.py`/`validate.sh` (real Anki engine), `apkg_to_cards.py` (`.apkg` → `cards.json` back, **GUIDs preserved** — for changing already-learned decks without losing progress). **Orchestrators:** `prep.sh` (extract+figindex+figextract in one), `finish.sh` (lint+grounding[+coverage]+build+validate; also several cards.json → one .apkg). **Tests:** `test.sh` (`tests/`, stdlib `unittest` of the logic tools — no Docker, no pip; `./tools/test.sh`). |
| `.githooks/` | **Commit guard** (`pre-commit`): the repo is **public** — the hook blocks commits that would add personal material (sources/, extracted/, decks/ content, PDFs/.apkg), even with `git add -f`. Active via `git config core.hooksPath .githooks` (once per clone). If it blocks wrongly: extend the allowlist in the hook, don't blindly `--no-verify`. |
| `reference/` | **Local** Anki reference works (manual + source code), **not in the repo** (third-party license/AGPL) — optionally clone locally, see `reference/README.md`. |
| `reference/anki-manual/` | Official Anki manual as a reference (don't touch). If present locally. |
| `reference/anki/` | Anki source code (shallow clone) as a reference — **read only**, if present locally. Has its own `CLAUDE.md`/`AGENTS.md`; those are Anki's dev notes, not for this project. Native image-occlusion format: `rslib/src/image_occlusion/imageocclusion.rs`. |

## Workflow when the user wants cards

**Convention: one subfolder per topic.** Sources in `sources/<topic>/`, generated
cards/packages in `decks/<topic>/`. The **deck name** starts with the topic so
Anki shows it as the top-level deck: `"<Topic>::<Title>"` (e.g.
`"Biology::Cellular respiration"`).

1. The source file is in `sources/<topic>/` (e.g. `sources/Biology/cellular_respiration.pdf`).
   **If a `sources/<topic>/context.md` exists (any spelling, e.g. `Kontext.md`),
   read it first** — it says what the topic is about and where the focus lies;
   that steers selection and emphasis of the cards.
2. **Prepare the source** (once per new file): PDF → machine-readable Markdown
   **and** crop the figures — in one step:
   ```bash
   ./tools/prep.sh sources/<topic>/<name>.pdf        # or: sources/<topic>/ (whole folder)
   ```
   `prep.sh` bundles `extract.sh` (→ `.md` + `figindex.py` → `.figures.md`) and
   `figextract.sh` (→ `figures/<name>_p*.png` + `<name>.figures.json`). Result:
   `extracted/<topic>/<name>.md` (page markers `<!-- p. N -->`; scanned pages
   detected via OCR and marked `(OCR)`). **Then read from the `.md`** — that is
   more efficient (greppable, cheaper, precisely citable) than loading the PDF as
   images. For `(OCR)` pages, double-check quotes against the original PDF. Pages
   are processed **in parallel** (all CPU cores); individual steps remain available
   via `./tools/extract.sh` (`-j N` to limit, `--lang` for other OCR languages) and
   `./tools/figextract.sh` (tune `--min-area`/`--zoom`).
3. **Read** the `.md` (Read tool); look up sections/pages as needed.
   **Image check:** the `.md` contains **no images**, only captions. Check
   `<name>.figures.md` (or the `· N fig.` markers) for where figures live. If a
   concept is **spatial/visual** (diagram, graph, schematic) or the image carries
   information the text does not → **cheaply view the cropped figure** under
   `extracted/<topic>/figures/<name>_p<page>_*.png` with the Read tool (instead of
   loading the whole PDF page) and decide whether an `occlusion`/image card is
   needed. If a crop is missing (vector not detected) → view the original PDF page
   (`pages="<p>"`). That way no image gets overlooked.
4. **Create** the cards (follow the `card-authoring` skill!) and write them as JSON
   to `decks/<topic>/<name>.cards.json` (format below).
5. **Build** the package:
   ```bash
   ./tools/build.sh decks/<topic>/<name>.cards.json
   ```
   → produces `decks/<topic>/<name>.apkg` (output lands next to the `.cards.json`).
   (Image missing? `docker build -t anki-cards .`)

   **Bundle several files into ONE .apkg** (each file = its own deck; `::` in the
   deck name creates subdecks) — e.g. a whole topic into one file:
   ```bash
   ./tools/build.sh decks/Biology/part1.cards.json decks/Biology/part2.cards.json decks/Biology/Biology-complete.apkg
   ```
6. Tell the user that `decks/<topic>/<name>.apkg` is ready
   → load in Anki via **File → Import** or double-click.

## Changing an existing/learned deck — WITHOUT losing progress

If the user has **already learned** the cards in Anki (or edited them there) and
you are asked to change them anyway: learning progress (scheduling/reviews) hangs
off the note **GUID**. The `.cards.json` in the repo is stale then — do **not**
rebuild from it. Instead:

1. Have the user export in Anki: **File → Export → `.apkg`** (with scheduling),
   the desired deck.
2. **Back to `cards.json`** (GUIDs are carried over):
   ```bash
   python3 tools/apkg_to_cards.py <export>.apkg -o decks/<topic>/<name>_rebuild
   ```
   Detects the modern (zstd) and legacy formats; one `cards.json` per deck. Runs
   on the host (stdlib + zstd), **no Docker**.
3. Edit the `cards.json` (structure/HTML — `card-authoring` skill). **Cloze:** keep
   the same `{{cN::…}}` (number + answer) **byte-identical** → card ord = cN−1
   stays, scheduling keeps fitting. Best to carry the tokens over programmatically
   from the original and only re-set the surroundings (table/list), then verify the
   token set is unchanged. **The extracted fields already contain the "details &
   source" box baked in** → do not additionally set `explanation`/`source`
   (double box).
4. **Rebuild** (GUIDs ⇒ progress kept): `./tools/build.sh decks/<topic>/<name>_rebuild/*.cards.json "<Title> (restructured).apkg"`.
5. **Verify:** build GUIDs == export GUIDs (same set), card count unchanged,
   `validate.sh` (0 errors). For CSS/structure changes also `preview.sh`.
6. The user imports: **"Update notes"**, do **not** reset scheduling.
   Pure **CSS changes** (note type styling) are often not applied by the import →
   alternatively paste the CSS once into *Manage note types → Cards → Styling*
   (no re-import needed, content/progress untouched).

## Feedback loop: check the cards yourself before handing them over

Before reporting an `.apkg` as "done" — especially with **image occlusion**,
where the boxes are placed by eye — check the result:

1. **Lint the content quickly** (pure Python, no Docker needed):
   ```bash
   python3 tools/lint_cards.py decks/<name>.cards.json
   ```
   Reports empty fields, missing deletions, occlusion coordinates outside 0..1,
   duplicate questions, unknown/typo fields, etc.
1b. **Check grounding** (anti-hallucination, pure Python): are the answers really
   in the source text, are cited pages correct?
   ```bash
   python3 tools/grounding_check.py decks/<topic>/<name>.cards.json
   ```
   ERROR = answer barely in the source text (possibly invented); warning = only
   partly covered (e.g. a foreign-language term) → verify against the source.
   Heuristic: warnings mean "have a look", not proof. The source is derived
   automatically from the file name (otherwise `--source <md|folder>`).
1c. **Coverage & duplicates** across a whole topic (when several `cards.json`):
   ```bash
   python3 tools/coverage.py decks/<topic>/
   ```
   Shows near-duplicates across file boundaries (which `lint_cards.py` cannot see)
   and — if cards carry `source: "… p. N"` — which source pages have no card yet.
2. **Render the appearance** (headless Chromium, same HTML as in the .apkg):
   ```bash
   ./tools/preview.sh decks/<name>.cards.json          # default: light AND night mode
   ./tools/preview.sh decks/<name>.cards.json --theme light   # light only (faster)
   ```
   → `decks/preview/<name>/NN-<type>-front.png` + `-back.png` (light) **and**
   `…-front-dark.png` + `…-back-dark.png` (Anki night mode) + `index.html`.
3. **View the PNGs with the Read tool — light AND dark.** Check: do the occlusion
   masks cover the right spots? Does the back show the right label? Layout ok?
   **Readable in night mode** (light text, contrast)? Night mode exposes exactly
   the mistakes that are invisible in light mode (hard-coded colors → dark on
   dark) — hence both by default.
4. Something misplaced → adjust coordinates/text in `decks/<name>.cards.json`,
   then **preview** again (and **build** at the end). Loop until it fits.
5. **Validate in the real Anki engine** (imports + renders every card with Anki's
   backend, no GUI — stronger than the preview emulation):
   ```bash
   ./tools/validate.sh decks/<name>.apkg
   ```
   Exit 0 = import ok, no render errors, no empty cards. On problems it reports
   note type + card.

**Shortcut:** `./tools/finish.sh decks/<topic>/<name>.cards.json` does 1 + 1b +
build + validate in one go (lint is a gate; grounding only a hint). Several
`cards.json` (plus a target `.apkg`, then mandatory) are bundled into ONE file
and additionally run through 1c (`coverage.py`):
`./tools/finish.sh decks/<topic>/*.cards.json decks/<topic>/<topic>-complete.apkg`.
For occlusion cards, additionally run `preview.sh` and look at the PNGs (steps 2–4).

> The preview image (`anki-cards-preview`) is large (Chromium) and is built
> automatically on the first `preview.sh` call. The slim builder image is
> unaffected by that.

## Card JSON format

```json
{
  "deck": "Biology::Chapter 3 - Cellular respiration",
  "cards": [
    {
      "type": "basic",
      "front": "Where in the cell does cellular respiration take place?",
      "back": "In the mitochondria.",
      "tags": ["bio", "respiration"]
    },
    {
      "type": "cloze",
      "text": "Glycolysis runs in the {{c1::cytoplasm}} and yields a net {{c2::2 ATP}}.",
      "extra": "Precursor of cellular respiration, oxygen-independent.",
      "tags": ["bio", "respiration"]
    }
  ]
}
```

- `deck`: deck name. `::` creates subdecks in Anki.
- `type`: `"basic"` (front/back), `"cloze"` (cloze text with `{{c1::...}}`),
  `"typein"` (type the answer, Anki checks) or `"occlusion"` (image with hidden
  regions, see below).
- `extra` (cloze/occlusion) and `tags` are optional.
- **All text fields are rendered as HTML** (no escaping): to structure, use
  `<br>` (line break — a bare `\n` does NOT work), `<ul>/<ol>`, `<table>`.
  Structure improves readability, not the fact count per card (atomicity stays).
- **Images in answers/explanations:** `<img src="extracted/<topic>/figures/….png">`
  in any text field (path **relative to the project root**, like occlusion images).
  The build embeds the file into the `.apkg` and rewrites the src to the file name;
  `preview.sh` inlines it as a data URI; `lint_cards.py` errors if the path is
  missing. http(s)/data URLs stay untouched. For "a picture on the back aids
  understanding" — occlusion remains the format for spatial *retrieval*.
- Optional `guid` per card: stable Anki note GUID. With it, a re-import updates an
  **already learned** note instead of duplicating it → **learning progress is
  preserved**. Use when reworking content from an Anki export (take the GUIDs from
  the export, change the fields). Without `guid`: genanki derives it from the
  fields as usual (changed text ⇒ new GUID ⇒ progress gone).

## Card types in detail

- **basic** — `front`, `back`. With `"reverse": true`, **both** directions are
  generated (forward and reverse, one note → two cards) — good for term ↔
  definition / vocabulary.
- **typein** — `front`, `back`. You type the answer, Anki compares it. Only for
  **exact, short** answers (terms, spellings, abbreviations).
- **cloze** — `text` with `{{c1::deletion}}`, optionally `{{c1::deletion::hint}}`;
  several `c1/c2/...` → several cards.
- **occlusion** — image with hidden regions (see below).

### Details & source (collapsed box) — possible on EVERY card

Two optional fields on **every** card:
- `explanation` — deeper explanation / relationship ("why"). May contain HTML.
- `source` — origin/evidence, e.g. `"Cockburn 2005; script p. 3"`.

Both appear **only on the back** in a box that is **collapsed by default**
("▸ Details & source"). Important (learning psychology): collapsed + after the
retrieval = elaborative feedback without making the question easier. So do
**not** hide the core answer in there — the box supplements, it does not replace
the answer.

```json
{ "type": "basic", "front": "...", "back": "...",
  "explanation": "Briefly, why/context.", "source": "Author year; script p. X" }
```

## Image occlusion ("image with hidden regions")

Own, self-rendered card type (HTML/CSS overlay on top of the image — works in
every Anki version, independent of Anki's internal IO format). Each region
produces **one card**.

```json
{
  "type": "occlusion",
  "image": "sources/heart.png",
  "mode": "hide-one",
  "header": "Label the heart",
  "extra": "<i>From: anatomy script p. 12</i>",
  "regions": [
    {"label": "Aorta",          "x": 0.30, "y": 0.10, "w": 0.12, "h": 0.06},
    {"label": "Left ventricle", "x": 0.55, "y": 0.60, "w": 0.18, "h": 0.10}
  ],
  "tags": ["anatomy", "heart"]
}
```

- `image`: path **relative to the project root** (e.g. `sources/heart.png`). The
  image is embedded into the `.apkg` automatically. **Slide figures** have no
  standalone file → run `figextract.sh` first and point to the crop
  (`extracted/<topic>/figures/<name>_p<page>_<i>.png`).
- `mode`: `"hide-one"` (only the queried region is masked, rest visible) or
  `"hide-all"` (all masked, on reveal only the queried one is shown).
- `regions`: list of regions. **Coordinates as fractions 0..1** (relative to the
  image size): `x`/`y` = top-left corner, `w`/`h` = width/height. `label` = the
  answer shown on the back.

### How I (Claude) place the regions

**Preferred: OCR (pixel-exact).** For images with text labels, first have the
exact boxes detected (for slides, run it on the `figextract` crop):
```bash
./tools/detect.sh extracted/<topic>/figures/<name>_p<page>_<i>.png   # or sources/image.png
#                                                  optional: --lang eng+deu --min-conf 45
```
→ produces `sources/image.labels.json` (detected labels with fractional
coordinates) and `sources/image.labels.png` (image with numbered boxes). View the
annotated PNG with the Read tool, pick the relevant labels and copy their
`x/y/w/h` **1:1** into the occlusion `regions` (merge multi-line labels into one
box if needed).

**Fallback: by eye.** If OCR misses a label (rotated/stylized text, low
contrast): view the image with the Read tool, estimate the box as fractions
(0,0 = top left, 1,1 = bottom right).

**Always afterwards:** render with `./tools/preview.sh`, view the PNG and check
that the masks sit right; otherwise adjust coordinates in the `.cards.json` and
re-render.

## Quality rules for good cards

**Follow the `card-authoring` skill before creating cards**
(`.claude/skills/card-authoring/SKILL.md`) — the evidence-based methodology
including the checklist. Evidence/sources: `.claude/skills/card-authoring/research.md`.

Core rules (short version, details in the skill):
- **Atomic:** one retrievable fact per card. Long answer → split.
- **Real retrieval:** unambiguous, distinct cue; producible answer; no yes/no,
  no whole sentence, no hint leak; ~90 % solvable but effortful.
- **Format by knowledge type:** basic = default; cloze for embedded facts;
  occlusion only spatial/visual; typein only exact spelling; reverse only for
  genuine two-way use.
- **Details/source** in `explanation`/`source` (collapsed box), **not** in the
  retrieval.
- **Grounding:** only what is in the source text (no hallucination); when unsure,
  cite the source instead of guessing. **Tags** per card. Only card-worthy,
  learning-relevant content.
