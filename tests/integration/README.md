# Integration and clean Windows acceptance

The checks generate original synthetic inputs. They never read personal topic
files or contact AnkiConnect. Run with Docker in Linux/WSL, or with the managed
native Windows environment:

```bash
python3 tests/integration/check_pipeline.py build
python3 tests/integration/check_pipeline.py visual
```

```powershell
.\.venv\Scripts\python.exe tests\integration\check_pipeline.py build --backend native
.\.venv\Scripts\python.exe tests\integration\check_pipeline.py visual --backend native
```

The default backend remains Docker. `build` uses `anki-cards` and
`anki-cards-validate`; `visual` uses `anki-cards-extract` and
`anki-cards-preview`. CI builds these images. Locally, build extraction and
preview images with `docker build -f Dockerfile.extract -t anki-cards-extract .`
and `docker build -f Dockerfile.preview -t anki-cards-preview .`.

`build` runs the public finish command on basic, reversed, cloze, type-in and
both image-occlusion modes (8 notes / 10 cards). It checks embedded image bytes,
note types, GUIDs and card ordinals across identical rebuilds and an intentional
field update. A second source-grounded input exercises finish's coverage and
bundled-package path (9 notes / 11 cards). Both versions import and render in
temporary collections using the real Anki engine.

`visual` prepares a generated two-page PDF with native text, an embedded diagram
and a raster-only page requiring OCR. Two page workers exercise Windows process
spawning. It checks text mirroring, figure indexing/cropping, label OCR and all
40 front/back previews in light and dark mode. A separate formula card renders
four previews offline. Its render report must prove typesetting and a locally
fulfilled `cancel.js` extension request. PNG assertions reject blank/corrupt
images, missing themes and identical hide-all targets without fixed pixel hashes.
An isolated MathJax check preserves literal TeX in `pre`/`code`, renders actual
formulas, and verifies that a missing `cancel.js` fails explicitly. It copies
assets to a temporary directory without changing the installed runtime.

Each run owns new gitignored `_ci-..._rebuild` directories under `sources/`,
`extracted/` and `decks/`. Successful runs clean up only these directories;
failures retain them. Add `--keep-fixtures` to inspect successful results.
Automated rendering checks do not replace visual inspection of changed layouts.

## Cold bootstrap and offline repeat

`windows_acceptance.ps1` runs from a **fresh source-only copy**, including one
extracted from a Git archive or GitHub source ZIP. It rejects existing `.forge`
and `.venv` directories, removes host runtime discovery from the process
environment, and calls `forge.cmd setup`. Only Windows PowerShell is needed.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\integration\windows_acceptance.ps1 -ReportDir C:\Temp\acf-reports
```

Setup must complete native build and visual checks. The driver then runs the
Python suite, asserts package/interpreter provenance and the loaded Visual C++
DLL paths, and repeats setup with downloader offline flags. That repeat must reuse installed
components and pass integration again. Reports include timings, logs, preflight,
doctor and provenance results, plus synthetic failure artifacts. The execution
policy flag applies to this process only; persistent Windows policy is unchanged.

Windows CI runs the driver without a setup-python action or dependency cache,
in an archive path containing spaces and a non-ASCII character. It tests the
Git-dependent guards separately with Git available. POSIX-only tests remain in
Linux CI. Hosted machines still include system libraries: the clean Sandbox
run remains a separate acceptance requirement.

## Windows Sandbox: actual clean, standard-user test

Commit the candidate revision first, then prepare its source-only archive:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\integration\prepare_windows_sandbox.ps1
```

The helper prints an `acceptance.wsb` path under an owned local
`decks/_sandbox-..._rebuild` directory. It archives **HEAD**, so uncommitted fixes
are excluded. It records that exact commit and never enables Windows features,
launches the Sandbox, or restarts the host.

Launch the generated `.wsb` once Sandbox is available. The archive directory is
shared read-only and only a dedicated reports directory is writable. Workspace
and runtime stay in the guest. The guest harness creates a temporary local
standard user and runs acceptance under that account, asserting its actual
process is not elevated. The normal Sandbox logon account is an administrator:
running setup as that account alone would not establish the no-admin claim.
No account is created on the host.

Sandbox receives networking for first downloads and 6 GB RAM. Before the second
setup, the privileged guest coordinator disables every active guest network
adapter and acknowledges this to the standard-user driver. The repeat therefore
runs without network access; its evidence is saved in `network-isolated.json`.
Hosted CI uses downloader offline flags, without changing its network adapters.
The coordinator retains partial reports on failure, rejects artifact junctions
and symlinks, and stops its guest test process after 45 minutes. Close the Sandbox
only after `reports/result.json` or `reports/sandbox-error.txt` is copied back. The
helper itself must be tested on the target Windows build; a generated `.wsb`
does not establish success. Feature activation may require host administrator
consent and a reboot, separately from product setup's standard-user requirement.

See Microsoft's [installation instructions](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-install)
and [configuration reference](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file).

## Optional live Anki test profile

`live_anki_acceptance.py` is **never invoked by setup or CI**. Its explicit phases
use a unique synthetic deck in the locally running Anki test profile. Confirm
the GUI profile is `test` before either importing phase. No phase syncs, prunes,
disables backups, or removes the test deck afterward.

```powershell
.\.venv\Scripts\python.exe tests\integration\live_anki_acceptance.py prepare
# Use the directory printed above for every subsequent phase:
.\.venv\Scripts\python.exe tests\integration\live_anki_acceptance.py import --directory <directory> --profile-confirmed test
# Review one basic and one cloze card in this unique deck in Anki.
.\.venv\Scripts\python.exe tests\integration\live_anki_acceptance.py rework --directory <directory>
.\.venv\Scripts\python.exe tests\integration\live_anki_acceptance.py push --directory <directory> --profile-confirmed test
.\.venv\Scripts\python.exe tests\integration\live_anki_acceptance.py verify --directory <directory>
```

`prepare` builds and validates 4 notes / 6 cards without contacting Anki.
`rework` exports the current learned deck with scheduling, decodes that fresh
export, changes a basic answer and only cloze surroundings, and checks the diff,
GUIDs, note types and ordinals before validation and a push dry-run. `push`
keeps the automatic backup. `verify` compares exported card IDs, scheduling and
review history, checks intended fields, and decodes the backup. Results go to
`verification.json` in the owned directory.

The live fixture excludes occlusion because the decoder cannot reconstruct
those notes. Occlusion stability is covered by the all-types package snapshots.
Report live Anki and Sandbox results separately from CI: neither is established
by mocked AnkiConnect tests.
