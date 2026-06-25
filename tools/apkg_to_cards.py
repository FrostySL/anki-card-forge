#!/usr/bin/env python3
"""Liest ein Anki-.apkg ZURUECK in cards.json — eine pro Deck — mit erhaltener
Notiz-GUID. Damit lassen sich **bereits in Anki gelernte/bearbeitete** Karten neu
aufbereiten, OHNE den Lernfortschritt zu verlieren.

    python3 tools/apkg_to_cards.py <export.apkg> [-o ZIELORDNER]

Workflow (siehe CLAUDE.md, Abschnitt "Bestehendes Deck aendern ohne Fortschrittsverlust"):
  1. In Anki exportieren: Datei -> Exportieren -> .apkg (mit Scheduling).
  2. Dieses Tool laufen lassen -> cards.json je Deck (Felder = aktueller Stand,
     `guid` pro Karte erhalten).
  3. cards.json editieren (Struktur/HTML, siehe Skill `kartenbau`).
  4. tools/build.sh damit neu bauen — build_deck uebernimmt die `guid`, sodass der
     Re-Import in Anki die Notiz AKTUALISIERT statt zu duplizieren (Fortschritt bleibt).
  5. In Anki importieren: "Notizen aktualisieren", Scheduling NICHT zuruecksetzen.

Warum das noetig ist: Lernfortschritt haengt an der Notiz-GUID. Ohne erhaltene GUID
berechnet genanki bei geaendertem Text eine neue -> Duplikate, Fortschritt weg.

Unterstuetzt das moderne Export-Format (collection.anki21b, zstd-komprimiert; echte
Daten) und das Legacy-Format (collection.anki2, wie genanki es schreibt). Bildet die
Notiztypen dieses Projekts ab:
  'Anki-Karten Basic'          -> basic
  'Anki-Karten Cloze'          -> cloze
  'Anki-Karten Type-in'        -> typein
  'Anki-Karten Basic+Reversed' -> basic + "reverse": true
Cloze wird auch an `{{c…::}}` im ersten Feld erkannt. Occlusion-Notizen koennen NICHT
zu image/regions zurueckgewandelt werden (Warnung, uebersprungen). Fremde Notiztypen
werden best-effort als basic uebernommen (Warnung).

WICHTIG: Die ausgelesenen Felder enthalten eine evtl. vorhandene "Vertiefung & Quelle"-
Box bereits eingebacken (im Back/Extra). Beim Editieren also NICHT zusaetzlich
`explanation`/`source` setzen (sonst doppelte Box) — entweder die Box im Feld lassen
oder sie dort herausloesen und sauber in `explanation`/`source` ueberfuehren.

Laeuft auf dem Host (nur stdlib + zstd) — KEIN Docker noetig.
"""
import argparse
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

FIELD_SEP = "\x1f"
KNOWN = {
    "Anki-Karten Basic", "Anki-Karten Cloze", "Anki-Karten Type-in",
    "Anki-Karten Basic+Reversed", "Anki-Karten Image Occlusion",
}


def _decompress_zstd(data: bytes) -> bytes:
    """zstd-Frame -> rohe Bytes. python-zstandard bevorzugt, sonst zstd-CLI."""
    try:
        import zstandard
    except ImportError:
        proc = subprocess.run(["zstd", "-dc"], input=data, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "Brauche python-'zstandard' ODER das 'zstd'-CLI zum Entpacken von "
                "collection.anki21b: " + proc.stderr.decode("utf-8", "replace")[:200]
            )
        return proc.stdout
    dctx = zstandard.ZstdDecompressor()
    try:
        return dctx.decompress(data)
    except zstandard.ZstdError:  # Groesse nicht im Frame-Header -> streamen
        return dctx.stream_reader(io.BytesIO(data)).read()


def open_collection(apkg_path):
    """Schreibt die ECHTE Collection-DB in ein Tempfile und gibt (Connection, Pfad)."""
    with zipfile.ZipFile(apkg_path) as z:
        names = set(z.namelist())
        if "collection.anki21b" in names:           # modern, zstd
            raw = _decompress_zstd(z.read("collection.anki21b"))
        elif "collection.anki21" in names:          # uebergangsformat
            blob = z.read("collection.anki21")
            raw = blob if blob[:16] == b"SQLite format 3\x00" else _decompress_zstd(blob)
        elif "collection.anki2" in names:           # legacy (genanki)
            raw = z.read("collection.anki2")
        else:
            raise RuntimeError("Keine collection.* im .apkg gefunden.")
    tmp = tempfile.NamedTemporaryFile(suffix=".anki2", delete=False)
    tmp.write(raw)
    tmp.close()
    return sqlite3.connect(tmp.name), tmp.name


def _maps(con):
    """(notetype-id->name, deck-id->name, schema). Deckname-Trenner -> '::'."""
    tabs = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "notetypes" in tabs:  # moderne DB: eigene Tabellen
        ntype = dict(con.execute("SELECT id, name FROM notetypes"))
        decks = {d: n.replace(FIELD_SEP, "::") for d, n in con.execute("SELECT id, name FROM decks")}
        return ntype, decks, "modern"
    # Legacy: alles in col als JSON
    models, decks_json = con.execute("SELECT models, decks FROM col").fetchone()
    ntype = {int(mid): m["name"] for mid, m in json.loads(models).items()}
    decks = {int(did): d["name"].replace(FIELD_SEP, "::") for did, d in json.loads(decks_json).items()}
    return ntype, decks, "legacy"


def _note_to_card(model, fields, guid, tags, nid, warnings):
    """Eine DB-Notiz -> ein cards.json-Eintrag (oder None bei Occlusion)."""
    def f(i):
        return fields[i] if i < len(fields) else ""

    m = model.lower()
    card = {"guid": guid}
    if "occlusion" in m:
        warnings.append(f"nid {nid}: Occlusion uebersprungen (nicht zu image/regions rueckwandelbar).")
        return None
    if "cloze" in m or "{{c" in f(0):
        card.update(type="cloze", text=f(0), extra=f(1))
    elif "type-in" in m or "typein" in m:
        card.update(type="typein", front=f(0), back=f(1))
    elif "reversed" in m or "reverse" in m:
        # Reversed-Model hat [Front, Back, More]; More (3. Feld) ans Back haengen,
        # damit eine evtl. eingebackene Box nicht verloren geht.
        back = f(1) + (f(2) if f(2).strip() else "")
        card.update(type="basic", reverse=True, front=f(0), back=back)
        if f(2).strip():
            warnings.append(f"nid {nid}: reversed – 'More'-Feld ans Back gehaengt (pruefen).")
    else:
        if model not in KNOWN:
            warnings.append(f"nid {nid}: unbekannter Notiztyp {model!r} -> als basic uebernommen.")
        card.update(type="basic", front=f(0), back=f(1))
    card["tags"] = tags.split()
    return card


def extract(con):
    """-> (dict deckname->[cards], warnings)."""
    ntype, decks, _schema = _maps(con)
    note_deck = {nid: decks.get(did, "Default")
                 for nid, did in con.execute("SELECT nid, MIN(did) FROM cards GROUP BY nid")}
    by_deck, warnings = {}, []
    for nid, guid, mid, flds, tags in con.execute("SELECT id, guid, mid, flds, tags FROM notes"):
        card = _note_to_card(ntype.get(mid, f"mid:{mid}"), flds.split(FIELD_SEP), guid, tags, nid, warnings)
        if card:
            by_deck.setdefault(note_deck.get(nid, "Default"), []).append(card)
    return by_deck, warnings


def write_cards_json(by_deck, outdir):
    os.makedirs(outdir, exist_ok=True)
    files = []
    for deck, cards in sorted(by_deck.items()):
        safe = re.sub(r"[^\w.+-]+", "_", deck).strip("_")
        path = os.path.join(outdir, safe + ".cards.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"deck": deck, "cards": cards}, fh, ensure_ascii=False, indent=1)
        files.append((path, deck, len(cards)))
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Anki-.apkg zurueck in cards.json (GUIDs erhalten).")
    ap.add_argument("apkg", help="Pfad zum .apkg (Anki-Export oder von uns gebaut)")
    ap.add_argument("-o", "--out", help="Zielordner (Default: <apkg>_cards/ daneben)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.apkg):
        ap.error(f"Datei nicht gefunden: {args.apkg}")
    outdir = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.apkg)),
        re.sub(r"\.apkg$", "", os.path.basename(args.apkg)) + "_cards",
    )

    con, tmp = open_collection(args.apkg)
    try:
        by_deck, warnings = extract(con)
    finally:
        con.close()
        os.unlink(tmp)

    files = write_cards_json(by_deck, outdir)
    total = sum(n for _, _, n in files)
    print(f"== {os.path.basename(args.apkg)} -> {len(files)} cards.json ({total} Notizen) ==")
    for path, deck, n in files:
        print(f"  {n:3d}  {deck}")
    if warnings:
        print(f"\n{len(warnings)} Warnung(en):")
        for w in warnings:
            print("  -", w)
    print(f"\ncards.json in: {outdir}")
    quoted = " ".join(f'"{p}"' for p, _, _ in files)
    print("Neu bauen (GUIDs/Fortschritt bleiben) z. B.:")
    print(f'  ./tools/build.sh {quoted} "out.apkg"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
