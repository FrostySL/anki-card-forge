#!/usr/bin/env python3
"""Detects text labels in an image (Tesseract OCR) and outputs their exact
bounding boxes as fractional coordinates (0..1) — as a template for image
occlusion regions. No more eyeballing the boxes.

Usage (via tools/detect.sh inside the preview container):
    ./tools/detect.sh sources/image.png [--lang eng+deu] [--min-conf 40]

Output:
  - table of detected labels (index, text, x, y, w, h) on stdout
  - <image>.labels.json  — the same data as a file (to copy into cards.json)
  - <image>.labels.png   — the image with numbered boxes for inspection
"""
import argparse
import json
import os
from collections import defaultdict

import pytesseract
from PIL import Image, ImageDraw, ImageFont
from pytesseract import Output


def detect(path, lang="eng+deu", min_conf=45, gap_factor=1.6):
    img = Image.open(path).convert("RGB")
    width, height = img.size
    data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT)

    # Group words by (block, paragraph, line)
    lines = defaultdict(list)
    for i in range(len(data["text"])):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        # Drop symbols/icons (barely alphanumeric) and weak matches
        if conf < min_conf or sum(c.isalnum() for c in text) < 2:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines[key].append(
            (data["left"][i], data["top"][i], data["width"][i], data["height"][i], text)
        )

    # In diagrams, Tesseract merges labels far apart on the same baseline into
    # one line -> split at large horizontal gaps.
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
    labels.sort(key=lambda l: (round(l["y"], 2), l["x"]))  # top->bottom, left->right
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
    ap = argparse.ArgumentParser(description="OCR label detection for occlusion boxes")
    ap.add_argument("image")
    ap.add_argument("--lang", default="eng+deu")
    ap.add_argument("--min-conf", type=float, default=45)
    ap.add_argument("--gap-factor", type=float, default=1.6,
                    help="split lines at gaps > factor * text height")
    args = ap.parse_args()

    img, labels = detect(args.image, args.lang, args.min_conf, args.gap_factor)
    stem = os.path.splitext(args.image)[0]
    json_path, png_path = stem + ".labels.json", stem + ".labels.png"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    annotate(img.copy(), labels, png_path)

    print(f"{len(labels)} labels detected in {args.image} ({img.size[0]}x{img.size[1]}):")
    for idx, l in enumerate(labels):
        print(
            f"  [{idx:2d}] {l['label'][:32]:32}  "
            f"x={l['x']:.3f} y={l['y']:.3f} w={l['w']:.3f} h={l['h']:.3f}"
        )
    print(f"-> {json_path}")
    print(f"-> {png_path}  (image with numbered boxes)")


if __name__ == "__main__":
    main()
