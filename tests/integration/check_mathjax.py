"""Prove a missing local TeX extension fails instead of producing raw formulas."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
if os.name == "nt":
    import native_setup
    os.environ.update(native_setup.environment(ROOT))
import preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="acf-missing-mathjax-") as temporary:
        # All prerequisites work, but the dynamically requested cancel extension
        # is deliberately absent. Installed project assets remain untouched.
        directory = Path(temporary) / "es5"
        shutil.copytree(preview.mathjax_directory(), directory, ignore=shutil.ignore_patterns("cancel.js"))
        with preview.sync_playwright() as playwright:
            in_container = os.environ.get("ACF_PREVIEW_CONTAINER") == "1" or Path("/.dockerenv").exists()
            browser = playwright.chromium.launch(chromium_sandbox=not in_container)
            try:
                context = browser.new_context()
                context.route("**/*", lambda route: route.abort())
                page = context.new_page()
                failures = preview.configure_mathjax(page)
                literal = r"\(\frac{1}{2}\)"
                page.set_content(preview._MATHJAX + f"<pre>{literal}</pre><code>{literal}</code>")
                assert preview.render_math(page, failures) == 0, "Literal TeX was typeset."
                assert page.locator("pre").text_content() == literal
                assert page.locator("code").text_content() == literal
                page.set_content(preview._MATHJAX + r"\(\sqrt{4}\)")
                assert preview.render_math(page, failures) >= 1, "Actual formula was not typeset."
                page.close()
                page = context.new_page()
                failures = preview.configure_mathjax(page, directory=directory)
                page.set_content(preview._MATHJAX + r"\[\require{cancel}\cancel{x}\]")
                try:
                    preview.render_math(page, failures)
                except Exception:
                    assert any("input/tex/extensions/cancel.js" in item for item in failures), failures
                else:
                    raise AssertionError("Missing TeX extension was silently accepted.")
            finally:
                browser.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"passed": True, "literal_tex_preserved": True, "formula_rendered": True,
                                     "missing_component": "input/tex/extensions/cancel.js",
                                     "errors": failures}, indent=2) + "\n", encoding="utf-8")
    print("PASS: literal TeX preserved; formulas render; missing local extension fails explicitly")


if __name__ == "__main__":
    main()
