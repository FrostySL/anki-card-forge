# Contributing

Use one short-lived branch per change and merge it into `main` through a pull
request. The same workflow applies to people and AI assistants.

## Branch and pull request

Start from an up-to-date `main` with a clean working tree:

```bash
git switch main
git pull --ff-only
git switch -c fix/describe-the-change
```

Use `feat/…` for features, `fix/…` for fixes, or `chore/…` for maintenance and
documentation. Keep related work in one branch; there is no separate `develop`
or release branch.

1. Make the change and run the relevant checks below.
2. Inspect `git diff`, stage only the intended files, and review
   `git diff --cached` before committing.
3. Push the branch and open a pull request:
   ```bash
   git push -u origin HEAD
   gh pr create
   ```
4. Describe the problem, the resulting behavior, and the tests actually run.
   Review the diff and wait for all required CI checks to pass on the current
   revision. Fix failures in the same branch.
5. Squash-merge the pull request, then return to `main` and update it:
   ```bash
   gh pr merge --squash --delete-branch
   git switch main
   git pull --ff-only
   ```

`main` accepts changes through pull requests; do not push directly or force-push
to it. Merged remote branches are deleted automatically. A second reviewer is
welcome but not required for this solo-maintained project. Passing checks does
not trigger a merge automatically; merge when the change is ready.

## Checks

Run the fast tests in Linux or WSL:

```bash
./tools/test.sh
```

On Windows 11 x64, run `.\forge.cmd setup`, then `.\forge.cmd test`.
The managed environment includes the real builder and decoder dependencies.
For a cold native acceptance test, run from a clean source copy:

```powershell
powershell -NoProfile -File tests/integration/windows_acceptance.ps1 -ReportDir C:\forge-reports
```

See the integration guide for its clean
archive, Sandbox and live Anki checks; report those results separately.

These use Python's standard library. Build smoke tests need `genanki` and skip
when it is unavailable; modern Anki package decoding also needs `zstd` or Python
`zstandard`. CI installs the dependencies to exercise those paths.

For shell or Dockerfile changes, also run the corresponding lint checks:

```bash
shellcheck -x tools/*.sh .githooks/pre-commit
for df in Dockerfile Dockerfile.*; do
  docker run --rm -i hadolint/hadolint hadolint - < "$df"
done
```

Run the Docker integration checks for changes to the corresponding tools.
The [integration guide](tests/integration/README.md) lists the required Docker
images; build the extraction and preview images before the visual check:

```bash
python3 tests/integration/check_pipeline.py build
python3 tests/integration/check_pipeline.py visual
```

The build check imports and renders a synthetic deck in the real Anki engine.
The visual check exercises extraction, OCR, and light/dark previews. Test inputs
are generated and contain no personal source material. Rendering checks do not
replace visually inspecting changed card layouts; use the preview workflow in
[AGENTS.md](AGENTS.md) for that.

[CI](.github/workflows/ci.yml) runs the full Python suite on Linux, a cold native
Windows setup and pipeline, the linters, the public-file policy, and the Docker
build check. Visual integration runs when relevant files change. The required
`CI passed` check combines these results, including visual integration whenever
it applies.

A change to card building or reworking must preserve the stable note-type IDs,
note GUIDs, and cloze numbering relied on by learned decks. Add regression tests
for changed behavior rather than only checking that a command exits successfully.
AnkiConnect CI tests use mocks; they do not connect to a desktop collection or
AnkiWeb. Report any manual integration tests separately.

## Keep personal material local

Enable the commit guard once per clone (`./tools/setup.sh` also does this):

```bash
git config core.hooksPath .githooks
```

Sources, extracts, generated decks, backups, and Anki collections stay local.
Only the repository's explicit public examples and documentation assets belong
in Git. If the guard rejects an intended public file, inspect it and adjust the
shared allowlist in `tools/check_repo_files.py` deliberately; do not bypass the
hook to make the commit pass.

The hook checks staged changes with `python3 tools/check_repo_files.py --staged`;
CI checks all tracked files with `python3 tools/check_repo_files.py --tracked`.
You can run either command directly.

CI can block an unsafe merge. It cannot prevent publication: a file pushed to a
branch in this public repository is already public before CI runs. Check staged
files before every commit and inspect the branch diff before pushing.
