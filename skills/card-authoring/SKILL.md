---
name: card-authoring
description: Apply when creating Anki flashcards from learning material. Evidence-based rules for HOW to phrase good cards and pick the right format (atomicity, active retrieval, basic/cloze/occlusion/type-in/reverse, details+source). Always follow before generating cards.
---

# Card authoring — evidence-based methodology

Apply **before** you generate cards (`*.cards.json`). Full evidence/sources:
[research.md](research.md). Card types, fields and the build/check workflow:
see `AGENTS.md` in the project root.

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
   see AGENTS.md "Card language"). Only card what is exam-/learning-relevant.
6. **Self-contained:** every question must make sense on its own in random
   review order. Name the subject and any necessary conditions; use plain,
   natural wording. Follow the standalone-question rules below.

## Standalone questions and source references

Write questions, answers and explanations about the subject directly. Avoid
source-relative framing such as "according to the book", "in this chapter",
"in the book's model", "described here" or "as shown in Figure 2.3". If scope
matters, name the actual model, conditions or assumptions instead of pointing
to the source. Keep book/chapter names and page/figure references in `source`,
which appears in the collapsed box on the back.

Every referent needed to interpret the question must be on the front. "This
diagram" is meaningful only if the diagram is included there; a figure number
or an image shown only on the back cannot supply missing context. Do not rely
on the source document, deck title, neighbouring cards or hidden explanations.

- Instead of "What centre-to-edge thickness profile characterizes the simple
  converging lens described here?", ask "How does the thickness of a simple
  glass converging lens in air compare at its centre and edges?"
- Instead of "What does the chapter say determines image size?", name the
  relevant condition: "For a subject at a fixed distance, how does increasing
  a lens's focal length affect image size?"

## Separate front-only review — before building

After drafting, review **every new or edited question in a separate pass**.
Include both directions of reversed cards and each generated cloze or
occlusion variant. For reworks, stay within the requested changes and preserve
GUIDs, cloze tokens and card ordinals as required by the rework workflow.

1. Read only the front and any image displayed there, without consulting the
   answer, explanation or source. State what single fact the question asks
   for and check that every referent and necessary condition is explicit.
2. Rewrite questions that depend on absent context, quote the source's framing,
   use unnecessarily awkward wording or reveal their answer. Recheck the
   rewritten fronts in isolation.
3. Only then compare each question with its answer and source to verify that
   the answer fits the cue and remains grounded.

Complete this pass before the automated quality pipeline. Lint, grounding,
coverage, previews and Anki validation do not establish that a question is
self-contained or well written; passing them does not replace this review.

## Format choice (by knowledge type)

| Format (`type`) | When |
|---|---|
| **basic** | Default: concepts, definitions, "why/how", understanding, inference. |
| **cloze** | Embedded single facts; the context sentence carries the meaning. Delete only the **keyword**, not half sentences; several deletions → c1, c2 … individually. |
| **occlusion** | Only **spatial/visual** mapping (anatomy, geography, diagrams, architecture). Mask only exam-relevant labels. For "why/how" → text card. |
| **typein** | Only where **exact spelling/syntax** counts (commands, keywords, terms, vocabulary). Not for concepts (typos/synonyms = frustration). |
| **basic + `reverse:true`** | Only for genuine **two-way use** (vocabulary L1↔L2, term↔definition). Omit for confusable pairs (interference). |

## Explanatory source graphics — project preference

The learner prefers visual explanations. For every card, consider the source's
diagrams, graphs, tables and photographs; include a useful graphic on each
relevant card when it clarifies the mechanism, relationship or example. A
graphic can be valuable even when the text already explains the concept.
Do not force an image onto a card if the source has no helpful visualization.

- Prefer a focused crop of the original source figure. Preserve the relevant
  labels, arrows, scales and legend. If automatic extraction misses a vector
  diagram or clips a figure, render and crop the original PDF page.
- Put explanatory images **after retrieval, visible when the answer is
  revealed**: in `back` for ordinary basic cards and `extra` for cloze cards.
  Keep cloze images out of `text` and preserve the deletion tokens. For reversed
  or type-in notes, use back-only feedback (`more`) without changing a reverse
  question or typed answer. Supplementary images may go in `explanation`, but
  do not hide the main visual explanation in collapsed Details by default.
- Put an image on the front only when interpreting it is part of the question;
  explanatory feedback must not reveal the answer before retrieval. Existing
  image-occlusion cards remain for spatial retrieval.
- Reuse a figure on multiple cards when it helps each retrieval target, rather
  than adding unrelated or decorative pictures. Keep citations in `source`.
- Embed local media in the package and inspect every changed image layout in
  light and dark previews for complete crops, readable labels and contrast.

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
version.) Previews render math with local MathJax, including dynamically loaded
extensions; rendering failures stop the preview. `preview --offline` additionally
rejects web media. Anki uses its bundled MathJax for the finished `.apkg`.

## Avoiding interference

- Separate overly similar cards ("sister cards") with **distinct, contrasting**
  cues (name the source of confusion explicitly).
- Keep prompts **consistent** (don't ask one way now, another way later).

## Details & source (collapsed box)  →  fields `explanation` + `source`

Supplementary context and provenance belong in the `<details>` box on the
**back**, **collapsed by default**. The essential answer, including the causal
explanation tested by a "why/how" question, stays in the main answer. Follow
the visual-feedback placement rules above for explanatory graphics.
In the `*.cards.json` via the optional fields:

```json
{ "type": "basic", "front": "...", "back": "<short core answer>",
  "explanation": "Why/context.", "source": "Author year; script p. X" }
```

Rules: keep supplementary context off the front and separate from the tested
answer; do not move the tested explanation into collapsed Details. When unsure
about a fact, verify it against the source instead of guessing.

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
  (or the `· N fig.` markers). For every card, check whether a figure offers a
  useful visual explanation, even if the text covers the same information.
  View the relevant crop
  `extracted/<topic>/figures/<name>_p<page>_*.png` with an image viewer (less
  overhead than a whole PDF page; if missing, inspect the original PDF page
  directly or render it to an image). Add helpful figures to the answer side
  using the placement rules above; use occlusion only for spatial retrieval.
- **Avoid verbosity:** LLM-typical long "paragraph cards" violate atomicity.
- **Avoid duplicates/redundancy** (not the same fact twice) — across a whole
  topic with `tools/coverage.py decks/<topic>/` (near-duplicates + coverage gaps).
- **Front-only review:** complete the separate pass above for every new or
  edited question, then self-check each card against the checklist.
- Then: `tools/lint_cards.py` (structure), `tools/grounding_check.py` (grounding),
  `tools/preview.sh` (renders **light AND night mode** → view the PNGs, check
  dark-mode readability), `tools/validate.sh` (real Anki engine) — or
  `tools/finish.sh` (lint+grounding+build+validate in one).

## Checklist — per card, before the build

- [ ] Exactly **one** atomic piece of information.
- [ ] Forces **active retrieval** (no yes/no, no whole sentence).
- [ ] Cue **unambiguous & distinct**, no hint leak.
- [ ] **Separate front-only review completed:** subject, referents and necessary
      conditions are clear without the source, deck title or other cards.
- [ ] Natural wording; no book/chapter framing; citations only in `source`.
- [ ] Answer as **short as possible**, exactly one correct form, producible.
- [ ] **Format** fits the knowledge type (table above).
- [ ] Cloze: only the keyword deleted; reverse only for genuine two-way use.
- [ ] Supplementary details/citations in `explanation`/`source`; the tested
      explanation remains in the core answer.
- [ ] **Grounded in the source**, no duplicate.
- [ ] **Visual-feedback review** done for this card: useful source graphics
      included on the answer side, or no suitable graphic available. Changed
      image layouts inspected in both themes.
