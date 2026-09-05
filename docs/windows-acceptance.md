# Windows acceptance evidence

Development verification, 5 September 2026. All inputs in these checks are
synthetic; personal collection exports and diagnostic files remain local.

| Check | Result |
|---|---|
| Native setup on the Windows 11 x64 development host | Passed, including OCR, browser, local MathJax and real Anki backend |
| Full setup repeated with `--offline` | Passed without downloads |
| Executable, package and loaded C++ DLL provenance | Passed: project `.forge/` and `.venv/` |
| Synthetic all-types build | Passed: 8 notes, 10 cards, no render errors |
| Multiple-input `finish` | Passed: 9 notes, 11 cards, real Anki validation |
| Native PDF and scanned PDF preparation | Passed, including parallel extraction, German/English OCR, figures and four detected labels |
| Light/dark card previews | Passed: 40 PNGs, with Unicode media paths |
| Offline formula previews | Passed: four PNGs, SVG mathematics and a dynamically loaded local `cancel` extension |
| MathJax failure cases | Passed: missing extension fails; literal TeX inside code/pre remains literal |
| Portable names and repository guard | Passed: reserved names, case/Unicode collisions, local runtime protection |
| Launcher without Python on PATH | Passed: actual inbox PowerShell, Unicode/space folder, read-only doctor/help, explicit empty-cache offline failure |
| Native Windows Python suite | Passed: 259 tests, five platform-specific skips; includes duplicate-case environment and Unicode OCR regressions |
| Tesseract Unicode paths | Passed: relative model paths and streamed label OCR with Unicode source/TEMP; three expected labels retained |
| Linux Python, shell and Docker integration | Passed in GitHub CI, including real Anki, PDF/OCR and formula previews |
| Clean source archive on GitHub Windows CI | Pending candidate CI run |
| Clean Windows Sandbox, standard user, guest network disabled on repeat | Feature enabled; pending host restart and candidate run |

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
