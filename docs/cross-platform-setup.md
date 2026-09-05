# Native Windows-Einrichtung und Plattformtests

Die gemeinsame Befehlssteuerung unterstützt **Windows 11 x64 nativ** und den
bestehenden **Linux-/Docker-Ablauf**. Native Linux-Einrichtung, macOS und Windows
ARM64 sind nicht Teil dieser Umsetzung. Der Karteninhalt entsteht weiterhin
im frei gewählten KI-Assistenten; das Repository ruft keine Modell-API auf.

## Windows verwenden

Das Repository klonen oder das GitHub-ZIP in einen beschreibbaren Ordner
entpacken. Ein normaler Benutzer kann anschließend in PowerShell starten:

```powershell
.\forge.cmd setup
.\forge.cmd doctor
.\forge.cmd prep sources\Biologie
.\forge.cmd preview decks\Biologie\kapitel.cards.json
.\forge.cmd finish decks\Biologie\kapitel.cards.json
.\forge.cmd anki ping
```

Python, Docker, Git und WSL müssen dafür nicht vorinstalliert sein. Setup lädt
beim ersten Lauf die benötigten Komponenten herunter und prüft deren Funktion.
Bei einer ZIP-Kopie wird die Einrichtung des Git-Hooks übersprungen. Bei einem
Git-Checkout aktiviert Setup den Commit-Guard, sofern Git verfügbar ist.

`doctor` prüft nur und lädt nichts herunter. Ein wiederholtes `setup` verwendet
intakte Komponenten erneut und repariert beschädigte oder fehlende Bestandteile.
`setup --offline` verwendet ausschließlich vorhandene Dateien und Caches; bei
einem fehlenden Bestandteil nennt es den Fehler. Erfolg wird erst nach den
Funktionsprüfungen gemeldet.

Deutsch und Englisch sind standardmäßig eingerichtet. Weitere OCR-Sprachen
kommen aus demselben festgelegten tessdata-Datenstand:

```powershell
.\forge.cmd setup --lang fra
.\forge.cmd prep sources\Französisch --lang fra -j 2
```

Pfade mit Leerzeichen werden in Anführungszeichen gesetzt. Eingabe-Wildcards
und Aufrufe aus Unterverzeichnissen sind möglich; Argumentpfade beziehen sich
auf das aktuelle Verzeichnis. Medienpfade **in Karten-JSON** beziehen sich
immer auf das Projekt und verwenden `/`. Für lange Dokumentnamen einen kurzen
Projektpfad wählen, damit Windows-Pfadlängengrenzen nicht erreicht werden.

## Lokale Komponenten und Integrität

| Ort | Inhalt |
|---|---|
| `.forge/` | uv, CPython, OCR, Sprachdaten, Chromium, MathJax, Download- und Paket-Caches |
| `.venv/` | Projektumgebung mit den festgelegten Python-Paketen |
| `tools/runtime-manifest.json` | Versionen, Originalquellen, Lizenzen und Downloadprüfsummen |
| `pyproject.toml`, `uv.lock` | Direkte und transitive Python-Abhängigkeiten |

Beide lokalen Verzeichnisse sind gitignored und durch den Commit-Guard geschützt.
Das Setup ändert weder Systemverzeichnisse noch den dauerhaften PATH. Nach einem
Umzug auf einen anderen Rechner sollte die Umgebung dort neu eingerichtet werden.

Festgelegt sind uv **0.12.10**, CPython **3.12.14 / Build 20260901**, Tesseract
**5.5.3.20260724**, 7-Zip **26.03**, MathJax **3.2.2** und zstandard **0.25.0**.
Die direkten Fachbibliotheken entsprechen den bisherigen Docker-Pins.
Die Sprachdaten stammen aus `tessdata_fast` bei Commit
`87416418657359cb625c412a48b6e1d6d41c29bd`.

Downloads werden vor der Verwendung geprüft und zunächst temporär gespeichert.
7zr entpackt das festgelegte 7-Zip-Paket; der vollständige Entpacker öffnet das
Tesseract-Paket. **Die Installer werden nicht ausgeführt.** Unterstützende DLLs,
Konfigurationen und Lizenzdateien bleiben erhalten. Die Release-DLLs aus dem
Microsoft-CRT-Archiv **14.44.35211** liegen direkt neben den verwalteten
Python-Executables. Debug-Runtimes und globale Installationen werden nicht verwendet.

Playwright verwaltet seine passende Chromium-Version im Projekt. Die komplette
MathJax-`es5`-Struktur wird lokal bereitgestellt, einschließlich dynamisch geladener
TeX-Erweiterungen. Vorschauen fangen die MathJax-Ressourcenanfragen ab und liefern
die Dateien lokal aus. Sie warten auf gerenderte SVG-Mathematik und brechen bei
fehlenden Komponenten oder Renderfehlern ab. Docker erhält dieselben Formelassets.
`preview --offline` weist zusätzlich externe Ressourcen wie Webbilder zurück.
Nach erfolgreicher Einrichtung benötigt die Verarbeitung lokaler Quellen und
Medien kein Internet; der gewählte KI-Assistent hat eigene Voraussetzungen.

## Gemeinsame Befehle

Neben `setup`, `doctor`, `prep` und `finish` stehen `extract`, `figextract`,
`figindex`, `detect`, `lint`, `grounding`, `coverage`, `build`, `preview`,
`validate`, `decode`, `diff`, `anki` und `test` zur Verfügung.

Die Steuerung startet die vorhandenen Python-Werkzeuge mit dem festgelegten
Interpreter und expliziten Argumentlisten. `prep` verbindet Extraktion,
Textspiegelung, Figurenindex und PDF-Figurenextraktion. `finish` führt Lint,
Grounding, bei mehreren Dateien Coverage, Build und echte Anki-Validierung aus.
Grounding und Coverage bleiben Hinweise. Lint- und Validierungsfehler stoppen
vor einem möglichen Import. `--push` importiert mit den bestehenden Backups;
`--prune` und `--sync` bleiben ausdrücklich beauftragte Aktionen.

Unter Linux bleiben `tools/setup.sh` und die einzelnen Docker-Wrapper verfügbar.
`prep.sh` und `finish.sh` rufen dieselbe Python-Steuerung mit Docker als Backend
auf. Die Anki-Notiztypen, GUIDs und Cloze-Zuordnungen bleiben kompatibel.

## Abnahme und bekannte Grenzen

Die [Integrationsanleitung](../tests/integration/README.md) beschreibt den
synthetischen Test mit acht Notizen, zehn Karten und 40 hellen/dunklen Vorschauen,
PDF-/Scan-/OCR-Tests, vollständigem `finish`, Offline-Formeln und Fehlerfällen.
Der Windows-CI-Job beginnt mit einem sauberen Quellarchiv ohne Projekt-Caches
und ohne vorab eingerichtetes Python; er prüft die tatsächlich geladenen Werkzeuge.
Sein Ergebnis fließt in den erforderlichen Gesamtcheck `CI passed` ein.

Für die zusätzliche Abnahme in Windows Sandbox wird der konkrete Commit als
Archiv bereitgestellt. Projekt und Laufzeiten befinden sich im Gast. Nur das
Eingabearchiv und ein begrenzter Diagnoseordner werden freigegeben. Der eigentliche
Setup-Prozess läuft als Standardbenutzer. Die Aktivierung von Windows Sandbox
und ein möglicher Neustart müssen am Host separat abgestimmt werden.

Ein echter Anki-Test verwendet einen eindeutig benannten synthetischen Stapel
im Profil `test`, lernt Karten und prüft Export → Decode → Änderung → Rebuild →
Import mit Backup. GUIDs, Notiztypen, Karten-IDs, Cloze-Zuordnungen, Lernstand und
Review-Historie werden verglichen; es erfolgt kein Sync. Die Rückkonvertierung
überspringt derzeit Image-Occlusion-Notizen. Der Rework-Test verwendet deshalb
nur rückkonvertierbare Typen; Occlusion wird separat gebaut und dargestellt.

Ein erfolgreicher lokaler Lauf auf einem eingerichteten Entwicklungsrechner
ersetzt die Sandbox-Abnahme nicht. Tatsächlich ausgeführte Prüfungen und noch
offene Abnahmeschritte werden im Pull Request und im Abnahmebericht ausgewiesen.
Der aktuelle Stand steht im [Windows-Abnahmebericht](windows-acceptance.md).
