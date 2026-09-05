#!/usr/bin/env python3
"""Synthetic native/Docker integration checks, never using personal sources.

    python3 tests/integration/check_pipeline.py build
    python3 tests/integration/check_pipeline.py visual [--keep-fixtures]

Select --backend native to exercise the managed Windows Python environment.
Images are built by CI before Docker checks run (the existing wrappers also build
missing images locally). Fixtures are never read from a user's topics. Every
run owns new, gitignored directories; failures retain those for diagnosis.
These checks do not contact AnkiConnect or import into a real user's collection.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_NOTES = 8
EXPECTED_CARDS = 10
CARD_TYPES = ["basic", "reversed", "reversed", "cloze", "cloze", "typein",
              "occlusion", "occlusion", "occlusion", "occlusion"]
BACKEND = "docker"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(*args):
    print("+ " + " ".join(map(str, args)), flush=True)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run(list(map(str, args)), cwd=ROOT, text=True,
                            encoding="utf-8", errors="replace", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout


def forge(command, *args):
    if BACKEND == "native":
        return run(sys.executable, "tools/forge.py", "--backend", "native", command, *args)
    return run(f"./tools/{command}.sh", *args)


def in_container(image, script, *args):
    if BACKEND == "native":
        return run(sys.executable, script, *args)
    return run("docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
               "-v", f"{ROOT}:/work", "--entrypoint", "python", image,
               script, *args)


def write_diagram(path):
    """Create a simple lossless illustration without a host imaging library."""
    width, height = 640, 240
    rows = []
    for y in range(height):
        row = bytearray([0])  # PNG filter: none
        for x in range(width):
            color = (255, 255, 255)
            if 64 <= x < 224 and 72 <= y < 168:
                color = (220, 45, 45)
            elif 416 <= x < 576 and 72 <= y < 168:
                color = (40, 100, 220)
            elif 224 <= x < 416 and 117 <= y < 123:
                color = (30, 30, 30)
            row.extend(color)
        rows.append(bytes(row))

    def chunk(kind, body):
        return (struct.pack("!I", len(body)) + kind + body
                + struct.pack("!I", zlib.crc32(kind + body) & 0xffffffff))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows)))
                     + chunk(b"IEND", b""))


def fixture(source_dir, deck_dir):
    # Exercise media paths that require both quoting and Unicode handling even
    # when this checkout itself has a simple ASCII path.
    image = source_dir / "blocks ä.png"
    write_diagram(image)
    regions = [
        {"label": "red", "x": .10, "y": .30, "w": .25, "h": .40},
        {"label": "blue", "x": .65, "y": .30, "w": .25, "h": .40},
    ]
    data = {
        "deck": "CI synthetic::All card types",
        "cards": [
            {"type": "basic", "guid": "ci-stable-basic", "front": "What flows between the blocks?",
             "back": "Data.", "explanation": f'<img src="{image.as_posix()}">',
             "source": "Synthetic fixture, page 1"},
            {"type": "basic", "reverse": True, "front": "JSON", "back": "JavaScript Object Notation"},
            {"type": "cloze", "text": "The {{c1::red}} block sends data to the {{c2::blue}} block."},
            {"type": "typein", "front": "Type the three-letter format abbreviation.", "back": "PNG"},
            {"type": "occlusion", "image": image.as_posix(), "mode": "hide-one",
             "header": "Name the color of the hidden block.", "regions": regions},
            {"type": "occlusion", "image": image.as_posix(), "mode": "hide-all",
             "header": "Name the color of the block marked with a question mark.", "regions": regions},
        ],
    }
    for card in data["cards"]:
        card["tags"] = ["synthetic_ci"]
    path = deck_dir / "all-types.cards.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path, image


def grounded_source(extracted_dir):
    extracted_dir.mkdir(parents=True, exist_ok=True)
    (extracted_dir / "all-types.md").write_text(
        "<!-- p. 1 -->\nData flows between the red and blue blocks. A data message flows.\n"
        "JSON means JavaScript Object Notation. PNG is a three-letter format abbreviation.\n"
        "The red block sends data to the blue block. The two colors are red and blue.\n",
        encoding="utf-8")


def package_snapshot(path, image):
    """Read the builder's package independently, without importing builder code."""
    with zipfile.ZipFile(path) as package:
        media = json.loads(package.read("media"))
        require(list(media.values()) == [image.name], f"Unexpected embedded media: {media}")
        require(package.read(next(iter(media))) == image.read_bytes(), "Embedded image changed")
        raw = package.read("collection.anki2")
    with tempfile.TemporaryDirectory(prefix="acf-ci-db-") as temp:
        db = Path(temp) / "collection.anki2"
        db.write_bytes(raw)
        with closing(sqlite3.connect(db)) as conn:
            notes = conn.execute("select guid, mid, flds from notes order by guid").fetchall()
            cards = conn.execute("select n.guid, c.ord from cards c join notes n on n.id=c.nid order by n.guid,c.ord").fetchall()
            models = json.loads(conn.execute("select models from col").fetchone()[0])
    require(len(notes) == EXPECTED_NOTES, f"Expected {EXPECTED_NOTES} notes, got {len(notes)}")
    require(len(cards) == EXPECTED_CARDS, f"Expected {EXPECTED_CARDS} cards, got {len(cards)}")
    require(len({note[0] for note in notes}) == EXPECTED_NOTES, "Duplicate note GUIDs")
    types = Counter(models[str(mid)]["name"] for _, mid, _ in notes)
    require(types == {"Anki-Karten Basic": 1, "Anki-Karten Basic+Reversed": 1,
                      "Anki-Karten Cloze": 1, "Anki-Karten Type-in": 1,
                      "Anki-Karten Image Occlusion": 4}, f"Wrong note types: {types}")
    require(len(cards) == len(set(cards)), "Duplicate card ordinals per note")
    return notes, cards


def check_build(cards, image, deck_dir, extracted_dir):
    original = deck_dir / "original.apkg"
    rebuilt = deck_dir / "rebuilt.apkg"
    run(sys.executable, "tools/lint_cards.py", cards)
    grounded_source(extracted_dir)
    output = forge("finish", cards, original)
    require(re.search(r"Notes: 8\s+Cards: 10", output), "Real Anki imported unexpected counts")
    require("No source text found" not in output, "Finish did not find its synthetic source")
    before = package_snapshot(original, image)
    forge("build", cards, rebuilt)
    require(package_snapshot(rebuilt, image) == before, "Identical rebuild changed note GUIDs, fields or ordinals")

    # Updating an explicitly identified note must keep its identity, while
    # generated GUIDs (including occlusion regions) and cloze ordinals stay put.
    data = json.loads(cards.read_text(encoding="utf-8"))
    data["cards"][0]["back"] = "A data message."
    cards.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    forge("build", cards, rebuilt)
    after = package_snapshot(rebuilt, image)
    require([(g, m) for g, m, _ in before[0]] == [(g, m) for g, m, _ in after[0]],
            "A content update changed GUIDs or note types")
    require(before[1] == after[1], "A content update changed the cloze/card ordinal mapping")
    changed = [new[0] for old, new in zip(before[0], after[0]) if old != new]
    require(changed == ["ci-stable-basic"], f"Unexpected content changes: {changed}")
    run(sys.executable, "tools/deck_diff.py", original, rebuilt, "--strict")
    forge("validate", rebuilt)

    # Exercise finish's multi-file coverage/bundling branch, independently of
    # the fixed all-types snapshot above.
    second = deck_dir / "supplement.cards.json"
    second.write_text(json.dumps({"deck": "CI synthetic::Supplement", "cards": [
        {"type": "basic", "guid": "ci-supplement", "front": "What is the output state?",
         "back": "Ready.", "tags": ["synthetic_ci"], "source": "Synthetic fixture, page 1"}
    ]}) + "\n", encoding="utf-8")
    (extracted_dir / "supplement.md").write_text(
        "<!-- p. 1 -->\nThe output state is Ready.\n", encoding="utf-8")
    output = forge("finish", cards, second, deck_dir / "bundle.apkg")
    require(re.search(r"Notes: 9\s+Cards: 11", output), "Bundled finish lost or duplicated cards")
    require("coverage" in output.lower(), "Bundled finish omitted coverage")
    require("grounding" in output.lower(), "Finish omitted source grounding")
    require("No source text found" not in output, "Bundled finish lost source grounding")


def check_visual(cards, image, source_dir, extracted_dir):
    pdf = source_dir / "sample.pdf"  # Lowercase-only folder exercises prep.sh's PDF detection.
    in_container("anki-cards-extract", "tests/integration/make_pdf.py", pdf, image)
    (source_dir / "notes.txt").write_text("Synthetic text source: local fixture only.\n", encoding="utf-8")
    # The pinned PDF extraction stack creates this native session sidecar
    # even for an in-memory document. Only remove the recognized file when
    # this invocation created it; never touch a pre-existing workspace file.
    session = ROOT / ":memory:.ses"
    session_existed = session.exists()
    try:
        forge("prep", source_dir, "--lang", "eng", "-j", "2", "--zoom", "1.5")
    finally:
        if not session_existed and session.is_file() and not session.is_symlink():
            if session.stat().st_size < 100 and re.fullmatch(
                    rb"\d+\n[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\n", session.read_bytes()):
                session.unlink()
    markdown = (extracted_dir / "sample.md").read_text(encoding="utf-8")
    require(re.search(r"<!-- p\. 1(?: · \d+ fig\.)? -->", markdown), "Native page marker missing")
    require("p. 2 (OCR)" in markdown, "Scanned page did not take the OCR path")
    require("(empty)" not in markdown, "Extraction produced an empty page")
    require("native text" in markdown.lower(), "Native PDF text was lost")
    require("ready" in markdown.lower(), "Scanned text did not survive OCR")
    require((extracted_dir / "notes.md").read_text(encoding="utf-8") == (source_dir / "notes.txt").read_text(encoding="utf-8"),
            "Text sources were not mirrored faithfully")
    index = (extracted_dir / "sample.figures.md").read_text(encoding="utf-8")
    require("Fig. 1" in index, "Figure caption index missing")
    figures = json.loads((extracted_dir / "sample.figures.json").read_text(encoding="utf-8"))["figures"]
    require(any(f["page"] == 1 for f in figures), "Native-page diagram was not cropped")
    for figure in figures:
        crop = Path(figure["image"])
        # The extract container records /work paths for absolute wrapper inputs.
        if BACKEND == "docker" and crop.is_absolute():
            crop = ROOT / crop.relative_to("/work")
        require(crop.is_file() and crop.stat().st_size > 100, f"Missing figure crop: {crop}")
    run(sys.executable, "tools/lint_cards.py", cards)
    scan = pdf.with_name(pdf.stem + "-scan.png")
    forge("detect", scan, "--lang", "eng")
    labels = json.loads(scan.with_suffix(".labels.json").read_text(encoding="utf-8"))
    require(any("READY" in label["label"].upper() for label in labels), "Label OCR lost READY")
    require(all(0 <= label[key] <= 1 for label in labels for key in ("x", "y", "w", "h")),
            "Label coordinates are not normalized")
    forge("preview", cards)  # Default must render BOTH themes.
    preview = cards.parent / "preview" / "all-types"
    expected = {f"{i:02d}-{kind}-{side}{theme}.png"
                for i, kind in enumerate(CARD_TYPES, 1)
                for side in ("front", "back") for theme in ("", "-dark")}
    require({p.name for p in preview.glob("*.png")} == expected, "Missing or unexpected previews")
    index = (preview / "index.html").read_text(encoding="utf-8")
    require(all(name in index for name in expected), "Preview index omits rendered cards")
    in_container("anki-cards-preview", "tests/integration/check_images.py", preview)

    formulas = cards.with_name("formulas.cards.json")
    formulas.write_text(json.dumps({"deck": "CI synthetic::Offline formulas", "cards": [
        {"type": "basic", "front": r"Simplify \(\frac{1}{2}+\sqrt{4}\).",
         "back": r"\[\require{cancel}\cancel{x}+\frac{5}{2}\]", "tags": ["synthetic_ci"]}
    ]}) + "\n", encoding="utf-8")
    forge("preview", formulas, "--offline")
    formula_preview = cards.parent / "preview" / "formulas"
    report = json.loads((formula_preview / "render-report.json").read_text(encoding="utf-8"))
    require(report["offline"] is True, "Formula preview was not offline")
    require(len(report["math_renders"]) == 4 and
            all(item["math_count"] > 0 for item in report["math_renders"]),
            "A light/dark formula front/back was not typeset")
    require(any("cancel.js" in path for path in report["mathjax_requests"]),
            "Formula fixture did not load the local dynamic TeX extension")
    in_container("anki-cards-preview", "tests/integration/check_images.py", formula_preview, "--formulas")
    in_container("anki-cards-preview", "tests/integration/check_mathjax.py",
                 "--output", formula_preview / "missing-extension-check.json")


def main():
    global BACKEND
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "visual"))
    parser.add_argument("--backend", choices=("docker", "native"), default="docker")
    parser.add_argument("--keep-fixtures", action="store_true", help="Keep successful synthetic outputs for inspection")
    args = parser.parse_args()
    BACKEND = args.backend
    if BACKEND == "docker" and os.name != "posix":
        parser.error("Run this check in Linux/WSL, where the Docker shell wrappers run.")
    os.chdir(ROOT)
    for parent in ("sources", "decks", "extracted"):
        Path(parent).mkdir(exist_ok=True)
    source_dir = Path(tempfile.mkdtemp(prefix=f"_ci-{args.mode}-", suffix="_rebuild", dir="sources")).resolve().relative_to(ROOT)
    deck_dir = Path("decks") / source_dir.name
    extracted_dir = Path("extracted") / source_dir.name
    deck_dir.mkdir()
    owned = (source_dir, deck_dir, extracted_dir)
    start = time.monotonic()
    success = False
    try:
        cards, image = fixture(source_dir, deck_dir)
        if args.mode == "build":
            check_build(cards, image, deck_dir, extracted_dir)
        else:
            check_visual(cards, image, source_dir, extracted_dir)
        success = True
        print(f"PASS: {BACKEND} {args.mode} integration ({time.monotonic() - start:.1f}s)", flush=True)
    finally:
        if success and not args.keep_fixtures:
            for path in owned:
                if path.exists():
                    require(path.resolve().parent in {ROOT / "sources", ROOT / "decks", ROOT / "extracted"}
                            and path.name.startswith("_ci-"), "Refusing cleanup outside owned fixture directories")
                    shutil.rmtree(path)
        else:
            print("Synthetic fixtures retained: " + ", ".join(map(str, owned)), flush=True)


if __name__ == "__main__":
    main()
