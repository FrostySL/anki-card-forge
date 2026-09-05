# Evidence-based principles for designing, phrasing and format selection of flashcards for Anki / spaced repetition

*A scientifically sourced guide for creating individual flashcards, automatically or manually. Focus: design, phrasing and format choice of INDIVIDUAL cards — not scheduling (SM-2/FSRS, intervals, ease, daily limits), which Anki handles itself.*

---

## TL;DR
- **By far the best-documented rule is: every card must force active RETRIEVAL of ONE atomic piece of information from memory — with an unambiguous cue and an unambiguous, producible answer.** This is the direct application of the "testing/retrieval effect", one of the most robustly replicated findings in the psychology of learning: Roediger & Karpicke (2006) found 61 % retention after one week in the testing group vs. 40 % in the rereading group, although the latter had read the text 14.2 times instead of 3.4; Dunlosky et al. (2013) rated "practice testing" as one of only **two** of the ten techniques examined with "high utility".
- **Phrasing matters more than card type.** Choose the format by knowledge type: basic Q/A as the default for concepts and "why/how"; cloze for embedded single facts and decomposed enumerations; image occlusion for spatial/visual mapping; type-in only for exact spelling/syntax; bidirectional cards only for genuine two-way use.
- **Deeper explanation ("why"/context) and the source belong on the back — but separated from the retrieval moment**, e.g. in an HTML box collapsed by default that is opened only AFTER answering. Feedback after retrieval is demonstrably effective (Butler, Karpicke & Roediger), but must not undermine the desirable difficulty or the atomicity of the core card.

---

## Key findings (quick overview)

1. **Retrieval practice is the working mechanism of every card.** A card only "works" if it forces actual retrieval — not mere recognition or rereading.
2. **Atomicity (minimum information principle)** is doubly motivated: psychologically (retrieval effort, interference) and practically (even scheduling).
3. **Wozniak's "20 rules"** are an excellent practical guide, but mostly experiential knowledge (1999, iteratively updated), not RCT results — their core ideas, however, largely coincide with controlled findings.
4. **Image occlusion has NO direct controlled study evidence.** Its effectiveness is extrapolated from active retrieval, the picture-superiority effect and dual coding — plausible, but calling it "proven" would be an overstatement.
5. **For AI-generated cards** the main risks are hallucinations and — more frequent and more insidious — structural defects: overly long "paragraph cards", ambiguity, missing atomicity, redundancy. A high defect rate degrades the deck "slowly and invisibly".

---

## Details

### 1. Fundamentals: atomicity, unambiguity, one fact per card

**Minimum information principle / atomicity.** Piotr Wozniak (1999, "Effective learning: Twenty rules of formulating knowledge", SuperMemo) states as rule 4: *"The material you learn must be formulated in as simple way as it is [possible]."* Original rationale: simple material is processed by the brain "always in the same way" (a more stable memory trace), and simple items can be scheduled separately according to their individual difficulty. Michael Nielsen ("Augmenting Long-term Memory", 2018) and Andy Matuschak ("How to write good prompts", 2020) adopt this: prompts should be **focused, precise, consistent, tractable and effortful**.

Empirically, atomicity is supported *indirectly* by (a) the retrieval-effort principle (Pyc & Rawson 2009) — a multi-fact card allows incomplete retrieval in which parts of the target information "stay dark" —, and (b) interference (complex items cannot be strengthened evenly). Important for the AI application: the principle itself is primarily theory/practice knowledge, but congruent with the controlled effects.

> **Bad (not atomic):**
> *Q: What are the properties of TCP?*
> *A: connection-oriented, reliable, ordered delivery, flow control, congestion control, full duplex.*
> (Problem: having forgotten "2 of 6", you still easily grade it "correct" → the forgotten fact is never corrected.)
>
> **Good (atomic, split):**
> *Q: Which TCP mechanism prevents a fast sender from overwhelming a slow RECEIVER?*
> *A: flow control (sliding window).*
> + separate card: *Q: Which TCP mechanism reacts to overload in the NETWORK (not at the receiver)?*
> *A: congestion control.*

### 2. Learning-psychology basis — each principle with a concrete consequence for the card

**Retrieval practice / testing effect.** Roediger, H. L. & Karpicke, J. D. (2006). "Test-enhanced learning: Taking memory tests improves long-term retention." *Psychological Science* 17(3):249–255. In experiment 1 the testing group retained 68 % vs. 54 % (restudy) after 2 days and 56 % vs. 42 % after 1 week. Even clearer in experiment 2 (original quote): *"students in the repeated-testing condition recalled much more after a week than did students in the repeated-study condition (61 % vs. 40 %), even though students in the former condition read the passage only 3.4 times and those in the latter condition read it 14.2 times."* Remarkably, the rereading group was *subjectively* more convinced of retaining more ("illusion of competence").
→ **Consequence:** every card must be a genuine retrieval question, not a reading or recognition item.

**Retrieval beats elaboration.** Karpicke, J. D. & Blunt, J. R. (2011). "Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping." *Science* 331(6018):772–775. On the short-answer test after 1 week, the retrieval group recalled 0.67 of the idea units vs. 0.45 for concept mapping (F(1,38)=21.63) — including on comprehension and inference questions. Original abstract: *"practicing retrieval produces greater gains in meaningful learning than elaborative studying with concept mapping … The advantage of retrieval practice was observed with test questions that assessed comprehension and required students to make inferences."* (Here too, students subjectively judged concept mapping as more effective.)
→ **Consequence:** forcing retrieval is worth more than merely presenting elaborate explanations. The core card tests; the explanation is an add-on on the back (see section 5).

**Generation effect.** Slamecka, N. J. & Graf, P. (1978). "The Generation Effect: Delineation of a Phenomenon." *Journal of Experimental Psychology: Human Learning and Memory* 4(6):592–604. Across five experiments the "generate" condition consistently beat the "read" condition (cued/uncued recognition, free/cued recall, confidence).
→ **Consequence:** the card must demand production (generate the answer yourself), not recognition from options.

**Elaborative interrogation & self-explanation.** Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. & Willingham, D. T. (2013). "Improving Students' Learning With Effective Learning Techniques." *Psychological Science in the Public Interest* 14(1):4–58. Both techniques were rated **"moderate utility"** (higher than highlighting/summarizing/rereading = "low", but below practice testing/distributed practice = "high"). The effectiveness of elaborative interrogation depends on prior knowledge; effect sizes in the literature range from 0.85 to 2.57, but applicability is often limited to discrete factual statements.
→ **Consequence:** "why" cards are a sensible complement to fact cards; anchor the generated explanation on the back.

**Encoding specificity.** Tulving, E. & Thomson, D. M. (1973). "Encoding specificity and retrieval processes in episodic memory." *Psychological Review* 80(5):352–373. A retrieval cue is only effective insofar as it overlaps with the encoding context; with "cue overload" (one cue points to too many targets) retrieval fails.
→ **Consequence:** the cue on the front must address the target information **unambiguously and distinctly**. Vague question ("What is important about X?") = vague retrieval.

**Desirable difficulties.** Bjork, R. A. (1994); Bjork, E. L. & Bjork, R. A. (2011), "Making Things Hard on Yourself, But in a Good Way." Conditions that make learning harder in the short term (while remaining successful) — spaced practice, interleaving, retrieval practice, generation — improve long-term retention and transfer. Underlying is the distinction between *storage strength* and *retrieval strength*: retrieval at medium forgetting produces the largest gain.
→ **Consequence:** cards should not "give away" the retrieval (no hint leaks) but stay tractable — rule of thumb ~90 % success rate; split overly hard cards or add cues.

**Retrieval-effort hypothesis.** Pyc, M. A. & Rawson, K. A. (2009). "Testing the retrieval effort hypothesis." *Journal of Memory and Language* 60(4):437–447. Finding: *"as the difficulty of retrieval during practice increased, final test performance increased"* (given successful retrieval). Additionally: Pyc & Rawson (2010), "Why testing improves memory: Mediator effectiveness hypothesis", *Science* 330:335 — test-restudy produces more effective "mediators" (cue→target links).
→ **Consequence:** dose hints sparingly — just enough for retrieval to succeed, but not become trivial.

**Dual coding.** Paivio, A. (1971/1986); Paivio, A. & Csapo, K. (1973), "Picture superiority in free recall: Imagery or dual coding?", *Cognitive Psychology* 5(2):176–206. Pictures are encoded twice (visually + verbally), words only once → better retention for pictorial material.
→ **Consequence:** relevant diagrams/images complement the text, **not** decoratively. (Caveat: see section 9.)

### 3. Question phrasing

Supported by encoding specificity (unambiguous cue), the generation effect (production) and retrieval practice (genuine retrieval). Matuschak (2020) operationalizes: prompts should *unambiguously produce a specific answer* and *make clear what "shape" of answer they expect*.

- **Active retrievability** instead of recognition; **no yes/no questions** (50 % guessable, no generation).
- **Unambiguous answer** (exactly one correct "shape").
- **Precise cue** that does not give away the answer (no hint leak).
- **No memorizing whole sentences** — isolate the specific information.

> **Bad:** *Q: Is HTTP stateless? — A: Yes.* (yes/no, guessable, no generation)
> **Good:** *Q: Which fundamental property of HTTP means the server stores no client information between two requests? — A: statelessness.*

### 4. Format choice — which card type when?

| Format | When to use (decision rule) | Best practices | Evidence |
|---|---|---|---|
| **Basic (Q/A)** | Default. Concepts, definitions, "why/how", understanding, inference. | One question = one retrieval target. Answer as short as possible. Explanation into the collapsed box. | Directly supported (retrieval practice, generation effect). Matuschak: produces deeper processing than cloze. |
| **Cloze (fill-in)** | Embedded single facts; decomposed enumerations; facts whose context sentence carries the meaning. | Delete only the **key** information, NOT half sentences. Leave enough context, but avoid hint leaks. With several deletions, each on its own (c1, c2 …). Optional letter hint. | Proven in practice; Wozniak: "cloze deletion is fast and has great mnemonic power". But Matuschak warns: cloze invites **shallow pattern matching** and ambiguity. |
| **Image occlusion** | Spatial/visual mapping: anatomy, geography, diagrams, network topologies, UML/architecture diagrams, layer models. | Mask only test-/exam-relevant labels (not all 20 of 20). Early on 4–6 boxes/card, later max. 8–10. Consistent orientation. Complement with text cards for "why/how". | **NO direct controlled study found** (see below). Theoretical support: picture superiority + dual coding + active retrieval. |
| **Type-in ("type the answer")** | Only where exact spelling/syntax counts: CLI commands, keywords, method names, technical terms, foreign-language vocabulary. | Use sparingly. Not for concepts (typos/synonyms are falsely graded as errors → frustration, wrong difficulty). | The generation effect supports production; type-in is the strictest form of production. No specific RCT for "type-in vs. mental recall". |
| **Bidirectional / reverse** | Only for genuine **two-way use**: vocabulary L1↔L2, term↔definition, symbol↔name. | Do NOT flip everything automatically. Omit for confusable pairs. | Wozniak: "passive and active approach … particularly practicable in word-pairs". Interference risk (section 7). |

**Other sensible, evidence-adjacent formats that are often overlooked:**
- **"More-than-you-think"/application prompts** (Matuschak): query not just the fact but its meaning/application — promotes transfer.
- **Open-list/salience prompts** (Matuschak): for open sets (e.g. "Name *one* design principle that promotes loose coupling") with changing answers — leverages a different mechanism than consistent prompts and is deliberately exempt from "sister card" interference.
- **Procedural/"step-by-step" cards** for algorithms/procedures (each step cues the next — see section 6).

**Important evidence note on image occlusion:** a targeted literature search found **no** peer-reviewed randomized/controlled study that directly tests image-occlusion cards against text cards on retention — neither in anatomy education nor elsewhere. The circulating pro-occlusion sources are app marketing and blogs; among other things they repeat the **debunked myth** that "~65 % of people are visual learners" (learning-styles myth). The theoretical support (picture-superiority effect: Nelson, D. L., Reed, V. S. & Walling, J. R., 1976, "Pictorial superiority effect", *JEP: Human Learning and Memory* 2(5):523–528; N=256) was measured on **isolated** pictures vs. words, not on retrieving labels in dense diagrams. Critically, Nelson et al. showed that the picture advantage *weakens or reverses* with **high schematic similarity** of the pictures — exactly the situation with similar-looking anatomical/diagrammatic structures. **Bottom line:** image occlusion is plausible and popular in practice, but labeling it "proven" would be wrong — recommendation: use it for clearly spatial mappings, switch to text cards for "why/how".

### 5. Explanation & source on the card (elaborative feedback)

**Recommendation: yes — but structurally separated from the retrieval.** Concretely: deeper explanation ("why", context, derivation) plus source/origin in an HTML box (`<details>` element) on the back, **collapsed by default**, which the learner opens **only after answering**.

Rationale from the research:
- **Feedback after retrieval works.** Roediger & Butler (2011, *Trends in Cognitive Sciences*): *"Retrieval practice is often effective even without feedback … but feedback enhances the benefits of testing."* Butler, Karpicke & Roediger (2007/2008): feedback helps especially by strengthening correct but low-confidence answers; **delayed** feedback (= after one's own answer attempt) outperformed immediate feedback.
- **Elaborative interrogation / self-explanation** (Dunlosky et al. 2013, "moderate utility"): the "why" explanation on the back supports integration with prior knowledge.
- **Source memory:** Nielsen advises storing the originator for uncertain facts ("beware of committing false facts to memory"); Wozniak rules 18/19: state source and date (especially for time-varying knowledge).

**The danger (and its avoidance):** extra information must neither lower the **retrieval difficulty** (explanation not on the front, not visible before retrieval) nor undermine **atomicity** (the explanation is NOT part of the tested answer — it is not queried). Hence: the core retrieval stays an atomic Q/A; the box is optional, downstream feedback.

> **Good:**
> *Front: Why does an index on a column reduce read cost but increase write cost?*
> *Back (core answer): reads use the sorted structure (e.g. B-tree) for O(log n) lookup; every write must additionally update the index.*
> *▸ [collapsed] Details & source: a B-tree keeps data sorted → range queries efficient; every INSERT/UPDATE/DELETE must rebalance the tree. Source: Kemper & Eickler, Datenbanksysteme, ch. on index structures.*

### 6. Lists, enumerations, orders, processes

- **Wozniak rules 9/10:** "Avoid sets and enumerations" — they are hard to retain but can be decomposed via **cloze deletion**.
- **Overlapping cloze** (add-on "Cloze Overlapper") for longer sequences/processes: each card masks one element but shows the neighboring steps as scaffolding.
- **Sequential cues:** step n as the cue for step n+1 (good for algorithms, build pipelines, OSI layers).
- **Preferred: decompose into atomic single facts**, possibly plus one integrating "overview" card.

> **Bad:** *Q: Name all 7 OSI layers. — A: Physical, Data Link, Network, Transport, Session, Presentation, Application.*
> **Good (relational cloze):** *Above the {{c1::transport}} layer (L4) sits the {{c2::session}} layer (L5).* + *Q: On which OSI layer does a router primarily operate? — A: layer 3 (network).*

### 7. Avoiding interference

- **Wozniak rule 11 "Combat interference"** — per SuperMemo experience *"probably the single greatest cause of forgetting"* for experienced users. Theoretically supported by Tulving & Thomson (cue overload) and the literature on proactive/retroactive interference.
- Separate **"sister cards"** (overly similar cards): distinct cues, contrasting phrasing, explicitly name the shared source of confusion.
- **Retrieval-induced forgetting** (Matuschak): inconsistent prompts that demand this answer now, that answer later inhibit the non-retrieved sibling knowledge → keep prompts **consistent**.
- **Bidirectional cards:** help with genuine vocabulary pairs, **hurt** with confusable pairs (e.g. two similar technical terms whose forward and reverse directions interfere with each other).

> **Bad (interference-prone):** two nearly identical cards "latency = ?" and "throughput = ?" without contrasting context.
> **Good:** *Q: Which network metric measures the DELAY of a single packet (time), not the amount of data per time? — A: latency.* (The contrast "time vs. amount/time" disambiguates both cards.)

### 8. Understanding & context

- **Wozniak rules 1–2:** "Do not learn if you do not understand" and "Learn before you memorize" — first build the big picture, then decompose into atomic items. Karpicke & Blunt show that retrieval practice promotes *meaningful* learning, not just rote memorization — provided the material was understood.
- **Nielsen:** no "orphan questions" (orphaned factoids) — embed cards in a single pool with clear context; phrase questions so the context is unambiguous.
- **Sufficient context on the card** so the cue stays distinct (encoding specificity) without giving away the answer.
- **Personalization & own examples** (Wozniak rule 16): own examples/applications are especially effective (congruent with the generation effect).

### 9. Mnemonics, images, examples

- **Images/dual coding** (Paivio & Csapo 1973): picture+word are effective for pictorial material. Caveat: picture superiority weakens with highly similar pictures (Nelson et al. 1976) — so choose distinct, non-decorative images.
- **Keyword mnemonics** were rated only **"low utility"** by Dunlosky et al. (2013) (narrowly applicable, fragile long-term retention) — use deliberately, not as the default.
- **Own examples** (personalization) are robustly effective (generation effect).

### 10. Common anti-patterns (each bad → good)

1. **Multi-fact card.** Bad: "Name all ACID properties and explain each." → Good: four atomic cards, one property each.
2. **Yes/no or guessable question.** Bad: "Is quicksort stable?" → Good: "Which property does quicksort lack in its standard form w.r.t. equal keys? — stability."
3. **Whole sentence as cloze.** Bad: "{{c1::Quicksort}} has an {{c2::average}} runtime of {{c3::O(n log n)}} but a {{c4::worst case}} of {{c5::O(n²)}}." (too many deletions, pattern matching) → Good: separate cards "quicksort average-case runtime? — O(n log n)" / "quicksort worst-case runtime? — O(n²)".
4. **Hint leak.** Bad: "The ACID acronym starts with A for {{c1::Atomicity}}." (the "A for" gives it away) → Good: "ACID — which property guarantees that a transaction executes fully or not at all? — atomicity."
5. **Decorative image without retrieval relevance.** → Good: an image showing the queried spatial/structural relationship.
6. **Orphan factoid** without context. Bad: "1965 — what? — Moore's law." → Good: "Who postulated in 1965 the doubling of transistors per chip roughly every two years? — Gordon Moore (Moore's law)."

### 11. Specifically for AI-/automatically generated cards

**Typical failure sources:**
- **Hallucinations** (invented facts) — especially with smaller/offline models and without source binding.
- **Structural defects** (more frequent and more insidious than open hallucinations): overly long, ambiguous, context-dependent "paragraph cards". They look plausible at first glance but cause friction months later (several valid answers, wrong memory trigger). LLMs tend towards verbosity and thereby violate the minimum information principle.
- **Redundancy** (several cards for the same fact) and **topic drift** (questions about "spaced repetition" instead of the content).

**Quality assurance (for the AI guideline):**
1. **Enforce atomicity** — one card = one retrieval target; split long answers automatically.
2. **Source binding / grounding:** generate cards only from the provided source text (RAG/"grounded generation"), not from model knowledge → minimizes hallucinations. Write the source into the collapsed box.
3. **Few-shot + structured output:** provide good example cards and a fixed format → reduces defects and makes them machine-checkable.
4. **Automatic self-check ("LLM as judge"):** check every card against the checklist (atomic? unambiguous? hint leak? guessable? answer short? supported by the source?); regenerate cards that fail.
5. **Human in the loop (spot checks):** LLMs lack the "taste" to judge whether a card holds up long-term — sample-based manual review remains necessary, since a high defect rate degrades the deck gradually.
6. **Duplicate/redundancy check** via embedding similarity.

---

## Recommendations (tiered, with thresholds)

**Implement immediately (mandatory rules for the AI):**
1. **Every card = one atomic retrieval.** If the answer contains >1 independent fact or >~1 short sentence → split.
2. **Force genuine retrieval:** no yes/no, no recognition questions; unambiguous, distinct cue; unambiguous, producible answer.
3. **Format by knowledge type** (table in section 4): basic = default; cloze for embedded facts; image occlusion only for spatial/visual mapping; type-in only for exact spelling; reverse only for genuine two-way use.
4. **Explanation + source in a collapsed `<details>` box** on the back, separate from the core retrieval.
5. **Grounding:** card content exclusively from the source material; when unsure, cite the originator/source instead of guessing.

**Quality gate (before importing into the deck):**
6. Automatic "LLM as judge" check per card against the checklist below; failure → regeneration.
7. Embedding duplicate check; remove redundancy.

**Thresholds that would change the recommendation:**
- If a card's **error rate** stays high in review (learners "never get it") → the card is too complex/ambiguous → split or add cues (Matuschak's "sigh test").
- If a deck's success rate drops systematically below ~90 % → too many non-atomic or interfering cards → refactor.
- If cloze cards show pure **pattern matching** (correct, but without understanding) → convert to basic Q/A.
- For image material without a clear spatial mapping → **no** image occlusion, use a text card instead (occlusion evidence is lacking and picture superiority fails with similar structures).

---

## Checklist "rules for good cards" (compact, AI-applicable)

**Content & structure**
- [ ] Exactly **one** atomic piece of information per card (minimum information principle).
- [ ] Material understood beforehand; no orphan factoid; enough context, but no hint leak.

**Question/cue**
- [ ] Forces **active retrieval** (no yes/no, no recognition, no whole sentence).
- [ ] Cue is **unambiguous & distinct** (encoding specificity, no cue overload).
- [ ] **Tractable** (target success rate ~90 %), but **effortful** (answer not derivable).

**Answer**
- [ ] As short as possible; exactly one correct "shape"; producible.

**Format**
- [ ] Format fits the knowledge type (basic/cloze/occlusion/type-in/reverse — see table).
- [ ] Cloze: only the keyword deleted, hint leaks checked.
- [ ] Reverse only for genuine two-way use; interference/"sister cards" checked.

**Feedback/source**
- [ ] Details ("why"/context) + source in a **collapsed** box on the back, separate from the retrieval.

**AI quality**
- [ ] Grounded in the source text, no hallucination; duplicate check passed; self-/spot-check passed.

---

## Full source list

**Primary literature (peer-reviewed)**
- Roediger, H. L. & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science*, 17(3), 249–255.
- Roediger, H. L. & Butler, A. C. (2011). The critical role of retrieval practice in long-term retention. *Trends in Cognitive Sciences*, 15(1), 20–27.
- Karpicke, J. D. & Blunt, J. R. (2011). Retrieval practice produces more learning than elaborative studying with concept mapping. *Science*, 331(6018), 772–775.
- Karpicke, J. D. & Roediger, H. L. (2008). The critical importance of retrieval for learning. *Science*, 319(5865), 966–968.
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. & Willingham, D. T. (2013). Improving students' learning with effective learning techniques: Promising directions from cognitive and educational psychology. *Psychological Science in the Public Interest*, 14(1), 4–58.
- Slamecka, N. J. & Graf, P. (1978). The generation effect: Delineation of a phenomenon. *Journal of Experimental Psychology: Human Learning and Memory*, 4(6), 592–604.
- Tulving, E. & Thomson, D. M. (1973). Encoding specificity and retrieval processes in episodic memory. *Psychological Review*, 80(5), 352–373.
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185–205). MIT Press.
- Bjork, E. L. & Bjork, R. A. (2011). Making things hard on yourself, but in a good way: Creating desirable difficulties to enhance learning. In *Psychology and the Real World* (pp. 56–64). Worth.
- Pyc, M. A. & Rawson, K. A. (2009). Testing the retrieval effort hypothesis: Does greater difficulty correctly recalling information lead to higher levels of memory? *Journal of Memory and Language*, 60(4), 437–447.
- Pyc, M. A. & Rawson, K. A. (2010). Why testing improves memory: Mediator effectiveness hypothesis. *Science*, 330(6002), 335.
- Butler, A. C., Karpicke, J. D. & Roediger, H. L. (2007). The effect of type and timing of feedback on learning from multiple-choice tests. *Journal of Experimental Psychology: Applied*, 13(4), 273–281.
- Paivio, A. & Csapo, K. (1973). Picture superiority in free recall: Imagery or dual coding? *Cognitive Psychology*, 5(2), 176–206.
- Paivio, A. (1971/1986). *Imagery and Verbal Processes* / *Mental Representations: A Dual Coding Approach*. Holt/Oxford University Press.
- Clark, J. M. & Paivio, A. (1991). Dual coding theory and education. *Educational Psychology Review*, 3(3), 149–170.
- Nelson, D. L., Reed, V. S. & Walling, J. R. (1976). Pictorial superiority effect. *Journal of Experimental Psychology: Human Learning and Memory*, 2(5), 523–528.
- Hattie, J. & Timperley, H. (2007). The power of feedback. *Review of Educational Research*, 77(1), 81–112.
- Pashler, H., Bain, P., Bottge, B., Graesser, A., Koedinger, K., McDaniel, M. & Metcalfe, J. (2007). *Organizing Instruction and Study to Improve Student Learning* (IES Practice Guide, NCER 2007-2004). U.S. Department of Education.

**Anki in medical education (observational/correlational)**
- Deng, F., Gluckstein, J. A. & Larsen, D. P. (2015). Student-directed retrieval practice is a predictor of medical licensing examination performance. *Perspectives on Medical Education*, 4(6), 308–313. (Finding: each additional ~1700 unique Anki cards ≈ +1 point USMLE Step 1; B=5.89×10⁻⁴, p=0.024.)
- Wothe, J. K. et al. (2023). Academic and wellness outcomes associated with use of Anki spaced repetition software in medical school. *Journal of Medical Education and Curricular Development*, 10. (Daily Anki use correlates with a higher Step 1 score, p=0.039; not Step 2.)

**Practice sources (experiential / not peer-reviewed)**
- Wozniak, P. (1999, upd.). Effective learning: Twenty rules of formulating knowledge. SuperMemo. (incl. minimum information principle.)
- Nielsen, M. (2018). Augmenting Long-term Memory. augmentingcognition.com/ltm.html
- Matuschak, A. (2020). How to write good prompts: using spaced repetition to create understanding. andymatuschak.org/prompts
- Matuschak, A. & Nielsen, M. (2019). How can we develop transformative tools for thought? numinous.productions/ttft
- Anki Manual (Ankitects). docs.ankiweb.net (cloze, note/card types, reverse).

---

## Caveats (limitations of the evidence)

- **Wozniak's "20 rules" and much of the concrete card best practice (Nielsen, Matuschak)** are experience-based, not tested in RCTs. Their core ideas, however, are congruent with controlled findings (retrieval practice, generation effect, interference).
- **Image occlusion** has **no** direct controlled effectiveness evidence; the rationale is extrapolation from picture superiority/dual coding, whose classic studies were run on isolated pictures (not on diagram labels) — and the picture advantage can vanish with similar structures. Circulating "65 % visual learners" claims are a debunked myth.
- **Anki studies in medicine** are consistently **observational/correlational** and confounded by self-selection (more motivated/stronger students use Anki more); at least one cohort study found no significant association. They support *retrieval practice + spacing in general*, not a specific card format.
- **Elaborative interrogation/self-explanation** are only "moderate utility" and strongly dependent on prior knowledge; insufficiently evaluated in real educational contexts.
- **Type-in vs. mental retrieval**: no specific RCT; the recommendation follows from the generation effect and practical logic (exact spelling).
- For the format question in general: the **phrasing** is empirically better secured than the **format choice** — the latter rests more on practice consensus.
