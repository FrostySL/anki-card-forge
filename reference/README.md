# reference/ — local reference material (not in the repo)

This folder serves Claude as a **reference** on Anki. The content is
**third-party code with its own license** and is therefore **not** versioned
here (see `.gitignore`) — only this note file is.

If you want the reference material locally (optional, purely for lookup; not
needed for card generation itself):

```bash
# Anki source code (AGPL-3.0) — a shallow clone is enough
git clone --depth 1 https://github.com/ankitects/anki reference/anki

# Anki manual
git clone --depth 1 https://github.com/ankitects/anki-manual reference/anki-manual
```

> **License note:** Anki is licensed under the **GNU AGPL-3.0**. This project
> uses **no** Anki source code — it produces `.apkg` files exclusively via the
> [`genanki`](https://github.com/kerrickstaley/genanki) library (MIT). The
> content under `reference/` is purely local lookup material.
