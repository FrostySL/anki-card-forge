"""Generate an original two-page fixture with native and raster-only text."""
from pathlib import Path
import sys

import fitz


def main():
    target, image = map(Path, sys.argv[1:])
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_text((40, 60), "Synthetic pipeline fixture", fontsize=24)
    page.insert_text((40, 110), "This page has native text and one embedded diagram.", fontsize=16)
    page.insert_text((40, 140), "The red block sends data to the blue block.", fontsize=16)
    page.insert_image(fitz.Rect(40, 220, 560, 415), filename=str(image))
    page.insert_text((40, 450), "Figure 1: A red block sends data to a blue block.", fontsize=14)

    # Render text to pixels first, then embed only that raster: no hidden text
    # layer is available, so extraction genuinely needs Tesseract on page two.
    scan = fitz.open()
    scanned = scan.new_page(width=600, height=800)
    for y, text in [(100, "SCANNED CHECK"), (160, "OCR reads this page."),
                    (220, "An input becomes an output."), (280, "The output is READY.")]:
        scanned.insert_text((45, y), text, fontsize=26)
    pixels = scanned.get_pixmap(matrix=fitz.Matrix(3, 3))
    pixels.save(str(target.with_name(target.stem + "-scan.png")))
    page = document.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=pixels.tobytes("png"))
    document.save(str(target))
    document.close()
    scan.close()
    print(f"Created synthetic native/scanned PDF: {target}")


if __name__ == "__main__":
    main()
