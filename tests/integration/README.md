# Docker integration checks

Run from Linux/WSL with Docker Engine available:

```bash
python3 tests/integration/check_pipeline.py build
python3 tests/integration/check_pipeline.py visual
```

The `build` check uses `anki-cards` and `anki-cards-validate`. It calls the real
build and validation wrappers on an original synthetic deck: basic, reversed,
cloze, type-in, and both image-occlusion modes (8 notes / 10 cards). It verifies
embedded image bytes, note types, stable GUIDs and card ordinals across rebuilds,
and one intentional content update. The real Anki backend imports and renders
both package versions in temporary collections.

The `visual` check uses `anki-cards-extract` and `anki-cards-preview`. It generates
a small PDF with native text, an embedded diagram, and a raster-only scanned
page. It exercises folder preparation, OCR, text mirroring, the figure index and
figure cropping, then checks all 40 front/back previews in light and dark mode.
Assertions check successful rendering and distinct occlusion targets without
freezing exact screenshot pixels or OCR layout coordinates.

CI builds these four images before running the checks. Locally the build and
validation wrappers can build missing images; before running `visual`, build its
images with `docker build -f Dockerfile.extract -t anki-cards-extract .` and
`docker build -f Dockerfile.preview -t anki-cards-preview .`. Only Python's standard
library is required on the host; PDF/image dependencies come from those images.

Each run creates new gitignored `_ci-*` directories under `sources/`, `extracted/`
and `decks/` (deck directories end in `_rebuild`). Successful runs remove their
fixtures. Use `--keep-fixtures` to inspect the results; failures always retain
and print their output paths. No source materials, running Anki instance,
AnkiConnect connection, credentials, or network-dependent card content are used.
