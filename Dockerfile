FROM python:3.12-slim

# genanki erzeugt die .apkg-Dateien
RUN pip install --no-cache-dir "genanki==0.13.1"

# Das Projekt (inkl. tools/, quellen/, decks/) wird zur Laufzeit nach /work
# gemountet. So wirken Aenderungen am Skript sofort, ohne Image-Neubau.
WORKDIR /work
ENTRYPOINT ["python", "/work/tools/build_deck.py"]
