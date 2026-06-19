# Anki-Karten

Aus **Skripten, Büchern und Texten** automatisch **Anki-Karteikarten** machen —
zusammen mit Claude Code.

## Idee

Die KI ist Claude selbst: Du legst eine Datei in `quellen/`, sagst Claude im Chat
„mach Karten daraus", Claude liest die Datei, schreibt die Karten und ein kleiner
Docker-Container verpackt sie zu einer fertigen `.apkg`-Datei für Anki.

```
quellen/skript.pdf  →  (Claude liest + erstellt Karten)  →  decks/skript.apkg  →  Import in Anki
```

## Benutzung

1. Datei in `quellen/` legen (PDF, Text, Markdown …).
2. Claude im Chat bitten: **„Erstelle Anki-Karten aus quellen/skript.pdf."**
3. Claude erzeugt `decks/skript.apkg`.
4. In Anki über **Datei → Importieren** (oder Doppelklick) laden.

## Einrichtung (einmalig)

Es muss nur **Docker** installiert sein. Image bauen:

```bash
docker build -t anki-karten .
```

Danach baut `tools/build.sh` aus einer Karten-JSON die `.apkg`:

```bash
./tools/build.sh decks/skript.cards.json
```

Optionaler **Vorschau-/Feedbackloop** (rendert die Karten als PNG, damit man –
v. a. bei Image Occlusion – sieht, ob alles sitzt). Das größere Vorschau-Image
wird beim ersten Aufruf automatisch gebaut:

```bash
./tools/preview.sh decks/skript.cards.json   # -> decks/preview/skript/*.png
```

## Ordnerstruktur

```
quellen/                 deine Quelldateien
decks/                   erzeugte .cards.json + .apkg
tools/build_deck.py      JSON → .apkg (genanki)
tools/build.sh           Docker-Wrapper
tools/preview.py/.sh     Karten → PNG-Vorschau (headless Chromium, Feedbackloop)
tools/lint_cards.py      schnelle Inhalts-/Struktur-Prüfung
reference/anki-manual/   offizielles Anki-Handbuch (Nachschlagewerk)
reference/anki/          Anki-Quellcode (shallow clone, Nachschlagewerk)
CLAUDE.md                Anleitung für Claude
```

Details zum Karten-Format und zu den Qualitätsregeln stehen in [CLAUDE.md](CLAUDE.md).
