---
name: card-authoring
description: Apply when creating Anki flashcards from learning material. Evidence-based rules for HOW to phrase good cards and pick the right format (atomicity, active retrieval, basic/cloze/occlusion/type-in/reverse, details+source). Always follow before generating cards.
---

# Card authoring — evidence-based methodology

Apply **before** you generate cards (`*.cards.json`). Full evidence/sources:
[research.md](research.md). Card types, fields and the build/check workflow:
see `CLAUDE.md` in the project root.

## Core principle (the most important thing)

**Every card forces active retrieval of ONE atomic piece of information** — an
unambiguous cue, an unambiguous, self-producible answer. This is the best
documented finding (retrieval/testing effect). **The phrasing matters more than
the card type.**

## Mandatory rules

1. **Atomic:** one card = one retrieval target. Answer > 1 independent fact or
   > ~1 short sentence → **split**.
2. **Real retrieval:** no yes/no questions, no recognition, no memorizing whole
   sentences. The answer must be *produced*.
3. **Unambiguous, distinct cue** (no "What is important about X?") that does
   **not give away** the answer (no hint leak).
4. **Solvable (~90 %) but effortful:** the answer must not be trivially derivable.
5. **Language = language of the source** (unless the user requests another —
   see CLAUDE.md "Card language"). Only card what is exam-/learning-relevant.

## Format choice (by knowledge type)

| Format (`type`) | When |
|---|---|
| **basic** | Default: concepts, definitions, "why/how", understanding, inference. |
| **cloze** | Embedded single facts; the context sentence carries the meaning. Delete only the **keyword**, not half sentences; several deletions → c1, c2 … individually. |
| **occlusion** | Only **spatial/visual** mapping (anatomy, geography, diagrams, architecture). Mask only exam-relevant labels. For "why/how" → text card. |
| **typein** | Only where **exact spelling/syntax** counts (commands, keywords, terms, vocabulary). Not for concepts (typos/synonyms = frustration). |
| **basic + `reverse:true`** | Only for genuine **two-way use** (vocabulary L1↔L2, term↔definition). Omit for confusable pairs (interference). |

## Lists / orders / processes

- Prefer decomposing into **atomic single facts** (+ optionally one overview card).
- Enumerations → **relational cloze** instead of "name all …".
- Orders/algorithms → **sequential cues** (step n cues step n+1).

## Formatting & structure (HTML in the fields)

All text fields (`front`, `back`, `text`, `extra`, `explanation`) are rendered
**as HTML** (genanki does not escape). Use that so cards are legibly structured
instead of a wall of prose.

- **`\n` in JSON is NOT a line break** — in HTML it is just a space. For visible
  breaks use `<br>`, for enumerations `<ul><li>…</li></ul>`/`<ol>`, for mappings/
  comparisons `<table>` (borders/padding are styled in the CSS).
- **Structure ≠ more content.** HTML makes *one* card more readable, but does not
  override atomicity: no "prettier packaging" of a six-fact card. A list with 5
  items that are all tested stays 5 cards.
- **Cloze table** for parallel mappings (phase→result, term→definition,
  layer→protocol): two-column `<table>`, per row **one** deletion in the answer
  column. Yields one card per row with the whole table as context — structured
  *and* atomic. Instead of everything in one sentence (`A → {{c1::…}}; B →
  {{c2::…}}; …`):

  ```json
  { "type": "cloze",
    "text": "<table><tr><th>Phase</th><th>Deliverable</th></tr><tr><td>Analysis</td><td>{{c1::situation study/project plan}}</td></tr><tr><td>Definition</td><td>{{c2::product definition}}</td></tr></table>" }
  ```
- Always render with `tools/preview.sh` and look at the PNGs — HTML typos are
  visually obvious at once.

### Ready-made CSS classes & math (in `_CSS`, effective in preview + .apkg)

Use sparingly and deliberately — **distinctiveness helps, decoration hurts**
(seductive details). Color-coded boxes belong on the **back/`explanation`**,
never on the question (hint leak).

| Device | For | Example |
|---|---|---|
| `<table>` / cloze table | Mappings, comparisons, parallel facts | see above |
| `<pre><code>` / `<code>` | Source code / inline identifiers (monospace) | `<pre><code>git rebase -i</code></pre>` |
| `<kbd>` | Keyboard shortcuts | `<kbd>Ctrl</kbd>+<kbd>C</kbd>` |
| `\( … \)` / `\[ … \]` | Formulas (MathJax, native in Anki) | `\( a^2 + b^2 = c^2 \)` |
| `<div class="note">` | Key statement / take-away | ★ |
| `<div class="pitfall">` | Typical trap / common mistake | ⚠ |
| `<div class="example">` | Worked example (documented as effective) | ❯ |
| `<div class="mnemonic">` | Mnemonic / memory aid | 🧠 |
| `<span class="contrast">…</span>` | On sister cards, mark the **distinguishing** feature (interference) | — |
| `<details class="hint"><summary>Hint</summary>…</details>` | Graded cue, ok on the **front** too (collapsed → retrieval stays); sparingly | — |
| `<div class="flow"><span class="step">A</span><span class="arrow">→</span>…</div>` | Process/sequence chain (dual coding of the order) | — |

(The German class names `merke`/`achtung`/`beispiel`/`eselsbruecke`/`kontrast`
still work as legacy aliases — use the English ones.)

Night mode: `.card` deliberately sets **no** fixed `color`/`background` → Anki
colors text+background per theme itself (tables/borders use translucent grays).
So **no hard-coded colors** in the fields, or you get dark text on a dark
background. (Do not rely on `.nightMode .card` — it does not apply in every Anki
version.) Math renders in the preview only online (CDN); the finished `.apkg`
always renders it (Anki ships MathJax).

## Avoiding interference

- Separate overly similar cards ("sister cards") with **distinct, contrasting**
  cues (name the source of confusion explicitly).
- Keep prompts **consistent** (don't ask one way now, another way later).

## Details & source (collapsed box)  →  fields `explanation` + `source`

Deeper explanation ("why"/context) and origin belong on the **back**, but
**separate from the retrieval**: in our `<details>` box that is **collapsed by
default**. In the `*.cards.json` via the optional fields:

```json
{ "type": "basic", "front": "...", "back": "<short core answer>",
  "explanation": "Why/context.", "source": "Author year; script p. X" }
```

Rules: the explanation goes **neither** on the front **nor** into the tested
answer (otherwise retrieval difficulty / atomicity suffers). When unsure about a
fact → cite the source instead of guessing.

## Anti-patterns (short)

- Multi-fact card → split.
- Yes/no or guessable question → rephrase as "which property …?".
- Whole sentence as cloze / too many deletions → separate atomic cards.
- Hint leak (cue gives away the answer) → rephrase.
- Decorative image without retrieval relevance → drop it or show a real mapping.
- Orphan factoid without context → put the context into the cue.

## When generating with AI (that is: you)

- **Grounding:** card content **only** from the provided source text, not from
  model knowledge → no hallucinations. Source into `source`. Verifiable with
  `tools/grounding_check.py` (answer against source text; ERROR = possibly invented).
- **Image check:** the `.md` contains **no images**, only captions. Before
  building, go through the figure index `extracted/<topic>/<name>.figures.md`
  (or the `· N fig.` markers). For **spatial/visual** concepts or when the image
  carries information the text does not → view the crop
  `extracted/<topic>/figures/<name>_p<page>_*.png` with the Read tool (cheaper
  than the whole PDF page; if missing, `pages="<p>"` on the PDF) and build an
  `occlusion`/image card if warranted — the crops double as the occlusion `image`.
- **Avoid verbosity:** LLM-typical long "paragraph cards" violate atomicity.
- **Avoid duplicates/redundancy** (not the same fact twice) — across a whole
  topic with `tools/coverage.py decks/<topic>/` (near-duplicates + coverage gaps).
- **Self-check** every card against the checklist; rephrase the failures.
- Then: `tools/lint_cards.py` (structure), `tools/grounding_check.py` (grounding),
  `tools/preview.sh` (renders **light AND night mode** → view the PNGs, check
  dark-mode readability), `tools/validate.sh` (real Anki engine) — or
  `tools/finish.sh` (lint+grounding+build+validate in one).

## Checklist — per card, before the build

- [ ] Exactly **one** atomic piece of information.
- [ ] Forces **active retrieval** (no yes/no, no whole sentence).
- [ ] Cue **unambiguous & distinct**, no hint leak.
- [ ] Answer as **short as possible**, exactly one correct form, producible.
- [ ] **Format** fits the knowledge type (table above).
- [ ] Cloze: only the keyword deleted; reverse only for genuine two-way use.
- [ ] Details/source (if useful) in `explanation`/`source` — not in the retrieval.
- [ ] **Grounded in the source**, no duplicate.
- [ ] **Image check** done: relevant figure (`.figures.md`) viewed if visual.
