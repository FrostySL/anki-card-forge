# reference/ — lokale Nachschlagewerke (nicht im Repo)

Dieser Ordner dient Claude als **Nachschlagewerk** zu Anki. Der Inhalt ist
**fremder Code mit eigener Lizenz** und wird daher **nicht** mitversioniert
(siehe `.gitignore`) — nur diese Hinweisdatei.

Wer die Nachschlagewerke lokal haben möchte (optional, nur als Referenz; für die
Kartenerzeugung selbst nicht nötig):

```bash
# Anki-Quellcode (AGPL-3.0) — flacher Klon reicht
git clone --depth 1 https://github.com/ankitects/anki reference/anki

# Anki-Handbuch
git clone --depth 1 https://github.com/ankitects/anki-manual reference/anki-manual
```

> **Lizenz-Hinweis:** Anki steht unter der **GNU AGPL-3.0**. Dieses Projekt
> verwendet **keinen** Anki-Quellcode — es erzeugt `.apkg`-Dateien ausschließlich
> über die Bibliothek [`genanki`](https://github.com/kerrickstaley/genanki) (MIT).
> Die Inhalte unter `reference/` sind reines lokales Nachschlagematerial.
