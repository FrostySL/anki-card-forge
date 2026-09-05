"""Check image content inside the preview image, where Pillow is installed.

No fixed screenshot hashes or OCR/layout coordinates: compare only meaningful
relationships within one render, keeping Chromium/font upgrades reviewable.
"""
from pathlib import Path
import sys

from PIL import Image, ImageChops


def main():
    folder = Path(sys.argv[1])
    images = {}
    for path in sorted(folder.glob("*.png")):
        with Image.open(path) as image:
            image.load()  # Reject corrupt/incomplete PNGs, not just their headers.
            assert image.width >= 100 and image.height >= 20, f"Empty-sized image: {path}"
            rgb = image.convert("RGB")
            assert any(low != high for low, high in rgb.getextrema()), f"Blank image: {path}"
            images[path.name] = rgb
    for name, light in images.items():
        if name.endswith("-dark.png"):
            continue
        dark = images[name.removesuffix(".png") + "-dark.png"]
        assert light.size == dark.size, f"Themes changed card dimensions: {name}"
        assert ImageChops.difference(light, dark).getbbox(), f"Dark theme was not applied: {name}"
    for suffix in ("", "-dark"):
        first = images[f"09-occlusion-front{suffix}.png"]
        second = images[f"10-occlusion-front{suffix}.png"]
        assert first.size == second.size
        assert ImageChops.difference(first, second).getbbox(), "Hide-all targets are indistinguishable"
    print(f"PASS: {len(images)} complete, nonblank previews; both themes and distinct occlusion targets")


if __name__ == "__main__":
    main()
