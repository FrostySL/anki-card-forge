"""Verify actual raster/vector crops and manifest coordinates on rotated PDFs."""
import json
from pathlib import Path
import sys
import tempfile

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import figextract


def main():
    with tempfile.TemporaryDirectory(prefix="acf-rotation-") as directory:
        root = Path(directory)
        for kind in ("vector", "raster"):
            for rotation in (0, 90, 180, 270):
                with fitz.open() as document:
                    page = document.new_page(width=400, height=600)
                    bounds = fitz.Rect(40, 80, 240, 240)
                    if kind == "vector":
                        page.draw_rect(bounds, color=(1, 0, 0), fill=(1, 0, 0))
                    else:
                        pixels = fitz.Pixmap(fitz.csRGB, 80, 64, bytes([255, 0, 0]) * 80 * 64, False)
                        page.insert_image(bounds, stream=pixels.tobytes("png"))
                    page.set_rotation(rotation)
                    expected = bounds * page.rotation_matrix
                    page_bounds = page.rect
                    pdf = root / f"{kind}-{rotation}.pdf"
                    document.save(pdf)
                output = root / f"{kind}-{rotation}"
                assert figextract.extract(str(pdf), str(output), zoom=1) == 1
                manifest = json.loads((output / (pdf.stem + ".figures.json")).read_text())
                figure, = manifest["figures"]
                assert figure["kind"] == kind
                for name, value in figextract._frac(expected, page_bounds).items():
                    assert abs(figure[name] - value) < .0002, (rotation, name, figure)
                crop = fitz.Pixmap(figure["image"])
                samples = crop.samples
                red = sum(samples[i] > 240 and samples[i + 1] < 15 and samples[i + 2] < 15
                          for i in range(0, len(samples), crop.n))
                assert red / (crop.width * crop.height) > .98, (kind, rotation, "wrong crop")
    print("PASS: raster/vector crops and coordinates at 0, 90, 180 and 270 degrees")


if __name__ == "__main__":
    main()
