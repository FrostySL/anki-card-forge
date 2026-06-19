# Evidenzbasierte Prinzipien der Karteikarten-Gestaltung, -Formulierung und -Formatwahl für Anki / Spaced Repetition

*Ein wissenschaftlich belegter Leitfaden für das automatische und manuelle Erstellen einzelner Lernkarten. Schwerpunkt: Gestaltung, Formulierung und Formatwahl EINZELNER Karten — nicht das Scheduling (SM-2/FSRS, Intervalle, Ease, Tageslimits), das Anki selbst übernimmt.*

---

## TL;DR
- **Die mit Abstand am besten belegte Regel lautet: Jede Karte muss aktiven ABRUF EINER atomaren Information aus dem Gedächtnis erzwingen — mit eindeutigem Cue und eindeutiger, produzierbarer Antwort.** Das ist die direkte Anwendung des „Testing/Retrieval-Effekts", der zu den am robustesten replizierten Befunden der Lernpsychologie gehört: Roediger & Karpicke (2006) fanden nach einer Woche 61 % Behalten in der Test-Gruppe vs. 40 % in der Wiederlese-Gruppe, obwohl letztere den Text 14,2-mal statt 3,4-mal gelesen hatte; Dunlosky et al. (2013) bewerteten „practice testing" als eine von nur **zwei** der zehn untersuchten Lerntechniken mit „high utility".
- **Die Formulierung ist wichtiger als der Kartentyp.** Wähle das Format nach Wissenstyp: Basic Q/A als Default für Konzepte und „Warum/Wie"; Cloze für eingebettete Einzelfakten und aufgelöste Aufzählungen; Image Occlusion für räumlich-visuelle Zuordnung; type-in nur bei exakter Schreibung/Syntax; bidirektionale Karten nur bei echter Zwei-Wege-Nutzung.
- **Tiefere Erklärung („Warum"/Zusammenhang) und Quelle gehören auf die Rückseite — aber getrennt vom Abrufmoment**, z. B. in einer standardmäßig zugeklappten HTML-Box, die erst NACH dem Antworten geöffnet wird. Feedback nach Abruf ist belegt wirksam (Butler, Karpicke & Roediger), darf aber die gewünschte Abrufschwierigkeit und die Atomarität der Kernkarte nicht untergraben.

---

## Key Findings (Kurzüberblick)

1. **Retrieval Practice ist die Wirkmechanik jeder Karte.** Eine Karte „funktioniert" nur, wenn sie tatsächlichen Abruf erzwingt — nicht bloßes Wiedererkennen oder Wiederlesen.
2. **Atomarität (Minimum Information Principle)** ist doppelt begründet: lernpsychologisch (Retrieval-Effort, Interferenz) und praktisch (gleichmäßiges Scheduling).
3. **Wozniaks „20 Regeln"** sind ein exzellenter Praxis-Leitfaden, aber überwiegend Erfahrungswissen (1999, iterativ aktualisiert), kein RCT-Ergebnis — ihre Kernideen decken sich jedoch weitgehend mit kontrollierten Befunden.
4. **Image Occlusion hat KEINE direkte kontrollierte Studienevidenz.** Die Wirksamkeit wird aus aktivem Abruf, dem Picture-Superiority-Effekt und Dual Coding extrapoliert — das ist plausibel, aber als „belegt" überzeichnet.
5. **Bei KI-generierten Karten** sind die Hauptrisiken Halluzinationen sowie — häufiger und tückischer — strukturelle Defekte: zu lange „Absatz-Karten", Mehrdeutigkeit, fehlende Atomarität, Redundanz. Ein hoher Defektanteil degradiert das Deck „langsam und unsichtbar".

---

## Details

### 1. Grundprinzipien: Atomarität, Eindeutigkeit, eine Tatsache pro Karte

**Minimum Information Principle / Atomarität.** Piotr Wozniak (1999, „Effective learning: Twenty rules of formulating knowledge", SuperMemo) formuliert als Regel 4: *„The material you learn must be formulated in as simple way as it is [possible]."* Begründung im Original: Einfaches Material wird vom Gehirn „immer auf dieselbe Weise" verarbeitet (stabilere Gedächtnisspur), und einfache Items lassen sich getrennt nach ihrer individuellen Schwierigkeit terminieren. Michael Nielsen („Augmenting Long-term Memory", 2018) und Andy Matuschak („How to write good prompts", 2020) übernehmen dies: Prompts sollen **focused, precise, consistent, tractable und effortful** sein.

Empirisch wird Atomarität *indirekt* gestützt durch (a) das Retrieval-Effort-Prinzip (Pyc & Rawson 2009) — eine Mehr-Fakten-Karte erlaubt unvollständigen Abruf, bei dem Teile der Zielinformation „dunkel bleiben" —, und (b) Interferenz (komplexe Items lassen sich nicht gleichmäßig stärken). Wichtig für die KI-Anwendung: Das Prinzip selbst ist primär Theorie/Erfahrungswissen, aber kongruent mit den kontrollierten Effekten.

> **Schlecht (nicht atomar):**
> *F: Was sind die Eigenschaften von TCP?*
> *A: verbindungsorientiert, zuverlässig, geordnete Zustellung, Flusskontrolle, Staukontrolle, Vollduplex.*
> (Problem: Bei „2 von 6 vergessen" markiert man trotzdem leicht „richtig" → der vergessene Fakt wird nie korrigiert.)
>
> **Gut (atomar, aufgeteilt):**
> *F: Welcher TCP-Mechanismus verhindert, dass ein schneller Sender einen langsamen EMPFÄNGER überflutet?*
> *A: Flusskontrolle (sliding window).*
> + separate Karte: *F: Welcher TCP-Mechanismus reagiert auf Überlast im NETZ (nicht beim Empfänger)?*
> *A: Staukontrolle (congestion control).*

### 2. Lernpsychologische Basis — je Prinzip mit konkreter Konsequenz für die Karte

**Retrieval Practice / Testing Effect.** Roediger, H. L. & Karpicke, J. D. (2006). „Test-enhanced learning: Taking memory tests improves long-term retention." *Psychological Science* 17(3):249–255. In Experiment 1 behielt die Test-Gruppe nach 2 Tagen 68 % vs. 54 % (Restudy) und nach 1 Woche 56 % vs. 42 %. Noch deutlicher Experiment 2 (Originalzitat): *„students in the repeated-testing condition recalled much more after a week than did students in the repeated-study condition (61 % vs. 40 %), even though students in the former condition read the passage only 3.4 times and those in the latter condition read it 14.2 times."* Bemerkenswert: Die Wiederlese-Gruppe war *subjektiv* überzeugter, mehr zu behalten („illusion of competence").
→ **Konsequenz:** Jede Karte muss eine echte Abruffrage sein, kein Lese- oder Wiedererkennungs-Item.

**Retrieval schlägt Elaboration.** Karpicke, J. D. & Blunt, J. R. (2011). „Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping." *Science* 331(6018):772–775. Auf dem Kurzantwort-Test nach 1 Woche recallte die Retrieval-Gruppe 0,67 der idea units vs. 0,45 bei Concept Mapping (F(1,38)=21,63) — und zwar auch bei Verständnis- und Inferenzfragen. Originalabstract: *„practicing retrieval produces greater gains in meaningful learning than elaborative studying with concept mapping … The advantage of retrieval practice was observed with test questions that assessed comprehension and required students to make inferences."* (Auch hier schätzten die Studierenden Concept Mapping subjektiv als effektiver ein.)
→ **Konsequenz:** Abruf erzwingen ist wertvoller als das bloße Präsentieren elaborierter Erklärungen. Die Kernkarte testet; die Erklärung ist Beiwerk auf der Rückseite (siehe Abschnitt 5).

**Generation Effect.** Slamecka, N. J. & Graf, P. (1978). „The Generation Effect: Delineation of a Phenomenon." *Journal of Experimental Psychology: Human Learning and Memory* 4(6):592–604. In fünf Experimenten war die „generate"-Bedingung der „read"-Bedingung durchweg überlegen (cued/uncued recognition, free/cued recall, Konfidenz).
→ **Konsequenz:** Die Karte muss Produktion verlangen (Antwort selbst erzeugen), nicht Wiedererkennen aus Optionen.

**Elaborative Interrogation & Self-Explanation.** Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. & Willingham, D. T. (2013). „Improving Students' Learning With Effective Learning Techniques." *Psychological Science in the Public Interest* 14(1):4–58. Beide Techniken wurden als **„moderate utility"** eingestuft (höher als Highlighting/Summarizing/Rereading = „low", aber unter practice testing/distributed practice = „high"). Wirksamkeit von elaborative interrogation hängt von Vorwissen ab; Effektstärken in der Literatur reichen von 0,85 bis 2,57, die Anwendbarkeit ist aber oft auf diskrete Faktenaussagen begrenzt.
→ **Konsequenz:** „Warum/Wieso"-Karten sind eine sinnvolle Ergänzung zu Faktenkarten; die generierte Erklärung auf der Rückseite verankern.

**Encoding Specificity.** Tulving, E. & Thomson, D. M. (1973). „Encoding specificity and retrieval processes in episodic memory." *Psychological Review* 80(5):352–373. Ein Retrieval-Cue ist nur wirksam, soweit er mit dem Enkodierkontext überlappt; bei „Cue Overload" (ein Cue zeigt auf zu viele Ziele) versagt der Abruf.
→ **Konsequenz:** Der Cue auf der Vorderseite muss die Zielinformation **eindeutig und distinkt** ansteuern. Vage Frage („Was ist wichtig an X?") = vager Abruf.

**Desirable Difficulties.** Bjork, R. A. (1994); Bjork, E. L. & Bjork, R. A. (2011), „Making Things Hard on Yourself, But in a Good Way." Bedingungen, die das Lernen kurzfristig erschweren (aber erfolgreich bleiben) — verteiltes Üben, Interleaving, Abrufübung, Generierung — verbessern Langzeitbehalten und Transfer. Zugrunde liegt die Unterscheidung *storage strength* vs. *retrieval strength*: Der Abruf bei mittlerer Vergessenheit erzeugt den größten Zuwachs.
→ **Konsequenz:** Karten sollen den Abruf nicht „verschenken" (keine Hint-Leaks), aber tractable bleiben — Faustregel ca. 90 % Erfolgsquote; zu schwere Karten aufteilen oder Cue ergänzen.

**Retrieval-Effort-Hypothese.** Pyc, M. A. & Rawson, K. A. (2009). „Testing the retrieval effort hypothesis." *Journal of Memory and Language* 60(4):437–447. Befund: *„as the difficulty of retrieval during practice increased, final test performance increased"* (bei erfolgreichem Abruf). Ergänzend: Pyc & Rawson (2010), „Why testing improves memory: Mediator effectiveness hypothesis", *Science* 330:335 — Test-Restudy erzeugt wirksamere „Mediatoren" (Cue→Ziel-Verknüpfungen).
→ **Konsequenz:** Hinweise sparsam dosieren — gerade so viel, dass der Abruf gelingt, aber nicht trivial wird.

**Dual Coding.** Paivio, A. (1971/1986); Paivio, A. & Csapo, K. (1973), „Picture superiority in free recall: Imagery or dual coding?", *Cognitive Psychology* 5(2):176–206. Bilder werden doppelt kodiert (bildlich + verbal), Wörter nur einfach → bessere Behaltensleistung für bildhaftes Material.
→ **Konsequenz:** Relevante Diagramme/Bilder ergänzen den Text, **nicht** dekorativ. (Caveat siehe Abschnitt 9.)

### 3. Frageformulierung

Belegt durch Encoding Specificity (eindeutiger Cue), Generation Effect (Produktion) und Retrieval Practice (echter Abruf). Matuschak (2020) operationalisiert: Prompts sollen *unambiguously produce a specific answer* und *make clear what „shape" of answer they expect*.

- **Aktive Abrufbarkeit** statt Wiedererkennung; **keine Ja/Nein-Fragen** (50 % ratbar, kein Generieren).
- **Eindeutige Antwort** (genau eine korrekte „Form").
- **Präziser Cue**, der nicht die Antwort verrät (kein Hint-Leak).
- **Kein Auswendiglernen ganzer Sätze** — die spezifische Information isolieren.

> **Schlecht:** *F: Ist HTTP zustandslos? — A: Ja.* (Ja/Nein, ratbar, kein Generieren)
> **Gut:** *F: Welche fundamentale Eigenschaft von HTTP bedeutet, dass der Server zwischen zwei Requests keine Client-Information speichert? — A: Zustandslosigkeit (statelessness).*

### 4. Formatwahl — wann welcher Kartentyp?

| Format | Wann verwenden (Entscheidungsregel) | Best Practices | Evidenzlage |
|---|---|---|---|
| **Basic (Q/A)** | Default. Konzepte, Definitionen, „Warum/Wie", Verständnis, Inferenz. | Eine Frage = ein Abrufziel. Antwort so kurz wie möglich. Erklärung in zugeklappte Box. | Direkt belegt (Retrieval Practice, Generation Effect). Matuschak: erzeugt tiefere Verarbeitung als Cloze. |
| **Cloze (Lückentext)** | Eingebettete Einzelfakten; aufgelöste Aufzählungen; Fakten, deren Kontextsatz die Bedeutung trägt. | Nur die **Schlüssel**information auslöschen, NICHT halbe Sätze. Genug Kontext lassen, aber Hint-Leaks vermeiden. Bei mehreren Lücken jede einzeln (c1, c2 …). Optional Buchstabenhinweis. | Praktisch bewährt; Wozniak: „cloze deletion is fast and has great mnemonic power". Aber Matuschak warnt: Cloze begünstigt **flaches Pattern-Matching** und Mehrdeutigkeit. |
| **Image Occlusion** | Räumlich-visuelle Zuordnung: Anatomie, Geografie, Diagramme, Netzwerktopologien, UML-/Architektur-Diagramme, Schichtenmodelle. | Nur test-/prüfungsrelevante Labels verdecken (nicht alle 20 von 20). Früh 4–6 Boxen/Karte, später max. 8–10. Konsistente Orientierung. Mit Text-Karten für „Warum/Wie" ergänzen. | **KEINE direkte kontrollierte Studie gefunden** (siehe unten). Theoretische Stütze: Picture Superiority + Dual Coding + aktiver Abruf. |
| **Type-in („type the answer")** | Nur wo exakte Schreibung/Syntax zählt: CLI-Befehle, Schlüsselwörter, Methodennamen, Fachtermini, fremdsprachliche Vokabeln. | Sparsam einsetzen. Nicht für Konzepte (Tippfehler/Synonyme werden fälschlich als Fehler gewertet → Frust, falsche Schwierigkeit). | Generation Effect stützt Produktion; type-in ist die strengste Produktionsform. Kein spezifischer RCT für „type-in vs. mental recall". |
| **Bidirektional / Reverse** | Nur bei echter **Zwei-Wege-Nutzung**: Vokabel L1↔L2, Term↔Definition, Symbol↔Name. | NICHT automatisch alles umdrehen. Bei verwechselbaren Paaren weglassen. | Wozniak: „passive and active approach … particularly practicable in word-pairs". Risiko Interferenz (Abschnitt 7). |

**Weitere sinnvolle, evidenznahe Formate, die oft übersehen werden:**
- **„More-than-you-think"-/Anwendungs-Prompts** (Matuschak): nicht nur den Fakt, sondern dessen Bedeutung/Anwendung abfragen — fördert Transfer.
- **Open-list-/Salience-Prompts** (Matuschak): für offene Mengen (z. B. „Nenne *ein* Designprinzip, das lose Kopplung fördert") mit wechselnden Antworten — leveraged einen anderen Wirkmechanismus als konsistente Prompts und ist bewusst von „Sister-Card"-Interferenz ausgenommen.
- **Prozedurale/„Schritt-für-Schritt"-Karten** für Algorithmen/Verfahren (jeder Schritt cued den nächsten — siehe Abschnitt 6).

**Wichtiger Evidenz-Hinweis zu Image Occlusion:** Eine gezielte Literaturrecherche fand **keine** peer-reviewte randomisierte/kontrollierte Studie, die Image-Occlusion-Karten direkt gegen Text-Karten auf Behalten testet — weder in der Anatomie- noch in anderer Bildung. Die kursierenden Pro-Occlusion-Quellen sind App-Marketing und Blogs; sie wiederholen u. a. den **widerlegten Mythos**, „~65 % der Menschen lernen visuell" (Learning-Styles-Mythos). Die theoretische Stütze (Picture-Superiority-Effekt: Nelson, D. L., Reed, V. S. & Walling, J. R., 1976, „Pictorial superiority effect", *JEP: Human Learning and Memory* 2(5):523–528; N=256) wurde an **isolierten** Bildern-vs-Wörtern gemessen, nicht am Abruf von Labels in dichten Diagrammen. Kritisch: Nelson et al. zeigten, dass sich der Bildvorteil bei **hoher schematischer Ähnlichkeit** der Bilder *abschwächt oder umkehrt* — genau die Situation bei sich ähnelnden anatomischen/diagrammatischen Strukturen. **Fazit:** Image Occlusion ist plausibel und praktisch beliebt, aber als „belegt" zu kennzeichnen wäre falsch — Empfehlung: für klar räumliche Zuordnungen verwenden, für „Warum/Wie" auf Text-Karten ausweichen.

### 5. Erklärung & Quelle auf der Karte (elaboratives Feedback)

**Empfehlung: Ja — aber strukturell getrennt vom Abruf.** Konkret: tiefere Erklärung („warum", Zusammenhang, Herleitung) plus Quelle/Herkunft in einer **standardmäßig zugeklappten** HTML-Box (`<details>`-Element) auf der Rückseite, die der Lernende **erst nach dem Antworten** öffnet.

Begründung aus der Forschung:
- **Feedback nach Abruf wirkt.** Roediger & Butler (2011, *Trends in Cognitive Sciences*): *„Retrieval practice is often effective even without feedback … but feedback enhances the benefits of testing."* Butler, Karpicke & Roediger (2007/2008): Feedback nützt besonders, indem es korrekte, aber unsichere Antworten stärkt; **verzögertes** Feedback (= erst nach dem eigenen Antwortversuch) schnitt besser ab als sofortiges.
- **Elaborative Interrogation / Self-Explanation** (Dunlosky et al. 2013, „moderate utility"): Die „Warum"-Erklärung auf der Rückseite unterstützt Integration mit Vorwissen.
- **Quellengedächtnis / Source Memory:** Nielsen rät, bei unsicheren Fakten den Urheber mitzuspeichern („beware of committing false facts to memory"); Wozniak Regel 18/19: Quelle und Datum angeben (besonders bei zeitlich veränderlichem Wissen).

**Gefahr (und ihre Vermeidung):** Zusatzinfo darf weder die **Abrufschwierigkeit** senken (Erklärung nicht auf die Vorderseite, nicht sichtbar vor dem Abruf) noch die **Atomarität** untergraben (die Erklärung ist NICHT Teil der getesteten Antwort — sie wird nicht mitabgefragt). Deshalb: Kernabruf bleibt eine atomare Q/A; die Box ist optionales, nachgelagertes Feedback.

> **Gut:**
> *Vorderseite: Warum reduziert ein Index auf einer Spalte die Lesekosten, erhöht aber die Schreibkosten?*
> *Rückseite (Kernantwort): Reads nutzen die sortierte Struktur (z. B. B-Baum) für O(log n)-Lookup; jeder Write muss den Index zusätzlich aktualisieren.*
> *▸ [zugeklappt] Vertiefung & Quelle: B-Baum hält Daten sortiert → Bereichsabfragen effizient; bei jedem INSERT/UPDATE/DELETE muss der Baum rebalanciert werden. Quelle: Kemper & Eickler, Datenbanksysteme, Kap. Indexstrukturen.*

### 6. Listen, Aufzählungen, Reihenfolgen, Prozesse

- **Wozniak Regel 9/10:** „Avoid sets and enumerations" — sie sind schwer zu behalten, lassen sich aber per **Cloze deletion** auflösen.
- **Overlapping Cloze** (Add-on „Cloze Overlapper") für längere Reihenfolgen/Prozesse: jede Karte verdeckt ein Element, zeigt aber die Nachbarschritte als Gerüst.
- **Sequenzielle Cues:** Schritt n als Cue für Schritt n+1 (gut für Algorithmen, Build-Pipelines, OSI-Schichten).
- **Bevorzugt: in atomare Einzelfakten zerlegen**, ggf. plus eine integrierende „Übersichts"-Karte.

> **Schlecht:** *F: Nenne alle 7 OSI-Schichten. — A: Physical, Data Link, Network, Transport, Session, Presentation, Application.*
> **Gut (Beziehungs-Cloze):** *Über der {{c1::Transport}}-Schicht (L4) liegt die {{c2::Session}}-Schicht (L5).* + *F: Auf welcher OSI-Schicht arbeitet ein Router primär? — A: Schicht 3 (Network).*

### 7. Interferenz vermeiden

- **Wozniak Regel 11 „Combat interference"** — laut SuperMemo-Erfahrung *„probably the single greatest cause of forgetting"* bei erfahrenen Nutzern. Theoretisch gestützt durch Tulving & Thomson (Cue Overload) und die Literatur zu proaktiver/retroaktiver Interferenz.
- **„Sister cards"** (zu ähnliche Karten) trennen: distinkte Cues, kontrastierende Formulierung, gemeinsame Verwechslungsquelle explizit benennen.
- **Retrieval-induced forgetting** (Matuschak): inkonsistente Prompts, die mal diese, mal jene Antwort verlangen, hemmen das nicht-abgerufene Geschwisterwissen → Prompts **konsistent** halten.
- **Bidirektionale Karten:** helfen bei echten Vokabelpaaren, **schaden** bei verwechselbaren Paaren (z. B. zwei ähnliche Fachbegriffe, deren Hin- und Rückrichtung sich gegenseitig stören).

> **Schlecht (interferenzanfällig):** zwei fast identische Karten „Latenz = ?" und „Durchsatz = ?" ohne kontrastierenden Kontext.
> **Gut:** *F: Welche Netzwerkkenngröße misst die VERZÖGERUNG eines einzelnen Pakets (Zeit), nicht die Datenmenge pro Zeit? — A: Latenz.* (Der Gegensatz „Zeit vs. Menge/Zeit" desambiguiert beide Karten.)

### 8. Verständnis & Kontext

- **Wozniak Regel 1–2:** „Do not learn if you do not understand" und „Learn before you memorize" — erst das Gesamtbild aufbauen, dann in atomare Items zerlegen. Karpicke & Blunt belegen, dass Abrufübung *bedeutungsvolles* Lernen fördert, nicht nur stures Memorieren — Voraussetzung ist aber, dass der Stoff verstanden wurde.
- **Nielsen:** keine „orphan questions" (verwaiste Faktoide) — Karten in einen einzigen Pool mit klarem Kontext einbetten; Fragen so phrasieren, dass der Kontext eindeutig ist.
- **Ausreichend Kontext auf der Karte**, damit der Cue distinkt bleibt (Encoding Specificity), ohne die Antwort zu verraten.
- **Personalisierung & eigene Beispiele** (Wozniak Regel 16): eigene Beispiele/Anwendungen sind besonders wirksam (kongruent mit Generation Effect).

### 9. Mnemonik, Bilder, Beispiele

- **Bilder/Dual Coding** (Paivio & Csapo 1973): Bild+Wort sind wirksam für bildhaftes Material. Caveat: Picture-Superiority schwächt sich bei stark ähnlichen Bildern ab (Nelson et al. 1976) — also distinkte, nicht-dekorative Bilder wählen.
- **Keyword-Mnemonik** wurde von Dunlosky et al. (2013) nur als **„low utility"** eingestuft (eng anwendbar, fragiles Langzeitbehalten) — gezielt einsetzen, nicht als Standard.
- **Eigene Beispiele** (Personalisierung) sind robust wirksam (Generation Effect).

### 10. Häufige Anti-Patterns (jeweils Schlecht → Gut)

1. **Mehr-Fakten-Karte.** Schlecht: „Nenne alle ACID-Eigenschaften und erkläre jede." → Gut: vier atomare Karten, je eine Eigenschaft.
2. **Ja/Nein-/ratbare Frage.** Schlecht: „Ist Quicksort stabil?" → Gut: „Welche Eigenschaft fehlt Quicksort in seiner Standardform bzgl. gleicher Schlüssel? — Stabilität."
3. **Ganzer Satz als Cloze.** Schlecht: „{{c1::Quicksort}} hat im {{c2::Durchschnitt}} eine Laufzeit von {{c3::O(n log n)}} aber im {{c4::Worst Case}} {{c5::O(n²)}}." (zu viele Lücken, Pattern-Matching) → Gut: getrennte Karten „Quicksort Average-Case Laufzeit? — O(n log n)" / „Quicksort Worst-Case Laufzeit? — O(n²)".
4. **Hint-Leak.** Schlecht: „Das ACID-Akronym beginnt mit A für {{c1::Atomicity}}." (das „A für" verrät) → Gut: „ACID — welche Eigenschaft garantiert, dass eine Transaktion ganz oder gar nicht ausgeführt wird? — Atomicity."
5. **Dekoratives Bild ohne Abrufbezug.** → Gut: Bild, das die abgefragte räumliche/strukturelle Beziehung zeigt.
6. **Verwaister Faktoid** ohne Kontext. Schlecht: „1965 — was? — Moores Gesetz." → Gut: „Wer postulierte 1965 die Verdopplung der Transistorzahl pro Chip ca. alle zwei Jahre? — Gordon Moore (Mooresches Gesetz)."

### 11. Speziell für KI-/automatisch generierte Karten

**Typische Fehlerquellen:**
- **Halluzinationen** (erfundene Fakten) — besonders bei kleineren/offline-Modellen und ohne Quellbindung.
- **Strukturelle Defekte** (häufiger und tückischer als offene Halluzinationen): zu lange, mehrdeutige, kontextabhängige „Absatz-Karten". Diese sehen auf den ersten Blick plausibel aus, lösen aber Monate später Reibung aus (mehrere gültige Antworten, falscher Memory-Trigger). LLMs neigen zu Verbosität und verletzen so das Minimum Information Principle.
- **Redundanz** (mehrere Karten zum selben Fakt) und **Themaverfehlung** (Fragen über „Spaced Repetition" statt über den Inhalt).

**Qualitätssicherung (für die KI-Richtlinie):**
1. **Atomarität erzwingen** — eine Karte = ein Abrufziel; lange Antworten automatisch aufteilen.
2. **Quellbindung / Grounding:** Karten nur aus dem bereitgestellten Quelltext erzeugen (RAG/„grounded generation"), nicht aus dem Modellwissen → minimiert Halluzinationen. Quelle in die zugeklappte Box schreiben.
3. **Few-shot + strukturierter Output:** gute Beispielkarten und festes Format vorgeben → reduziert Defekte und macht sie maschinell prüfbar.
4. **Automatische Selbstprüfung („LLM-as-judge"):** jede Karte gegen die Checkliste prüfen (atomar? eindeutig? Hint-Leak? ratbar? Antwort kurz? aus Quelle belegbar?); Karten, die durchfallen, neu generieren.
5. **Mensch-in-der-Schleife (Stichprobe):** LLMs fehlt der „Geschmack" zu beurteilen, ob eine Karte langfristig taugt — stichprobenartige manuelle Kontrolle bleibt nötig, da ein hoher Defektanteil das Deck schleichend degradiert.
6. **Dubletten-/Redundanzcheck** über Embedding-Ähnlichkeit.

---

## Recommendations (gestaffelt, mit Schwellen)

**Sofort umsetzen (Pflicht-Regeln für die KI):**
1. **Jede Karte = ein atomarer Abruf.** Wenn die Antwort >1 unabhängige Tatsache oder >ca. 1 kurzen Satz enthält → aufteilen.
2. **Echten Abruf erzwingen:** keine Ja/Nein-, keine Wiedererkennungsfragen; eindeutiger, distinkter Cue; eindeutige, produzierbare Antwort.
3. **Format nach Wissenstyp** (Tabelle in Abschnitt 4): Basic = Default; Cloze für eingebettete Fakten; Image Occlusion nur für räumlich-visuelle Zuordnung; type-in nur bei exakter Schreibung; Reverse nur bei echter Zwei-Wege-Nutzung.
4. **Erklärung + Quelle in zugeklappte `<details>`-Box** auf der Rückseite, getrennt vom Kernabruf.
5. **Grounding:** Karteninhalt ausschließlich aus dem Quellmaterial; bei Unsicherheit Urheber/Quelle mitnennen statt zu raten.

**Qualitäts-Gate (vor dem Import ins Deck):**
6. Automatischer „LLM-as-judge"-Check pro Karte gegen die Checkliste unten; Durchfall → Regeneration.
7. Embedding-Dublettencheck; Redundanz entfernen.

**Schwellen, die die Empfehlung ändern würden:**
- Steigt im Review die **Fehlerquote** einer Karte dauerhaft (Lernende „können sie nie") → Karte ist zu komplex/mehrdeutig → aufteilen oder Cue ergänzen (Matuschaks „sigh test").
- Sinkt die Erfolgsquote eines Decks systematisch unter ~90 % → zu viele nicht-atomare oder interferierende Karten → Refactoring.
- Erscheint bei Cloze-Karten reines **Pattern-Matching** (richtig, aber ohne Verständnis) → in Basic Q/A umwandeln.
- Für Bildmaterial ohne klare räumliche Zuordnung → **kein** Image Occlusion, sondern Text-Karte (da Occlusion-Evidenz fehlt und Picture-Superiority bei ähnlichen Strukturen versagt).

---

## Checkliste „Regeln für gute Karten" (kompakt, KI-anwendbar)

**Inhalt & Struktur**
- [ ] Genau **eine** atomare Information pro Karte (Minimum Information Principle).
- [ ] Stoff zuvor verstanden; kein verwaister Faktoid; genug Kontext, aber kein Hint-Leak.

**Frage/Cue**
- [ ] Erzwingt **aktiven Abruf** (kein Ja/Nein, kein Wiedererkennen, kein ganzer Satz).
- [ ] Cue ist **eindeutig & distinkt** (Encoding Specificity, kein Cue-Overload).
- [ ] **Tractable** (Ziel-Erfolgsquote ~90 %), aber **effortful** (Antwort nicht ableitbar).

**Antwort**
- [ ] So kurz wie möglich; genau eine korrekte „Form"; produzierbar.

**Format**
- [ ] Format passt zum Wissenstyp (Basic/Cloze/Occlusion/type-in/Reverse — siehe Tabelle).
- [ ] Cloze: nur Schlüsselwort ausgelöscht, Hint-Leaks geprüft.
- [ ] Reverse nur bei echter Zwei-Wege-Nutzung; Interferenz/„sister cards" geprüft.

**Feedback/Quelle**
- [ ] Vertiefung („warum"/Zusammenhang) + Quelle in **zugeklappter** Rückseiten-Box, getrennt vom Abruf.

**KI-Qualität**
- [ ] Aus Quelltext belegt (grounded), keine Halluzination; Dublettencheck bestanden; Selbst-/Stichprobenprüfung bestanden.

---

## Vollständige Quellenliste

**Primärliteratur (peer-reviewed)**
- Roediger, H. L. & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science*, 17(3), 249–255.
- Roediger, H. L. & Butler, A. C. (2011). The critical role of retrieval practice in long-term retention. *Trends in Cognitive Sciences*, 15(1), 20–27.
- Karpicke, J. D. & Blunt, J. R. (2011). Retrieval practice produces more learning than elaborative studying with concept mapping. *Science*, 331(6018), 772–775.
- Karpicke, J. D. & Roediger, H. L. (2008). The critical importance of retrieval for learning. *Science*, 319(5865), 966–968.
- Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J. & Willingham, D. T. (2013). Improving students' learning with effective learning techniques: Promising directions from cognitive and educational psychology. *Psychological Science in the Public Interest*, 14(1), 4–58.
- Slamecka, N. J. & Graf, P. (1978). The generation effect: Delineation of a phenomenon. *Journal of Experimental Psychology: Human Learning and Memory*, 4(6), 592–604.
- Tulving, E. & Thomson, D. M. (1973). Encoding specificity and retrieval processes in episodic memory. *Psychological Review*, 80(5), 352–373.
- Bjork, R. A. (1994). Memory and metamemory considerations in the training of human beings. In J. Metcalfe & A. Shimamura (Eds.), *Metacognition: Knowing about knowing* (pp. 185–205). MIT Press.
- Bjork, E. L. & Bjork, R. A. (2011). Making things hard on yourself, but in a good way: Creating desirable difficulties to enhance learning. In *Psychology and the Real World* (pp. 56–64). Worth.
- Pyc, M. A. & Rawson, K. A. (2009). Testing the retrieval effort hypothesis: Does greater difficulty correctly recalling information lead to higher levels of memory? *Journal of Memory and Language*, 60(4), 437–447.
- Pyc, M. A. & Rawson, K. A. (2010). Why testing improves memory: Mediator effectiveness hypothesis. *Science*, 330(6002), 335.
- Butler, A. C., Karpicke, J. D. & Roediger, H. L. (2007). The effect of type and timing of feedback on learning from multiple-choice tests. *Journal of Experimental Psychology: Applied*, 13(4), 273–281.
- Paivio, A. & Csapo, K. (1973). Picture superiority in free recall: Imagery or dual coding? *Cognitive Psychology*, 5(2), 176–206.
- Paivio, A. (1971/1986). *Imagery and Verbal Processes* / *Mental Representations: A Dual Coding Approach*. Holt/Oxford University Press.
- Clark, J. M. & Paivio, A. (1991). Dual coding theory and education. *Educational Psychology Review*, 3(3), 149–170.
- Nelson, D. L., Reed, V. S. & Walling, J. R. (1976). Pictorial superiority effect. *Journal of Experimental Psychology: Human Learning and Memory*, 2(5), 523–528.
- Hattie, J. & Timperley, H. (2007). The power of feedback. *Review of Educational Research*, 77(1), 81–112.
- Pashler, H., Bain, P., Bottge, B., Graesser, A., Koedinger, K., McDaniel, M. & Metcalfe, J. (2007). *Organizing Instruction and Study to Improve Student Learning* (IES Practice Guide, NCER 2007-2004). U.S. Department of Education.

**Anki in der Medizinausbildung (beobachtend/korrelativ)**
- Deng, F., Gluckstein, J. A. & Larsen, D. P. (2015). Student-directed retrieval practice is a predictor of medical licensing examination performance. *Perspectives on Medical Education*, 4(6), 308–313. (Befund: jede zusätzliche ~1700 einzigartige Anki-Karten ≈ +1 Punkt USMLE Step 1; B=5,89×10⁻⁴, p=0,024.)
- Wothe, J. K. et al. (2023). Academic and wellness outcomes associated with use of Anki spaced repetition software in medical school. *Journal of Medical Education and Curricular Development*, 10. (Tägliche Anki-Nutzung korreliert mit höherem Step-1-Score, p=0,039; nicht Step 2.)

**Praxisquellen (Erfahrungswissen / nicht peer-reviewed)**
- Wozniak, P. (1999, akt.). Effective learning: Twenty rules of formulating knowledge. SuperMemo. (inkl. Minimum Information Principle.)
- Nielsen, M. (2018). Augmenting Long-term Memory. augmentingcognition.com/ltm.html
- Matuschak, A. (2020). How to write good prompts: using spaced repetition to create understanding. andymatuschak.org/prompts
- Matuschak, A. & Nielsen, M. (2019). How can we develop transformative tools for thought? numinous.productions/ttft
- Anki Manual (Ankitects). docs.ankiweb.net (Cloze, Note-/Card-Types, Reverse).

---

## Caveats (Einschränkungen der Evidenz)

- **Wozniaks „20 Regeln" und ein Großteil der konkreten Karten-Best-Practices (Nielsen, Matuschak)** sind erfahrungsbasiert, nicht in RCTs getestet. Ihre Kernideen sind jedoch kongruent mit kontrollierten Befunden (Retrieval Practice, Generation Effect, Interferenz).
- **Image Occlusion** hat **keine** direkte kontrollierte Wirksamkeitsevidenz; die Begründung ist Extrapolation aus Picture-Superiority/Dual Coding, deren klassische Studien an isolierten Bildern (nicht an Diagramm-Labels) durchgeführt wurden — und der Bildvorteil kann bei ähnlichen Strukturen verschwinden. Kursierende „65 % visuelle Lerner"-Behauptungen sind ein widerlegter Mythos.
- **Anki-Studien in der Medizin** sind durchweg **beobachtend/korrelativ** und durch Selbstselektion konfundiert (motiviertere/stärkere Studierende nutzen Anki häufiger); mindestens eine Kohortenstudie fand keinen signifikanten Zusammenhang. Sie stützen *Retrieval Practice + Spacing allgemein*, nicht ein bestimmtes Kartenformat.
- **Elaborative interrogation/self-explanation** sind nur „moderate utility" und stark vom Vorwissen abhängig; in echten Bildungskontexten unzureichend evaluiert.
- **type-in vs. mentaler Abruf**: kein spezifischer RCT; die Empfehlung folgt aus dem Generation Effect und der Praxislogik (exakte Schreibung).
- Bei der Formatfrage gilt generell: Die **Formulierung** ist empirisch besser abgesichert als die **Formatwahl** — letztere ruht stärker auf Praxiskonsens.