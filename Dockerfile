FROM python:3.12-slim

# genanki produces the .apkg files
RUN pip install --no-cache-dir "genanki==0.13.1"

# The project (incl. tools/, sources/, decks/) is mounted to /work at runtime.
# Script changes therefore take effect immediately, without rebuilding the image.
WORKDIR /work
ENTRYPOINT ["python", "/work/tools/build_deck.py"]
