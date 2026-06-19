# Anki-Karten — Projekt-Anleitung (für Claude)

Dieses Projekt erzeugt **Anki-Karteikarten aus Quelldateien**.
**Claude (ich) bin die KI**, die die Karten inhaltlich erstellt — es gibt **keinen**
externen LLM-Aufruf und keinen API-Key. Docker macht nur das stumpfe
„Karten-JSON → `.apkg`" über die Lib `genanki`.

## Ordner

| Ordner | Zweck |
|---|---|
| `quellen/` | Der Nutzer legt hier PDFs / Texte / Markdown rein. |
| `decks/` | Hier landen die generierten `.cards.json` **und** die fertigen `.apkg`. |
| `tools/` | `build_deck.py` (JSON→apkg), `build.sh` (Wrapper), `preview.py`/`preview.sh` (Karten→PNG), `detect_labels.py`/`detect.sh` (OCR→exakte Boxen), `lint_cards.py` (Inhalts-Check), `validate.py`/`validate.sh` (echte Anki-Engine). |
| `reference/anki-manual/` | Offizielles Anki-Handbuch als Nachschlagewerk (nicht anfassen). |
| `reference/anki/` | Anki-Quellcode (shallow clone) als Nachschlagewerk — **nur lesen**. Hat eigene `CLAUDE.md`/`AGENTS.md`; das sind Ankis Dev-Hinweise, nicht für dieses Projekt. Natives Image-Occlusion-Format: `rslib/src/image_occlusion/imageocclusion.rs`. |

## Workflow, wenn der Nutzer Karten will

1. Quelldatei liegt in `quellen/` (z. B. `quellen/skript.pdf`).
2. **Lies** die Datei mit dem Read-Tool (PDFs kann das Read-Tool direkt lesen).
3. **Erstelle** die Karten und schreibe sie als JSON nach `decks/<name>.cards.json`
   (Format unten).
4. **Baue** das Paket:
   ```bash
   ./tools/build.sh decks/<name>.cards.json
   ```
   → erzeugt `decks/<name>.apkg`. (Image fehlt? `docker build -t anki-karten .`)

   **Mehrere Dateien in EINE .apkg** bündeln (jede Datei = eigenes Deck; `::` im
   Decknamen erzeugt Unterdecks): alle `.json` angeben + ein `.apkg` als Ausgabe:
   ```bash
   ./tools/build.sh decks/text.cards.json decks/bilder.cards.json decks/komplett.apkg
   ```
5. Sag dem Nutzer, dass `decks/<name>.apkg` fertig ist
   → in Anki per **Datei → Importieren** oder Doppelklick laden.

## Feedbackloop: Karten vor dem Export selbst prüfen

Bevor du eine `.apkg` als „fertig" meldest — besonders bei **Image-Occlusion**, wo
die Boxen per Auge platziert sind — prüfe das Ergebnis:

1. **Inhalt schnell linten** (reines Python, kein Docker nötig):
   ```bash
   python3 tools/lint_cards.py decks/<name>.cards.json
   ```
   Meldet leere Felder, fehlende Lücken, Occlusion-Koordinaten außerhalb 0..1,
   doppelte Fragen usw.
2. **Darstellung rendern** (headless Chromium, gleiches HTML wie im .apkg):
   ```bash
   ./tools/preview.sh decks/<name>.cards.json
   ```
   → `decks/preview/<name>/NN-<typ>-front.png` + `-back.png` (+ `index.html`).
3. **PNGs mit dem Read-Tool ansehen.** Prüfe: Decken die Occlusion-Masken die
   richtigen Stellen? Zeigt die Rückseite das richtige Label? Layout ok?
4. Sitzt etwas daneben → Koordinaten/Texte in `decks/<name>.cards.json` anpassen,
   dann erneut **preview** (und am Ende **build**). Schleife, bis es passt.
5. **In der echten Anki-Engine validieren** (importiert + rendert jede Karte mit
   Ankis Backend, ohne GUI — stärker als die Vorschau-Emulation):
   ```bash
   ./tools/validate.sh decks/<name>.apkg
   ```
   Exit 0 = Import ok, keine Render-Fehler, keine leeren Karten. Bei Problemen
   meldet es Notiztyp + Karte.

> Das Vorschau-Image (`anki-karten-preview`) ist groß (Chromium) und wird beim
> ersten `preview.sh`-Aufruf automatisch gebaut. Das schlanke Builder-Image bleibt
> davon unberührt.

## Karten-JSON-Format

```json
{
  "deck": "Biologie::Kapitel 3 - Zellatmung",
  "cards": [
    {
      "type": "basic",
      "front": "Wo in der Zelle findet die Zellatmung statt?",
      "back": "In den Mitochondrien.",
      "tags": ["bio", "zellatmung"]
    },
    {
      "type": "cloze",
      "text": "Die Glykolyse läuft im {{c1::Zytoplasma}} ab und liefert netto {{c2::2 ATP}}.",
      "extra": "Vorstufe der Zellatmung, sauerstoffunabhängig.",
      "tags": ["bio", "zellatmung"]
    }
  ]
}
```

- `deck`: Deckname. `::` erzeugt Unterdecks in Anki.
- `type`: `"basic"` (Front/Back), `"cloze"` (Lückentext mit `{{c1::...}}`),
  `"typein"` (Antwort eintippen, Anki prüft) oder `"occlusion"` (Bild mit
  verdeckten Bereichen, siehe unten).
- `extra` (cloze/occlusion) und `tags` sind optional.

## Kartentypen im Detail

- **basic** — `front`, `back`. Mit `"reverse": true` werden **beide** Richtungen
  erzeugt (Vor- und Rückrichtung, eine Notiz → zwei Karten) — gut für Begriff ↔
  Definition / Vokabeln.
- **typein** — `front`, `back`. Du tippst die Antwort, Anki vergleicht sie. Nur für
  **exakte, kurze** Antworten (Begriffe, Schreibweisen, Abkürzungen).
- **cloze** — `text` mit `{{c1::Lücke}}`, optional `{{c1::Lücke::Hinweis}}`;
  mehrere `c1/c2/...` → mehrere Karten.
- **occlusion** — Bild mit verdeckten Bereichen (siehe unten).

### Vertiefung & Quelle (Klappbox) — auf JEDER Karte möglich

Zwei optionale Felder an **jeder** Karte:
- `explanation` — tiefere Erklärung / Zusammenhang („warum"). Darf HTML enthalten.
- `source` — Herkunft/Beleg, z. B. `"Cockburn 2005; Skript S. 3"`.

Beide erscheinen **nur auf der Rückseite** in einer **standardmäßig zugeklappten**
Box („▸ Vertiefung & Quelle"). Wichtig (lernpsychologisch): zugeklappt + nach dem
Abruf = elaboratives Feedback, ohne die Frage zu erleichtern. Also **nicht** den
Antwort-Kern dort verstecken — die Box ergänzt, sie ersetzt die Antwort nicht.

```json
{ "type": "basic", "front": "...", "back": "...",
  "explanation": "Kurz, warum/Zusammenhang.", "source": "Autor Jahr; Skript S. X" }
```

## Image Occlusion ("Bild mit verdeckten Bereichen")

Eigener, selbst-gerenderter Kartentyp (HTML/CSS-Overlay über dem Bild — läuft in
jeder Anki-Version, unabhängig von Ankis internem IO-Format). Pro Bereich (`region`)
wird **eine Karte** erzeugt.

```json
{
  "type": "occlusion",
  "image": "quellen/herz.png",
  "mode": "hide-one",
  "header": "Beschrifte das Herz",
  "extra": "<i>Aus: Anatomie-Skript S. 12</i>",
  "regions": [
    {"label": "Aorta",            "x": 0.30, "y": 0.10, "w": 0.12, "h": 0.06},
    {"label": "linke Herzkammer", "x": 0.55, "y": 0.60, "w": 0.18, "h": 0.10}
  ],
  "tags": ["anatomie", "herz"]
}
```

- `image`: Pfad **relativ zum Projekt-Root** (z. B. `quellen/herz.png`). Das Bild
  wird automatisch ins `.apkg` eingebettet.
- `mode`: `"hide-one"` (nur der gesuchte Bereich ist verdeckt, Rest sichtbar) oder
  `"hide-all"` (alle verdeckt, beim Aufdecken wird nur der gesuchte gezeigt).
- `regions`: Liste der Bereiche. **Koordinaten als Bruchteil 0..1** (relativ zur
  Bildgröße): `x`/`y` = obere linke Ecke, `w`/`h` = Breite/Höhe. `label` = die
  Antwort, die auf der Rückseite erscheint.

### So platziere ich (Claude) die Bereiche

**Bevorzugt: OCR (pixelgenau).** Bei Bildern mit Textbeschriftungen zuerst die
exakten Boxen erkennen lassen:
```bash
./tools/detect.sh quellen/bild.png        # optional: --lang deu+eng --min-conf 45
```
→ erzeugt `quellen/bild.labels.json` (erkannte Labels mit Bruchteil-Koordinaten)
und `quellen/bild.labels.png` (Bild mit nummerierten Boxen). Das annotierte PNG mit
dem Read-Tool ansehen, die relevanten Labels auswählen und ihre `x/y/w/h` **1:1** in
die occlusion-`regions` übernehmen (mehrzeilige Labels ggf. zu einer Box vereinen).

**Fallback: per Auge.** Wenn OCR ein Label nicht findet (gedrehter/stilisierter Text,
niedriger Kontrast): Bild mit dem Read-Tool ansehen, Box als Bruchteile (0,0 = oben
links, 1,1 = unten rechts) schätzen.

**Immer danach:** mit `./tools/preview.sh` rendern, das PNG ansehen und prüfen, ob
die Masken sitzen; sonst Koordinaten in der `.cards.json` anpassen und neu rendern.

## Qualitätsregeln für gute Karten

**Vor dem Erstellen von Karten den Skill `kartenbau` befolgen**
(`.claude/skills/kartenbau/SKILL.md`) — die evidenzbasierte Methodik samt Checkliste.
Belege/Quellen: `.claude/skills/kartenbau/research.md`.

Kernregeln (Kurzfassung, Details im Skill):
- **Atomar:** eine abrufbare Tatsache pro Karte. Lange Antwort → aufteilen.
- **Echter Abruf:** eindeutiger, distinkter Cue; produzierbare Antwort; kein Ja/Nein,
  kein ganzer Satz, kein Hint-Leak; ~90 % lösbar, aber fordernd.
- **Format nach Wissenstyp:** Basic = Default; Cloze für eingebettete Fakten;
  Occlusion nur räumlich-visuell; typein nur exakte Schreibung; reverse nur echte
  Zwei-Wege-Nutzung.
- **Vertiefung/Quelle** in `explanation`/`source` (zugeklappte Box), **nicht** in den
  Abruf.
- **Grounding:** nur was im Quelltext steht (keine Halluzination); bei Unsicherheit
  Quelle nennen statt raten. **Tags** pro Karte. Nur Lernrelevantes verkarten.
