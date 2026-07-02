# Anki-Karten — Projekt-Anleitung (für Claude)

Dieses Projekt erzeugt **Anki-Karteikarten aus Quelldateien**.
**Claude (ich) bin die KI**, die die Karten inhaltlich erstellt — es gibt **keinen**
externen LLM-Aufruf und keinen API-Key. Docker macht nur das stumpfe
„Karten-JSON → `.apkg`" über die Lib `genanki`.

## Ordner

| Ordner | Zweck |
|---|---|
| `quellen/<Thema>/` | Quellen **pro Themengebiet** in eigenem Unterordner (z. B. `quellen/Biologie/`, `quellen/Mathe/`, `quellen/Softwareentwicklung/`). PDFs/Texte/Markdown. Optional eine **`context.md`** (Groß-/Kleinschreibung bzw. `Kontext.md` tolerieren — im Zweifel `ls quellen/<Thema>/`) mit Kontext zum Thema (worum geht's, wozu/warum gebraucht, Fokus, Prüfungsrelevanz) — **vor** dem Kartenbau lesen. |
| `decks/<Thema>/` | Spiegelt die Themen: generierte `.cards.json` **und** `.apkg` liegen im selben Themenordner (z. B. `decks/Biologie/`). |
| `aufbereitet/<Thema>/` | **Maschinenlesbare Markdown-Extrakte** der Quellen (via `tools/extract.sh`), gespiegelt nach Thema (z. B. `aufbereitet/Biologie/zellatmung.md`). Hier lese/zitiere ich effizient statt aus dem PDF. Dazu pro Datei ein **`<name>.figures.md`** (Abbildungs-Index: „Abb. N – S. P: Titel"); Seitenmarker zeigen die Bildzahl (`<!-- S. 12 · 2 Abb. -->`). **Bilder selbst sind nicht im `.md`** — entweder die echte Seite via Read-Tool am PDF ansehen (`pages="<S.>"`) **oder** die per `figextract.sh` geschnittenen Crops unter **`figures/<name>_S<Seite>_<i>.png`** nutzen (Manifest `<name>.figures.json`: Seite, Bbox 0..1, Art). Gitignored (abgeleitet, reproduzierbar). |
| `tools/` | `build_deck.py` (JSON→apkg), `build.sh` (Wrapper), `extract.py`/`extract.sh` (PDF→Markdown, OCR-Fallback), `figindex.py` (Abbildungs-Index, stdlib), `figextract.py`/`figextract.sh` (Abbildungen aus PDF schneiden → PNG-Crops), `preview.py`/`preview.sh` (Karten→PNG), `detect_labels.py`/`detect.sh` (OCR→exakte Boxen), `lint_cards.py` (Struktur-Check), `grounding_check.py` (Karten gegen Quelltext prüfen), `coverage.py` (Dubletten + Abdeckung über alle cards.json), `validate.py`/`validate.sh` (echte Anki-Engine), `apkg_to_cards.py` (`.apkg` → `cards.json` zurück, **GUIDs erhalten** — für Änderungen an bereits gelernten Decks ohne Fortschrittsverlust). **Orchestratoren:** `prep.sh` (extract+figindex+figextract in einem), `finish.sh` (lint+grounding[+coverage]+build+validate; auch mehrere cards.json → eine .apkg). **Tests:** `test.sh` (`tests/`, stdlib-`unittest` der Logik-Tools — kein Docker, kein pip; `./tools/test.sh`). |
| `.githooks/` | **Commit-Guard** (`pre-commit`): Das Repo ist **öffentlich** — der Hook blockiert Commits, die persönliches Material hinzufügen würden (quellen/, aufbereitet/, decks/-Inhalte, PDFs/.apkg), auch bei `git add -f`. Aktiv via `git config core.hooksPath .githooks` (einmal pro Clone). Blockiert er zu Unrecht: Allowlist im Hook erweitern, nicht blind `--no-verify`. |
| `reference/` | **Lokale** Anki-Nachschlagewerke (Handbuch + Quellcode), **nicht im Repo** (fremde Lizenz/AGPL) — optional lokal klonen, siehe `reference/README.md`. |
| `reference/anki-manual/` | Offizielles Anki-Handbuch als Nachschlagewerk (nicht anfassen). Falls lokal vorhanden. |
| `reference/anki/` | Anki-Quellcode (shallow clone) als Nachschlagewerk — **nur lesen**, falls lokal vorhanden. Hat eigene `CLAUDE.md`/`AGENTS.md`; das sind Ankis Dev-Hinweise, nicht für dieses Projekt. Natives Image-Occlusion-Format: `rslib/src/image_occlusion/imageocclusion.rs`. |

## Workflow, wenn der Nutzer Karten will

**Konvention: pro Themengebiet ein Unterordner.** Quellen in `quellen/<Thema>/`,
erzeugte Karten/Pakete in `decks/<Thema>/`. Der **Deckname** beginnt mit dem Thema,
damit Anki es als oberstes Deck führt: `"<Thema>::<Titel>"` (z. B.
`"Biologie::Zellatmung"`).

1. Quelldatei liegt in `quellen/<Thema>/` (z. B. `quellen/Biologie/zellatmung.pdf`).
   **Liegt eine `quellen/<Thema>/context.md` (oder anders geschrieben, z. B.
   `Kontext.md`) vor, zuerst diese lesen** — sie sagt, worum es geht und worauf der
   Fokus liegt; das steuert Auswahl und Schwerpunkt der Karten.
2. **Quelle aufbereiten** (einmal pro neuer Datei): PDF → maschinenlesbares Markdown
   **und** Abbildungen schneiden — in einem Schritt:
   ```bash
   ./tools/prep.sh quellen/<Thema>/<name>.pdf        # oder: quellen/<Thema>/ (ganzer Ordner)
   ```
   `prep.sh` bündelt `extract.sh` (→ `.md` + `figindex.py` → `.figures.md`) und
   `figextract.sh` (→ `figures/<name>_S*.png` + `<name>.figures.json`). Ergebnis:
   `aufbereitet/<Thema>/<name>.md` (Seitenmarker `<!-- S. N -->`; gescannte Seiten
   per OCR erkannt und als `(OCR)` markiert). **Danach aus dem `.md` lesen** — das ist
   effizienter (greppbar, billiger, exakt zitierbar) als das PDF als Bild zu laden.
   Bei `(OCR)`-Seiten Zitate gegen das Original-PDF gegenprüfen. Seiten werden
   **parallel** verarbeitet (alle CPU-Kerne); Einzelschritte gehen weiter mit
   `./tools/extract.sh` (`-j N` begrenzt, `--lang` für andere OCR-Sprachen) bzw.
   `./tools/figextract.sh` (`--min-area`/`--zoom` justieren).
3. **Lies** das `.md` (Read-Tool); bei Bedarf gezielt Abschnitte/Seiten nachschlagen.
   **Bild-Check:** Das `.md` enthält **keine Bilder**, nur Captions. Schau in
   `<name>.figures.md` (bzw. die `· N Abb.`-Marker), wo Abbildungen liegen. Ist ein
   Konzept **räumlich-visuell** (Diagramm, Graph, Schema) oder trägt das Bild Info,
   die der Text nicht hergibt → **billig den geschnittenen Crop** unter
   `aufbereitet/<Thema>/figures/<name>_S<S.>_*.png` mit dem Read-Tool ansehen (statt
   die ganze PDF-Seite zu laden) und entscheiden, ob eine `occlusion`-/Bildkarte nötig
   ist. Fehlt ein Crop (Vektor nicht erkannt) → Original-PDF-Seite ansehen
   (`pages="<S.>"`). So wird kein Bild übersehen.
4. **Erstelle** die Karten (Skill `kartenbau` befolgen!) und schreibe sie als JSON
   nach `decks/<Thema>/<name>.cards.json` (Format unten).
5. **Baue** das Paket:
   ```bash
   ./tools/build.sh decks/<Thema>/<name>.cards.json
   ```
   → erzeugt `decks/<Thema>/<name>.apkg` (Ausgabe landet neben der `.cards.json`).
   (Image fehlt? `docker build -t anki-karten .`)

   **Mehrere Dateien in EINE .apkg** bündeln (jede Datei = eigenes Deck; `::` im
   Decknamen erzeugt Unterdecks) — z. B. ein ganzes Thema in eine Datei:
   ```bash
   ./tools/build.sh decks/Biologie/teil1.cards.json decks/Biologie/teil2.cards.json decks/Biologie/Biologie-komplett.apkg
   ```
6. Sag dem Nutzer, dass `decks/<Thema>/<name>.apkg` fertig ist
   → in Anki per **Datei → Importieren** oder Doppelklick laden.

## Bestehendes/gelerntes Deck ändern — OHNE Lernfortschritt zu verlieren

Wenn der Nutzer Karten **schon in Anki gelernt** (oder dort bearbeitet) hat und du sie
trotzdem ändern sollst: Lernfortschritt (Scheduling/Reviews) hängt an der Notiz-**GUID**.
Die `.cards.json` im Repo ist dann veraltet — **nicht** daraus neu bauen. Stattdessen:

1. Nutzer in Anki exportieren lassen: **Datei → Exportieren → `.apkg`** (mit Scheduling),
   gewünschtes Deck.
2. **Zurück nach `cards.json`** (GUIDs werden übernommen):
   ```bash
   python3 tools/apkg_to_cards.py <export>.apkg -o decks/<Thema>/<name>_rebuild
   ```
   Erkennt modernes (zstd) und Legacy-Format; je Deck eine `cards.json`. Läuft auf dem
   Host (stdlib + zstd), **kein Docker**.
3. Die `cards.json` editieren (Struktur/HTML — Skill `kartenbau`). **Cloze:** dieselben
   `{{cN::…}}` (Nummer + Antwort) **byte-identisch** lassen → Karten-Ord = cN−1 bleibt,
   Scheduling passt weiter. Tokens am besten programmatisch aus dem Original übernehmen
   und nur das Drumherum (Tabelle/Liste) neu setzen, dann verifizieren, dass die
   Token-Menge gleich ist. **Die ausgelesenen Felder enthalten die „Vertiefung & Quelle"-
   Box schon eingebacken** → nicht zusätzlich `explanation`/`source` setzen (Doppel-Box).
4. **Neu bauen** (GUIDs ⇒ Fortschritt bleibt): `./tools/build.sh decks/<Thema>/<name>_rebuild/*.cards.json "<Titel> (umstrukturiert).apkg"`.
5. **Prüfen:** Bau-GUIDs == Export-GUIDs (Menge identisch), Kartenzahl unverändert,
   `validate.sh` (0 Fehler). Bei CSS-/Struktur-Änderungen zusätzlich `preview.sh`.
6. Nutzer importiert: **„Notizen aktualisieren"**, Scheduling **nicht** zurücksetzen.
   Reine **CSS-Änderungen** (Notiztyp-Styling) aktualisiert der Import oft nicht →
   alternativ die CSS einmal in *Notiztypen verwalten → Karten → Styling* einfügen
   (kein Re-Import nötig, Inhalt/Fortschritt unberührt).

## Feedbackloop: Karten vor dem Export selbst prüfen

Bevor du eine `.apkg` als „fertig" meldest — besonders bei **Image-Occlusion**, wo
die Boxen per Auge platziert sind — prüfe das Ergebnis:

1. **Inhalt schnell linten** (reines Python, kein Docker nötig):
   ```bash
   python3 tools/lint_cards.py decks/<name>.cards.json
   ```
   Meldet leere Felder, fehlende Lücken, Occlusion-Koordinaten außerhalb 0..1,
   doppelte Fragen usw.
1b. **Grounding prüfen** (Anti-Halluzination, reines Python): stehen die Antworten
   wirklich im Quelltext, stimmen zitierte Seiten?
   ```bash
   python3 tools/grounding_check.py decks/<Thema>/<name>.cards.json
   ```
   FEHLER = Antwort kaum im Quelltext (evtl. erfunden); Warnung = nur teils gedeckt
   (z. B. fremdsprachiger Term) → gegen die Quelle prüfen. Heuristik: Warnungen sind
   ein „nachsehen", kein Beweis. Quelle wird automatisch aus dem Dateinamen abgeleitet
   (sonst `--source <md|ordner>`).
1c. **Abdeckung & Dubletten** über ein ganzes Thema (wenn mehrere `cards.json`):
   ```bash
   python3 tools/coverage.py decks/<Thema>/
   ```
   Zeigt Beinah-Dubletten über Dateigrenzen (was `lint_cards.py` nicht sieht) und —
   sofern Karten `source: "… S. N"` tragen — welche Quellseiten noch keine Karte haben.
2. **Darstellung rendern** (headless Chromium, gleiches HTML wie im .apkg):
   ```bash
   ./tools/preview.sh decks/<name>.cards.json          # Default: hell UND Nachtmodus
   ./tools/preview.sh decks/<name>.cards.json --theme light   # nur hell (schneller)
   ```
   → `decks/preview/<name>/NN-<typ>-front.png` + `-back.png` (hell) **und**
   `…-front-dark.png` + `…-back-dark.png` (Anki-Nachtmodus) + `index.html`.
3. **PNGs mit dem Read-Tool ansehen — hell UND dunkel.** Prüfe: Decken die
   Occlusion-Masken die richtigen Stellen? Zeigt die Rückseite das richtige Label?
   Layout ok? **Im Nachtmodus lesbar** (heller Text, Kontrast)? Der Nachtmodus deckt
   genau die Fehler auf, die im Hellmodus unsichtbar sind (harte Farben → dunkel auf
   dunkel) — deshalb standardmäßig beide.
4. Sitzt etwas daneben → Koordinaten/Texte in `decks/<name>.cards.json` anpassen,
   dann erneut **preview** (und am Ende **build**). Schleife, bis es passt.
5. **In der echten Anki-Engine validieren** (importiert + rendert jede Karte mit
   Ankis Backend, ohne GUI — stärker als die Vorschau-Emulation):
   ```bash
   ./tools/validate.sh decks/<name>.apkg
   ```
   Exit 0 = Import ok, keine Render-Fehler, keine leeren Karten. Bei Problemen
   meldet es Notiztyp + Karte.

**Abkürzung:** `./tools/finish.sh decks/<Thema>/<name>.cards.json` macht 1 + 1b +
Build + Validate in einem Rutsch (Lint ist ein Gate; Grounding nur Hinweis). Mehrere
`cards.json` (plus Ziel-`.apkg`, dann Pflicht) bündeln in EINE Datei und laufen
zusätzlich durch 1c (`coverage.py`):
`./tools/finish.sh decks/<Thema>/*.cards.json decks/<Thema>/<Thema>-komplett.apkg`. Bei
Occlusion-Karten zusätzlich `preview.sh` und die PNGs ansehen (Schritte 2–4).

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
- **Alle Textfelder werden als HTML gerendert** (kein Escaping): zum Strukturieren
  `<br>` (Umbruch — ein bloßes `\n` wirkt NICHT), `<ul>/<ol>`, `<table>` nutzen.
  Struktur erhöht die Lesbarkeit, nicht die Faktenzahl pro Karte (Atomarität bleibt).
- Optional `guid` pro Karte: stabile Anki-Notiz-GUID. Damit aktualisiert ein erneuter
  Import eine **bereits gelernte** Notiz statt sie zu duplizieren → **Lernfortschritt
  bleibt erhalten**. Nutzen, wenn man Inhalte aus einem Anki-Export neu aufbereitet
  (GUIDs aus dem Export übernehmen, Felder ändern). Ohne `guid`: genanki leitet sie
  wie gehabt aus den Feldern ab (geänderter Text ⇒ neue GUID ⇒ Fortschritt weg).

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
  wird automatisch ins `.apkg` eingebettet. **Folien-Abbildungen** haben keine eigene
  Datei → vorher `figextract.sh` laufen lassen und auf den geschnittenen Crop zeigen
  (`aufbereitet/<Thema>/figures/<name>_S<Seite>_<i>.png`).
- `mode`: `"hide-one"` (nur der gesuchte Bereich ist verdeckt, Rest sichtbar) oder
  `"hide-all"` (alle verdeckt, beim Aufdecken wird nur der gesuchte gezeigt).
- `regions`: Liste der Bereiche. **Koordinaten als Bruchteil 0..1** (relativ zur
  Bildgröße): `x`/`y` = obere linke Ecke, `w`/`h` = Breite/Höhe. `label` = die
  Antwort, die auf der Rückseite erscheint.

### So platziere ich (Claude) die Bereiche

**Bevorzugt: OCR (pixelgenau).** Bei Bildern mit Textbeschriftungen zuerst die
exakten Boxen erkennen lassen (bei Folien auf den `figextract`-Crop):
```bash
./tools/detect.sh aufbereitet/<Thema>/figures/<name>_S<Seite>_<i>.png   # oder quellen/bild.png
#                                                  optional: --lang deu+eng --min-conf 45
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
