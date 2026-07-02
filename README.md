# Anki-Karten

Aus **Skripten, Büchern und Texten** automatisch **Anki-Karteikarten** machen —
zusammen mit [Claude Code](https://claude.com/claude-code).

## Idee

Die KI ist Claude selbst: Du legst eine Datei in `quellen/<Thema>/`, sagst Claude
im Chat „mach Karten daraus", Claude liest die Datei, schreibt die Karten nach den
Regeln des `kartenbau`-Skills, und ein kleiner Docker-Container verpackt sie zu einer
fertigen `.apkg`-Datei für Anki. **Kein externer LLM-Aufruf, kein API-Key** — Docker
macht nur das stumpfe „Karten-JSON → `.apkg`" über die Bibliothek `genanki`.

```
quellen/<Thema>/skript.pdf  →  (Claude liest + erstellt Karten)  →  decks/<Thema>/skript.apkg  →  Import in Anki
```

## Voraussetzungen

- **[Claude Code](https://claude.com/claude-code)** (die KI, die die Karten schreibt)
- **Docker** (verpackt Karten zu `.apkg`, rendert Vorschauen, macht OCR)

Sonst nichts — alle Python-Abhängigkeiten leben in den Docker-Images.

## Benutzung

1. Quelle nach `quellen/<Thema>/` legen (PDF, Text, Markdown …) — pro Themengebiet
   ein Unterordner, z. B. `quellen/Biologie/`.
2. Claude im Chat bitten: **„Erstelle Anki-Karten aus quellen/Biologie/zellatmung.pdf."**
3. Claude erzeugt `decks/Biologie/zellatmung.apkg`.
4. In Anki über **Datei → Importieren** (oder Doppelklick) laden.

Claude bereitet Quellen bei Bedarf zuerst zu Markdown auf (inkl. OCR für gescannte
PDFs) und prüft die Karten vor dem Export selbst (Lint, PNG-Vorschau, echte
Anki-Engine). Die Methodik dafür steht in [CLAUDE.md](CLAUDE.md) und im
`kartenbau`-Skill.

## Einrichtung (einmalig)

```bash
docker build -t anki-karten .            # schlankes Builder-Image
git config core.hooksPath .githooks      # Commit-Guard aktivieren (s. u.)
```

Die größeren Images (Vorschau/OCR, Quellen-Aufbereitung) werden beim ersten Aufruf
der jeweiligen `tools/*.sh` automatisch gebaut.

Der **Commit-Guard** (`.githooks/pre-commit`) verhindert, dass persönliches
Material (Quellen-PDFs, Extrakte, eigene Decks) versehentlich in diesem
öffentlichen Repo landet — auch bei `git add -f`, wo die `.gitignore` nicht mehr
greift. Neue Dateien sind nur aus Werkzeug-/Doku-Pfaden erlaubt; bewusst umgehen:
`git commit --no-verify`.

## Kartentypen

- **basic** — Frage/Antwort (mit `reverse` auch beidseitig).
- **cloze** — Lückentext `{{c1::…}}`.
- **typein** — Antwort eintippen, Anki vergleicht (für exakte Schreibweisen).
- **occlusion** — Bild mit verdeckten Bereichen (Anatomie, Diagramme …).

Auf **jeder** Karte optional eine zugeklappte Box „Vertiefung & Quelle"
(`explanation` + `source`). Details zum Karten-JSON-Format: [CLAUDE.md](CLAUDE.md).

## Werkzeuge

| Tool | Zweck |
|---|---|
| `tools/prep.sh` | Quelle aufbereiten in einem Schritt: `extract` + Abbildungs-Index + `figextract` |
| `tools/extract.sh` | PDF → Markdown (parallele OCR für Scans; inkl. Abbildungs-Index via `figindex.py`) |
| `tools/figextract.sh` | Abbildungen aus dem PDF schneiden → PNG-Crops + Manifest |
| `tools/detect.sh` | OCR (Tesseract): Label-Boxen für Image Occlusion erkennen |
| `tools/lint_cards.py` | schnelle Inhalts-/Struktur-Prüfung (reines Python, ohne Docker) |
| `tools/grounding_check.py` | Anti-Halluzination: stehen die Antworten wirklich im Quelltext? |
| `tools/coverage.py` | Beinah-Dubletten + Quellseiten-Abdeckung über ein ganzes Thema |
| `tools/build.sh` | Karten-JSON → `.apkg` (genanki); bündelt auch mehrere JSONs in eine Datei |
| `tools/preview.sh` | Karten → PNG-Vorschau hell + Nachtmodus (headless Chromium, Feedbackloop) |
| `tools/validate.sh` | `.apkg` in echter Anki-Engine prüfen (Import + Render) |
| `tools/finish.sh` | Abkürzung: Lint + Grounding (+ Coverage) + Build + Validate in einem |
| `tools/apkg_to_cards.py` | `.apkg` → `cards.json` zurück, GUIDs bleiben (gelernte Decks ändern ohne Fortschrittsverlust) |
| `tools/test.sh` | Testsuite der Logik-Tools (stdlib-`unittest`, ohne Docker/pip) |

## Ordnerstruktur

```
quellen/<Thema>/          deine Quelldateien (lokal, nicht versioniert)
aufbereitet/<Thema>/      Markdown-Extrakte der Quellen (lokal, via extract.sh)
decks/<Thema>/            erzeugte .cards.json + .apkg (lokal; nur Beispiel im Repo)
tools/                    Aufbereitung, Bau, Prüfung — siehe Werkzeug-Tabelle oben
.claude/skills/kartenbau/ evidenzbasierte Methodik fürs Kartenschreiben
reference/                lokale Anki-Nachschlagewerke (nicht im Repo, s. reference/README.md)
CLAUDE.md                 Anleitung + Karten-Format für Claude
```

Deine Quellen, Extrakte und erzeugten Decks bleiben **lokal** (per `.gitignore`) —
das Repo enthält nur die Werkzeuge und ein Beispiel-Deck.

## Unterstützen

Das Projekt ist kostenlos und Open Source. Wenn es dir hilft und du gerade gut
drauf bist, freue ich mich über ein Trinkgeld über den **Sponsor-Button** oben am
Repo (eingerichtet in [.github/FUNDING.yml](.github/FUNDING.yml)). Kein Muss —
Sternchen ⭐ und Feedback helfen genauso.

## Lizenz

[MIT](LICENSE). Dieses Projekt enthält **keinen** Anki-Quellcode; es erzeugt
`.apkg`-Dateien über [`genanki`](https://github.com/kerrickstaley/genanki) (MIT).
Anki selbst steht unter der AGPL-3.0 und ist hier nicht enthalten.
