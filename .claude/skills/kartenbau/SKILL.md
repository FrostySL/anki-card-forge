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

## Formatierung & Struktur (HTML in den Feldern)

Alle Textfelder (`front`, `back`, `text`, `extra`, `explanation`) werden **als HTML
gerendert** (genanki escaped nicht). Nutze das, damit Karten lesbar strukturiert sind
statt als Fließtext-„Wurst".

- **`\n` im JSON ist KEIN Umbruch** — in HTML nur ein Leerzeichen. Für sichtbare
  Umbrüche `<br>`, für Aufzählungen `<ul><li>…</li></ul>`/`<ol>`, für Zuordnungen/
  Vergleiche `<table>` (Rahmen/Padding sind im CSS gestylt).
- **Struktur ≠ mehr Stoff.** HTML macht *eine* Karte lesbarer, hebelt aber nicht die
  Atomarität aus: keine 6-Fakten-Karte „schöner verpacken". Eine Liste mit 5 Punkten,
  die alle abgefragt werden, bleibt 5 Karten.
- **Cloze-Tabelle** für parallele Zuordnungen (Phase→Ergebnis, Begriff→Definition,
  Schicht→Protokoll): 2-Spalten-`<table>`, je Zeile **eine** Lücke in der Antwortspalte.
  Ergibt pro Zeile eine Karte mit der ganzen Tabelle als Kontext — strukturiert *und*
  atomar. Statt allem in einem Satz (`A → {{c1::…}}; B → {{c2::…}}; …`):

  ```json
  { "type": "cloze",
    "text": "<table><tr><th>Phase</th><th>Phasenergebnis</th></tr><tr><td>Analyse</td><td>{{c1::Situationsstudie/Projektplan}}</td></tr><tr><td>Definition</td><td>{{c2::Produktdefinition}}</td></tr></table>" }
  ```
- Immer mit `tools/preview.sh` rendern und die PNGs ansehen — HTML-Tippfehler fallen
  visuell sofort auf.

### Vorgefertigte CSS-Klassen & Mathe (in `_CSS`, wirken in Vorschau + .apkg)

Sparsam und gezielt einsetzen — **Distinktheit hilft, Deko schadet** (seductive
details). Farbcodierte Boxen gehören auf die **Rückseite/`explanation`**, nie auf die
Frage (Hint-Leak).

| Mittel | Wofür | Beispiel |
|---|---|---|
| `<table>` / Cloze-Tabelle | Zuordnungen, Vergleiche, parallele Fakten | siehe oben |
| `<pre><code>` / `<code>` | Quelltext / Inline-Bezeichner (monospace) | `<pre><code>git rebase -i</code></pre>` |
| `<kbd>` | Tastenkürzel | `<kbd>Strg</kbd>+<kbd>C</kbd>` |
| `\( … \)` / `\[ … \]` | Formeln (MathJax, in Anki nativ) | `\( a^2 + b^2 = c^2 \)` |
| `<div class="merke">` | Kernsatz / Take-away | ★ |
| `<div class="achtung">` | typische Falle / häufiger Fehler | ⚠ |
| `<div class="beispiel">` | Worked Example (belegt lernwirksam) | ❯ |
| `<div class="eselsbruecke">` | Mnemonik / Merkhilfe | 🧠 |
| `<span class="kontrast">…</span>` | bei Schwesterkarten das **unterscheidende** Merkmal markieren (Interferenz) | — |
| `<details class="hint"><summary>Hinweis</summary>…</details>` | gestufter Cue, auch **vorne** ok (zugeklappt → Abruf bleibt); sparsam | — |
| `<div class="flow"><span class="step">A</span><span class="arrow">→</span>…</div>` | Prozess-/Ablaufkette (Dual Coding der Reihenfolge) | — |

Nachtmodus: `.card` setzt bewusst **keine** feste `color`/`background` → Anki färbt
Text+Hintergrund je Theme selbst (Tabellen/Rahmen nutzen durchscheinende Graustufen).
Also **keine hartkodierten Farben** in die Felder schreiben, sonst dunkler Text auf
dunklem Grund. (Auf `.nightMode .card` ist kein Verlass — greift nicht in jeder Anki-
Version.) Mathe rendert in der Vorschau nur online (CDN); das fertige `.apkg` rendert
es immer (Anki bringt MathJax mit).

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
  Modellwissen → keine Halluzinationen. Quelle in `source`. Nachprüfbar mit
  `tools/grounding_check.py` (Antwort gegen Quelltext; FEHLER = evtl. erfunden).
- **Bild-Check:** Das `.md` enthält **keine Bilder**, nur Captions. Vor dem Bauen den
  Abbildungs-Index `aufbereitet/<Thema>/<name>.figures.md` (bzw. `· N Abb.`-Marker)
  durchgehen. Bei **räumlich-visuellen** Konzepten oder wenn das Bild Info trägt, die
  der Text nicht hergibt → den geschnittenen Crop
  `aufbereitet/<Thema>/figures/<name>_S<S.>_*.png` per Read-Tool ansehen (billiger als
  die ganze PDF-Seite; fehlt er, dann `pages="<S.>"` am PDF) und ggf.
  `occlusion`-/Bildkarte bauen — die Crops sind auch direkt die occlusion-`image`.
- **Verbosität vermeiden:** LLM-typische lange „Absatz-Karten" verletzen Atomarität.
- **Dubletten/Redundanz** vermeiden (nicht denselben Fakt mehrfach) — über ein ganzes
  Thema mit `tools/coverage.py decks/<Thema>/` (Beinah-Dubletten + Abdeckungslücken).
- **Selbstcheck** jede Karte gegen die Checkliste; Durchfaller neu formulieren.
- Danach: `tools/lint_cards.py` (Struktur), `tools/grounding_check.py` (Grounding),
  `tools/preview.sh` (rendert **hell UND Nachtmodus** → PNGs ansehen, auf Lesbarkeit
  im Dunkelmodus prüfen), `tools/validate.sh` (echte Anki-Engine) — oder
  `tools/finish.sh` (lint+grounding+build+validate in einem).

## Checkliste — pro Karte vor dem Build

- [ ] Genau **eine** atomare Information.
- [ ] Erzwingt **aktiven Abruf** (kein Ja/Nein, kein ganzer Satz).
- [ ] Cue **eindeutig & distinkt**, kein Hint-Leak.
- [ ] Antwort so **kurz wie möglich**, genau eine korrekte Form, produzierbar.
- [ ] **Format** passt zum Wissenstyp (Tabelle oben).
- [ ] Cloze: nur Schlüsselwort ausgelöscht; reverse nur bei echter Zwei-Wege-Nutzung.
- [ ] Vertiefung/Quelle (falls sinnvoll) in `explanation`/`source` — nicht im Abruf.
- [ ] **Aus der Quelle belegt** (grounded), keine Dublette.
- [ ] **Bild-Check** gemacht: relevante Abbildung (`.figures.md`) angesehen, falls visuell.
