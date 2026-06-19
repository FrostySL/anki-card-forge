---
name: kartenbau
description: Beim Erstellen von Anki-Karteikarten aus Lernmaterial anwenden. Evidenzbasierte Regeln, WIE man inhaltlich gute Karten formuliert und das richtige Format wählt (Atomarität, aktiver Abruf, Basic/Cloze/Occlusion/type-in/reverse, Vertiefung+Quelle). Immer befolgen, bevor Karten generiert werden.
---

# Kartenbau — evidenzbasierte Methodik

Anwenden, **bevor** du Karten (`*.cards.json`) erzeugst. Volle Belege/Quellen:
[research.md](research.md). Kartentypen, Felder und der Build-/Prüf-Workflow:
siehe `CLAUDE.md` im Projekt-Root.

## Kernprinzip (das Wichtigste)

**Jede Karte erzwingt den aktiven Abruf EINER atomaren Information** — eindeutiger
Cue, eindeutige, selbst produzierbare Antwort. Das ist der am besten belegte Befund
(Retrieval/Testing-Effekt). **Die Formulierung ist wichtiger als der Kartentyp.**

## Pflichtregeln

1. **Atomar:** eine Karte = ein Abrufziel. Antwort > 1 unabhängige Tatsache oder
   > ~1 kurzer Satz → **aufteilen**.
2. **Echter Abruf:** keine Ja/Nein-Fragen, kein Wiedererkennen, kein Auswendiglernen
   ganzer Sätze. Antwort selbst *produzieren*.
3. **Eindeutiger, distinkter Cue** (kein „Was ist wichtig an X?"), der die Antwort
   **nicht verrät** (kein Hint-Leak).
4. **Lösbar (~90 %) aber fordernd:** Antwort darf nicht trivial ableitbar sein.
5. **Sprache = Sprache der Quelle.** Nur das Prüfungs-/Lernrelevante verkarten.

## Formatwahl (nach Wissenstyp)

| Format (`type`) | Wann |
|---|---|
| **basic** | Default: Konzepte, Definitionen, „Warum/Wie", Verständnis, Inferenz. |
| **cloze** | Eingebettete Einzelfakten; Kontextsatz trägt die Bedeutung. Nur das **Schlüsselwort** auslöschen, nicht halbe Sätze; mehrere Lücken → c1, c2 … einzeln. |
| **occlusion** | Nur **räumlich-visuelle** Zuordnung (Anatomie, Geografie, Diagramme, Architektur). Nur prüfungsrelevante Labels verdecken. Für „Warum/Wie" → Text-Karte. |
| **typein** | Nur wo **exakte Schreibung/Syntax** zählt (Befehle, Schlüsselwörter, Termini, Vokabeln). Nicht für Konzepte (Tippfehler/Synonyme = Frust). |
| **basic + `reverse:true`** | Nur bei echter **Zwei-Wege-Nutzung** (Vokabel L1↔L2, Term↔Definition). Bei verwechselbaren Paaren weglassen (Interferenz). |

## Listen / Reihenfolgen / Prozesse

- Bevorzugt in **atomare Einzelfakten** zerlegen (+ optional eine Übersichtskarte).
- Aufzählungen → **Beziehungs-Cloze** statt „Nenne alle …".
- Reihenfolgen/Algorithmen → **sequenzielle Cues** (Schritt n cued Schritt n+1).

## Interferenz vermeiden

- Zu ähnliche Karten („sister cards") durch **distinkte, kontrastierende** Cues trennen
  (die Verwechslungsquelle explizit benennen).
- Prompts **konsistent** halten (nicht mal so, mal so fragen).

## Vertiefung & Quelle (Klappbox)  →  Felder `explanation` + `source`

Tiefere Erklärung („warum"/Zusammenhang) und Herkunft gehören auf die **Rückseite**,
aber **getrennt vom Abruf**: in unsere standardmäßig **zugeklappte** `<details>`-Box.
In der `*.cards.json` über die optionalen Felder:

```json
{ "type": "basic", "front": "...", "back": "<kurze Kernantwort>",
  "explanation": "Warum/Zusammenhang.", "source": "Autor Jahr; Skript S. X" }
```

Regeln: Die Erklärung **nicht** auf die Vorderseite und **nicht** in die getestete
Antwort (sonst sinkt Abrufschwierigkeit / Atomarität). Bei Unsicherheit über einen
Fakt → Quelle nennen statt raten.

## Anti-Patterns (kurz)

- Mehr-Fakten-Karte → aufteilen.
- Ja/Nein-/ratbare Frage → in „welche Eigenschaft …?" umformen.
- Ganzer Satz als Cloze / zu viele Lücken → einzelne atomare Karten.
- Hint-Leak (Cue verrät Antwort) → umformulieren.
- Dekoratives Bild ohne Abrufbezug → weglassen oder echte Zuordnung zeigen.
- Verwaister Faktoid ohne Kontext → Kontext in den Cue.

## Beim KI-Generieren (also: von dir)

- **Grounding:** Karteninhalt **nur** aus dem bereitgestellten Quelltext, nicht aus
  Modellwissen → keine Halluzinationen. Quelle in `source`.
- **Verbosität vermeiden:** LLM-typische lange „Absatz-Karten" verletzen Atomarität.
- **Dubletten/Redundanz** vermeiden (nicht denselben Fakt mehrfach).
- **Selbstcheck** jede Karte gegen die Checkliste; Durchfaller neu formulieren.
- Danach: `tools/lint_cards.py` (Struktur), `tools/preview.sh` (ansehen),
  `tools/validate.sh` (echte Anki-Engine).

## Checkliste — pro Karte vor dem Build

- [ ] Genau **eine** atomare Information.
- [ ] Erzwingt **aktiven Abruf** (kein Ja/Nein, kein ganzer Satz).
- [ ] Cue **eindeutig & distinkt**, kein Hint-Leak.
- [ ] Antwort so **kurz wie möglich**, genau eine korrekte Form, produzierbar.
- [ ] **Format** passt zum Wissenstyp (Tabelle oben).
- [ ] Cloze: nur Schlüsselwort ausgelöscht; reverse nur bei echter Zwei-Wege-Nutzung.
- [ ] Vertiefung/Quelle (falls sinnvoll) in `explanation`/`source` — nicht im Abruf.
- [ ] **Aus der Quelle belegt** (grounded), keine Dublette.
