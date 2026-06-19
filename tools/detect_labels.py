#!/usr/bin/env python3
"""Erkennt Text-Labels in einem Bild (Tesseract OCR) und gibt deren exakte
Bounding-Boxen als Bruchteil-Koordinaten (0..1) aus – als Vorlage fuer
Image-Occlusion-Regionen. So muessen die Boxen nicht per Auge geschaetzt werden.

Aufruf (ueber tools/detect.sh im Vorschau-Container):
    ./tools/detect.sh quellen/bild.png [--lang deu+eng] [--min-conf 40]

Ausgabe:
  - Tabelle der erkannten Labels (Index, Text, x, y, w, h) auf stdout
  - <bild>.labels.json  – dieselben Daten als Datei (zum Uebernehmen in cards.json)
  - <bild>.labels.png   – das Bild mit nummerierten Boxen zum Anschauen
"""
import argparse
import json
import os
from collections import defaultdict

import pytesseract
from PIL import Image, ImageDraw, ImageFont
from pytesseract import Output


def detect(path, lang="deu+eng", min_conf=45, gap_factor=1.6):
    img = Image.open(path).convert("RGB")
    width, height = img.size
    data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT)

    # Woerter nach (block, par, line) gruppieren
    lines = defaultdict(list)
    for i in range(len(data["text"])):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        # Symbole/Icons (kaum alphanumerisch) und schwache Treffer verwerfen
        if conf < min_conf or sum(c.isalnum() for c in text) < 2:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines[key].append(
            (data["left"][i], data["top"][i], data["width"][i], data["height"][i], text)
        )

    # In Diagrammen fasst Tesseract weit auseinander liegende Labels derselben
    # Hoehe zu einer Zeile zusammen -> bei grossen horizontalen Luecken auftrennen.
    groups = []
    for words in lines.values():
        words.sort(key=lambda w: w[0])
        avg_h = sum(w[3] for w in words) / len(words)
        current = [words[0]]
        for prev, word in zip(words, words[1:]):
            gap = word[0] - (prev[0] + prev[2])
            if gap > gap_factor * avg_h:
                groups.append(current)
                current = [word]
            else:
                current.append(word)
        groups.append(current)

    labels = []
    for words in groups:
        x0 = min(w[0] for w in words)
        y0 = min(w[1] for w in words)
        x1 = max(w[0] + w[2] for w in words)
        y1 = max(w[1] + w[3] for w in words)
        labels.append(
            {
                "label": " ".join(w[4] for w in words),
                "x": round(x0 / width, 4),
                "y": round(y0 / height, 4),
                "w": round((x1 - x0) / width, 4),
                "h": round((y1 - y0) / height, 4),
            }
        )
    labels.sort(key=lambda l: (round(l["y"], 2), l["x"]))  # oben->unten, links->rechts
    return img, labels


def annotate(img, labels, out_path):
    draw = ImageDraw.Draw(img)
    width, height = img.size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    for idx, l in enumerate(labels):
        x, y = l["x"] * width, l["y"] * height
        w, h = l["w"] * width, l["h"] * height
        draw.rectangle([x, y, x + w, y + h], outline=(229, 57, 53), width=3)
        draw.text((x, max(0, y - 24)), str(idx), fill=(229, 57, 53), font=font)
    img.save(out_path)


def main():
    ap = argparse.ArgumentParser(description="OCR-Label-Erkennung fuer Occlusion-Boxen")
    ap.add_argument("image")
    ap.add_argument("--lang", default="deu+eng")
    ap.add_argument("--min-conf", type=float, default=45)
    ap.add_argument("--gap-factor", type=float, default=1.6,
                    help="Zeilen bei Luecke > Faktor*Texthoehe auftrennen")
    args = ap.parse_args()

    img, labels = detect(args.image, args.lang, args.min_conf, args.gap_factor)
    stem = os.path.splitext(args.image)[0]
    json_path, png_path = stem + ".labels.json", stem + ".labels.png"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    annotate(img.copy(), labels, png_path)

    print(f"{len(labels)} Labels erkannt in {args.image} ({img.size[0]}x{img.size[1]}):")
    for idx, l in enumerate(labels):
        print(
            f"  [{idx:2d}] {l['label'][:32]:32}  "
            f"x={l['x']:.3f} y={l['y']:.3f} w={l['w']:.3f} h={l['h']:.3f}"
        )
    print(f"-> {json_path}")
    print(f"-> {png_path}  (Bild mit nummerierten Boxen)")


if __name__ == "__main__":
    main()
