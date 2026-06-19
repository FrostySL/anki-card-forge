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
docker build -t anki-karten .          # schlankes Builder-Image
```

Die größeren Images (Vorschau/OCR, Quellen-Aufbereitung) werden beim ersten Aufruf
der jeweiligen `tools/*.sh` automatisch gebaut.

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
| `tools/build.sh` | Karten-JSON → `.apkg` (genanki) |
| `tools/extract.sh` | PDF → Markdown (parallele OCR für Scans) |
| `tools/preview.sh` | Karten → PNG-Vorschau (headless Chromium, Feedbackloop) |
| `tools/detect.sh` | OCR (Tesseract): Label-Boxen für Image Occlusion erkennen |
| `tools/lint_cards.py` | schnelle Inhalts-/Struktur-Prüfung |
| `tools/validate.sh` | `.apkg` in echter Anki-Engine prüfen (Import + Render) |

## Ordnerstruktur

```
quellen/<Thema>/          deine Quelldateien (lokal, nicht versioniert)
aufbereitet/<Thema>/      Markdown-Extrakte der Quellen (lokal, via extract.sh)
decks/<Thema>/            erzeugte .cards.json + .apkg (lokal; nur Beispiel im Repo)
tools/                    build / extract / preview / detect / lint / validate
.claude/skills/kartenbau/ evidenzbasierte Methodik fürs Kartenschreiben
reference/                lokale Anki-Nachschlagewerke (nicht im Repo, s. reference/README.md)
CLAUDE.md                 Anleitung + Karten-Format für Claude
```

Deine Quellen, Extrakte und erzeugten Decks bleiben **lokal** (per `.gitignore`) —
das Repo enthält nur die Werkzeuge und ein Beispiel-Deck.

## Lizenz

[MIT](LICENSE). Dieses Projekt enthält **keinen** Anki-Quellcode; es erzeugt
`.apkg`-Dateien über [`genanki`](https://github.com/kerrickstaley/genanki) (MIT).
Anki selbst steht unter der AGPL-3.0 und ist hier nicht enthalten.
