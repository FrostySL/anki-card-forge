# Planung: Plattformübergreifende Einrichtung

- Stand: 5. September 2026
- Feature-Branch: `feature/cross-platform-setup`
- Status: Gesprächsergebnis und Vorschläge; das Feature ist noch nicht implementiert.

Diese Notiz hält den Kontext für die Weiterarbeit auf einem anderen Rechner fest.
Sie ergänzt [AGENTS.md](../AGENTS.md) und
[CONTRIBUTING.md](../CONTRIBUTING.md). Die bestehenden Anleitungen beschreiben
weiterhin die tatsächlich verfügbaren Werkzeuge. Die unten gezeigten neuen
Befehle sind ausschließlich Entwürfe.

## Vom Nutzer festgelegtes Ziel

Mehr Menschen sollen das Repository unter Windows, Linux und perspektivisch
macOS verwenden können, mit möglichst wenig manueller Einrichtung.
Die bisherige Entwicklungsumgebung nutzt Windows mit WSL/Ubuntu; der dokumentierte
Projektablauf ist vor allem auf Linux, Bash und Docker ausgerichtet.
Der nächste Schwerpunkt der besprochenen Erweiterung ist ein direkter
Windows-Ablauf.

Das bestehende Arbeitsmodell bleibt erhalten:

1. Nutzer laden oder klonen das Repository und öffnen es in ihrem bevorzugten
   KI-Werkzeug, etwa einem Assistenten in VS Code oder einem anderen Harness.
2. Der Assistent liest die Projektanweisungen und verwendet die bereitgestellten
   lokalen Werkzeuge zur Einrichtung und Verarbeitung der Quellen.
3. Der vom Nutzer gewählte Assistent schreibt die Karten als
   providerunabhängige `*.cards.json`.
4. Das Repository übernimmt Extraktion, Vorschau, Qualitätsprüfungen und den
   Bau der Anki-Pakete.

Das Repository führt weiterhin keine Modell-API-Aufrufe aus und verlangt keinen
zusätzlichen Modell-API-Key. Modellzugang und Nutzung bleiben beim gewählten
KI-Werkzeug. Die dafür bereits vorhandenen Konten oder Abonnements werden durch
dieses Feature nicht ersetzt.

Eine eigene Desktop-Oberfläche, ein gehosteter Dienst und eine integrierte
KI-Anbindung gehören nicht zu diesem Ziel. Der Nutzer möchte das Repository
weiterhin seiner vorhandenen KI als Werkzeugkasten geben.

## Besprochene technische Richtung

Die folgenden Punkte sind Architekturvorschläge, noch keine abschließend
geprüften Technologieentscheidungen:

- Eine gemeinsame Kommandozeile in Python koordiniert die vorhandenen Werkzeuge.
  Kleine Starter für die jeweiligen Betriebssysteme rufen dieselbe Ablauflogik
  auf. Setup-, Vorbereitungs- und Abschlusslogik sollen zentral gepflegt werden.
- Das Projekt prüft Voraussetzungen selbst und richtet fehlende Komponenten
  über einen wiederholbar ausführbaren, dokumentierten Ablauf ein. Der
  Assistent soll diesen Ablauf aufrufen können, ohne bei jedem Nutzer die
  Installation neu improvisieren zu müssen.
- Laufzeit und Abhängigkeiten sollen möglichst in einem vom Projekt verwalteten
  Verzeichnis liegen. Globale Installationen, Administratorrechte und Änderungen
  an der dauerhaften Systemkonfiguration sollen möglichst vermeidbar sein.
- Für Python und Python-Pakete wurde **uv** als Kandidat vorgeschlagen. Ein kleiner
  Starter könnte eine festgelegte uv-Version beziehen, die benötigte
  Python-Version bereitstellen und festgelegte Paketversionen installieren.
  `pyproject.toml` und ein Lockfile wären mögliche Bausteine dafür.
- OCR-Werkzeuge, Sprachdaten und Browserkomponenten müssen ebenfalls planbar
  bereitgestellt werden. Große Komponenten könnten beim ersten Bedarf geladen
  und anschließend wiederverwendet werden; ein vollständiges Setup muss alle
  für den gewünschten Ablauf notwendigen Prüfungen verfügbar machen.
- Ein nativer Ablauf mit geringer Einrichtungshürde ist das angestrebte Ziel.
  Docker wurde als optionaler Ausführungsweg für bestehende Nutzer, Entwicklung
  oder geeignete Sonderfälle diskutiert. Wie weit der vollständige Ablauf ohne
  Docker tragfähig ist, muss zuerst untersucht werden.
- Linux soll weiter funktionieren. macOS soll in der gemeinsamen Architektur
  berücksichtigt werden; konkrete Unterstützung folgt erst nach Prüfung und
  Tests auf den jeweiligen Plattformen.

## So könnte der Windows-Einstieg aussehen

Nutzer öffnen das Repository in einem normalen Windows-Verzeichnis mit einem
Assistenten, der Dateien lesen und schreiben sowie lokale Werkzeuge aufrufen
kann. Sie geben beispielsweise diesen Auftrag:

> Hier sind das Projekt und meine Unterlagen. Richte die benötigten Werkzeuge
> ein und erstelle die Karten nach den Projektanweisungen.

Ein zukünftiger Windows-Starter könnte so angesprochen werden:

```powershell
.\forge.cmd setup
.\forge.cmd prep sources\Biologie
.\forge.cmd finish decks\Biologie\kapitel.cards.json
```

`forge.cmd` und diese Befehle existieren in diesem Planungsstand noch nicht.
Die genaue Schnittstelle ist offen. Der Starter müsste auch auf einem System
ohne vorinstalliertes Python anlaufen können. Beim ersten Start würden die
benötigten Komponenten heruntergeladen; spätere Aufrufe würden sie wiederverwenden.
Eine selbst eingerichtete WSL-Umgebung oder eine vorherige Docker-Installation
sollte für diesen angestrebten Windows-Ablauf nicht nötig sein.

## Zuerst am Code zu prüfen

Die ursprüngliche Einschätzung beruhte auf der Projektanleitung und externer
Dokumentation. Eine systematische Prüfung der Portabilität der tatsächlichen
Implementierung und ein vollständiger nativer Windows-Test stehen noch aus.

| Bereich | Untersuchungsbedarf |
|---|---|
| Shell-Einstiegspunkte | Ablauflogik und Voraussetzungen von `setup.sh`, `prep.sh`, `finish.sh` sowie den einzelnen Werkzeug-Wrappern erfassen. |
| Python-Kern | Direkte native Ausführung, Paketversionen, Unterprozesse, Dateizugriffe und mögliche Linux-Annahmen prüfen. |
| PDF-Extraktion und OCR | Native Abhängigkeiten, Windows-Binärpakete, Sprachdaten und Installation ohne separate Nutzereinrichtung untersuchen. |
| Kartenbilder und Vorschau | Den bestehenden Chromium-Ablauf auf native Installation und Rendering in hellem und dunklem Design prüfen. Playwright wurde als möglicher Baustein genannt, nicht als bereits beschlossener Austausch. |
| Anki-Paketbau und Validierung | Verfügbarkeit kompatibler Windows-Pakete für den Builder, Kompression und das echte Anki-Backend nachweisen. Eine erfolgreiche Python-Installation allein genügt dafür nicht. |
| AnkiConnect | Direkten Zugriff aus Windows auf das dort laufende Anki prüfen; den bestehenden WSL/Windows-Sonderfall in der Dokumentation berücksichtigen. |
| Dateisystem | Laufwerksbuchstaben, Leerzeichen, Umlaute, temporäre Dateien, Dateisperren und zulässige Dateinamen prüfen. Anki-Decknamen mit `::` müssen von Dateinamen getrennt behandelt werden. |
| Setup und Git | Wiederholtes Setup, fehlgeschlagene Downloads, feste Versionen, Prüfsummen und Gitignore für lokale Laufzeiten und Caches berücksichtigen. |
| Plattformumfang | Unterstützte Windows-/macOS-Versionen, x64/ARM64 und verfügbare native Abhängigkeiten ausdrücklich festlegen. |

Die bestehende CI enthält laut Beitragsleitfaden bereits fokussierte
AnkiConnect-Tests unter Windows. Das belegt noch keine Unterstützung des
vollständigen Ablaufs auf Windows. Die weitere Prüfung soll auf vorhandenen
Tests aufbauen.

## Fachliche Anforderungen bleiben erhalten

- Die providerneutralen Autorenanweisungen, Workflows und das Kartenformat bleiben
  Grundlage für alle Assistenten.
- Lint, Grounding, gegebenenfalls Coverage, Vorschau und echte Anki-Validierung
  dürfen durch den neuen Einstiegspunkt nicht unbemerkt entfallen. Fehlende
  Prüfungen werden klar als solche ausgewiesen.
- Anki-GUIDs, Notiztypen und Cloze-Zuordnungen müssen bei Reworks erhalten bleiben.
- AnkiConnect bleibt optional und lokal. Vor Änderungen bleiben Backups aktiv;
  Entfernen von Karten und Sync erfolgen weiterhin nur auf ausdrücklichen
  Nutzerauftrag gemäß den Projektregeln.
- Persönliche Quellen, Extrakte, Karten, Pakete und Backups bleiben lokal und
  werden nicht veröffentlicht. Dasselbe gilt für heruntergeladene Laufzeiten
  und lokale Caches.

## Vorschlag für die nächsten Arbeitsschritte

1. Aktuelle Werkzeuge und Dockerfiles lesen und eine konkrete Liste der
   Abhängigkeiten sowie der Plattformannahmen erstellen.
2. An einem sauberen Windows-System die kritischen Komponenten untersuchen:
   Python-Einrichtung, OCR, Browser-Vorschau und echtes Anki-Backend. Erst daraus
   eine belastbare Entscheidung zu uv, Starter und nativer Ausführung ableiten.
3. Einen kleinen gemeinsamen Einstiegspunkt und ein wiederholbares Setup
   entwerfen. Die bestehenden Linux-Aufrufe während der Umstellung nutzbar halten.
4. Einen durchgängigen Ablauf mit öffentlichen, synthetischen Beispieldaten
   umsetzen und prüfen; danach die weiteren Quellen- und Rework-Fälle anbinden.
5. Projektanweisungen und Nutzeranleitung so aktualisieren, dass verschiedene
   Assistenten den Einstieg selbstständig finden und ausführen können.
6. Passende native Windows-Tests und Linux-Regressionsprüfungen ergänzen;
   macOS und weitere Architekturen nach dokumentierter Verifikation freigeben.

Ein sinnvolles Abnahmeszenario wäre ein frisches Windows-System mit dem
KI-Werkzeug des Nutzers: Repository herunterladen, Einrichtungsauftrag geben,
Text-PDF und Scan vorbereiten, Karten durch den Assistenten schreiben lassen,
Prüfungen und Vorschau ausführen, Anki-Paket bauen und mit dem echten Backend
validieren. Der zweite Durchlauf soll die eingerichtete Umgebung wiederverwenden.
Die genauen unterstützten Systemversionen und Voraussetzungen sind vorher
festzulegen; dies ist ein Zieltest, kein bereits bestandenes Ergebnis.

## Weiterarbeit auf diesem Branch

Dieser Stand dokumentiert ausschließlich die Besprechung. Die Implementierung
wird auf `feature/cross-platform-setup` fortgesetzt, sobald der nächste
Arbeitsauftrag dazu vorliegt. Der Branch enthält keine Kopie einer lokalen
WSL-Installation oder persönlicher Quelldateien; für praktische Tests ist auf
dem jeweiligen Rechner eine passende Umgebung nötig.

Einstieg für einen neuen Assistenten:

> Lies AGENTS.md, CONTRIBUTING.md und docs/cross-platform-setup.md. Wir wollen die
> Einrichtung insbesondere unter Windows vereinfachen und die freie Wahl des
> KI-Assistenten beibehalten. Prüfe zunächst die tatsächlichen Werkzeuge und
> Abhängigkeiten. Behandle die genannten technischen Lösungen als Vorschläge
> und behaupte keine Plattformunterstützung ohne passende Verifikation.

## Im Gespräch verwendete technische Referenzen

- [uv: Installation und fertige Binärdateien](https://docs.astral.sh/uv/getting-started/installation/)
- [uv: Automatische Python-Einrichtung](https://docs.astral.sh/uv/guides/install-python/)
- [uv: Projektstruktur und Umgebungen](https://docs.astral.sh/uv/concepts/projects/layout/)
- [Playwright für Python: Installation](https://playwright.dev/python/docs/intro)
- [Docker Desktop: unterstützte Plattformen](https://docs.docker.com/desktop/)
- [Docker: Einbindung von Host-Verzeichnissen](https://docs.docker.com/engine/storage/bind-mounts/)

Diese Referenzen stützen die diskutierten Möglichkeiten. Sie ersetzen keine
Prüfung der Abhängigkeiten und des vollständigen Projektablaufs auf Windows.
