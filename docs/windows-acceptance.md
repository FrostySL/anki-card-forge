# Windows acceptance evidence

Windows acceptance, 5 September 2026. All inputs in these checks are
synthetic; personal collection exports and diagnostic files remain local.

| Check | Result |
|---|---|
| Native setup on the Windows 11 x64 development host | Passed, including OCR, browser, local MathJax and real Anki backend |
| Full setup repeated with `--offline` | Passed without downloads |
| Executable, package and loaded C++ DLL provenance | Passed: project `.forge/` and `.venv/` |
| Synthetic all-types build | Passed: 8 notes, 10 cards, no render errors |
| Multiple-input `finish` | Passed: 9 notes, 11 cards, real Anki validation |
| Native PDF and scanned PDF preparation | Passed, including parallel extraction, OCR, figures and four detected labels |
| German OCR on the native development host | Passed with `deu` and `eng+deu`, including exact recognition of umlauts and ß |
| Light/dark card previews | Passed: 40 PNGs, with Unicode media paths |
| Offline formula previews | Passed: four PNGs, SVG mathematics and a dynamically loaded local `cancel` extension |
| MathJax failure cases | Passed: missing extension fails; literal TeX inside code/pre remains literal |
| Portable names and repository guard | Passed: reserved names, case/Unicode collisions, local runtime protection |
| Launcher without Python on PATH | Passed: actual inbox PowerShell, Unicode/space folder, read-only doctor/help, explicit empty-cache offline failure |
| Native Windows Python suite | Passed: 265 tests in the source-only Sandbox, 20 expected Git/platform skips; Git guards run separately in CI |
| Tesseract Unicode paths | Passed: relative model paths and streamed label OCR with Unicode source/TEMP; three expected labels retained |
| Linux Python, shell and Docker integration | Passed in GitHub CI, including real Anki, PDF/OCR and formula previews |
| Clean source archive on GitHub Windows CI | Passed: cold bootstrap, provenance, full tests, offline repeat and separate Git guards |
| Clean Windows Sandbox, standard user, guest network disabled on repeat | Passed: cold setup 223.8 seconds, offline repeat 60.2 seconds, no setup interventions |

## Hosted Windows CI

The [successful CI run](https://github.com/FrostySL/anki-card-forge/actions/runs/33973857518)
tested implementation revision `0b96ed4`. A source-only archive in
`D:\a\_temp\Anki Test ä` started with no Python, uv, Docker, Git or Tesseract
discoverable on PATH and no project caches. Cold setup took **60.6 seconds**;
the offline repeat took **31.9 seconds**. The complete acceptance driver took
107.3 seconds, with no manual intervention. The resulting dependency cache was
713,277,204 bytes; these hosted-run timings depend on the runner and network.

Provenance confirmed the interpreter, all eight checked modules and the three
loaded Microsoft C++ runtime DLLs came from `.forge/` or `.venv/`. Both setup
passes ran the complete synthetic build and visual pipeline. The source-only
suite passed; Git-specific tests ran separately with Git available.

The hosted process was elevated and its offline check used downloader flags.
The separate Sandbox result below proves standard-user setup and a repeat with
the guest network adapter disabled. Current-revision status is visible in
[PR #4's checks](https://github.com/FrostySL/anki-card-forge/pull/4/checks).

## Clean Windows Sandbox

The clean archive and its ZIP comment both identify the tested revision as
`9daec679a21ac1083af672abb255c5209fcb21b5`. The guest ran Windows build 26100;
the project and all runtimes lived inside `C:\Users\Public\Anki Test ä`.
The actual driver ran as `ACFStandardTest` with `elevated: false`. Preflight
found no Python, uv, Git, Docker or Tesseract on PATH and no project caches.

Cold setup passed in **223.8 seconds**. The complete source-only suite then
passed **265 tests**, with 20 expected skips: 15 require Git, four require POSIX,
and one requires unavailable Windows symlink privileges. The guest coordinator
disabled its Ethernet adapter; matching request/acknowledgement nonces confirm
isolation before the standard-user driver repeated setup. This offline repeat
passed in **60.2 seconds**, reusing installed components without downloads,
package repairs or browser reinstallation. No manual setup intervention or
administrator prompt was needed by the product setup.

Both runs completed the all-types and multiple-input builds, real Anki
validation, text/scanned PDF processing, English OCR, label/figure
extraction, 40 light/dark previews and four formula previews. Formula checks
proved rendered SVG mathematics and dynamic local extensions, including failure
when an extension is missing. Final doctor reported no issues and verified all
32 installed packages and both German/English OCR language packs. Provenance
confirmed the interpreter, all eight checked
modules and three loaded Microsoft runtime DLLs came from the guest project's
`.forge/` and `.venv/` directories.

The full driver took **354.1 seconds**; its final cache occupied 713,277,377
bytes. These timings depend on hardware and network conditions. The closed
transcript, matching successful result/completion records, setup state, doctor,
provenance and network-isolation reports were copied back without a coordinator
error. The complete logs and synthetic artifacts remain local.

A separate focused native-host test used German text images with `--lang deu`
and `--lang eng+deu`. Both recognized the exact phrases `Zellkern steuert die Zelle`
and `Übertragung und Größe`, including umlauts and ß. This confirms German OCR
in addition to the English synthetic pipeline and the language-pack integrity
checks in Sandbox.

Earlier cold attempts exposed missing public CA roots and a generated Chromium
`debug.log` being mistaken for immutable payload. The fixes retain TLS
certificate/hostname checks and add the locked certifi roots; browser integrity
now verifies all 601 shipped files against the pinned ZIP payloads. Regression
tests reject damaged DLLs while allowing diagnostic logs to change. A separate
offline migration from the old inventory also passed the complete pipeline.

After this Sandbox candidate, integration of the existing `main` update changed
only the four Linux Docker base-image lines to Python 3.14. Native Windows code,
the manifest, lockfile and test harness remained identical. The combined
revision `ed63a8f` passed [all CI checks](https://github.com/FrostySL/anki-card-forge/actions/runs/33980750792),
including Linux Docker build/OCR/preview and cold Windows setup. Subsequent
acceptance-documentation changes are also checked on the PR's final revision.

## Live Anki profile test

In the explicitly selected `test` profile, a unique
`Windows acceptance::<nonce>` deck was imported: four notes and six cards
(basic with image, reversed basic, two-cloze note, type-in). The basic, one
reversed card and one cloze card were reviewed in the Anki GUI.

A fresh export with scheduling was decoded; the basic answer and cloze HTML
wrapper were changed while preserving the cloze tokens. Rebuild and strict
diff reported **zero added, zero removed, two changed notes and zero cloze
warnings**. Real Anki validation passed before the update import.

After importing with automatic backup, a second fresh export proved that
note GUIDs, note IDs/types, card IDs/ordinals, scheduling fields and all three
review-history records were unchanged. The two intended field changes matched
the verified package, and the automatic backup contained the learned state.
There was no sync or prune. The synthetic test deck remains in the profile.

Image-occlusion was verified separately in the build and visual suite; the
decoder's existing image-occlusion limitation excludes it from this rework test.

## Completion gate

Development-host results do not replace clean Windows acceptance. Merge requires
review of the candidate diff, green required CI at its current revision, and
the documented Sandbox result. See the [test procedures](../tests/integration/README.md).
