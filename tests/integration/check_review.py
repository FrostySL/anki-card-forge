"""Exercise the native review in a real Windows browser after forge.cmd setup."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urljoin, urlsplit

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]


def command(source, *args):
    return [str(ROOT / "forge.cmd"), "review", str(source.relative_to(ROOT)), *args]


@contextmanager
def server(source, log, *options):
    with log.open("wb") as output:
        process = subprocess.Popen(command(source, *options), cwd=ROOT, stdout=output, stderr=output)
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                lines = log.read_text(encoding="utf-8", errors="replace")
                if process.poll() is not None:
                    raise RuntimeError(f"Review server exited ({process.returncode}):\n{lines}")
                address = re.search(r"http://127\.0\.0\.1:\d+/[^\s]*", lines)
                if address:
                    yield address[0]
                    return
                time.sleep(0.1)
            raise TimeoutError(f"Review server failed to start. See {log}")
        finally:
            if process.poll() is None:
                # forge.cmd starts PowerShell and Python children. Stop our own tree.
                subprocess.run(["taskkill", "/t", "/f", "/pid", str(process.pid)],
                               check=True, stdout=subprocess.DEVNULL)
            process.wait(timeout=15)


def open_page(browser, url, width, locale="de-DE"):
    context = browser.new_context(locale=locale, viewport={"width": width, "height": 820},
                                  permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(url)
    expect(page.locator("#review")).to_be_visible()
    return page


def check_layout(page, narrow):
    """Check loaded PNGs and actual layout in CSS pixels rather than CSS rules."""
    expect(page.locator(".previews")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#zoom-front")).to_be_enabled()
    for side in ("front", "back"):
        image = page.locator("#" + side)
        image.evaluate("(image) => image.decode()")
        assert image.evaluate("(image) => image.naturalWidth") > 0
    front = page.locator("#front").bounding_box()
    back = page.locator("#back").bounding_box()
    assert front and back
    if narrow:
        assert back["y"] >= front["y"] + front["height"] - 1, (front, back)
    else:
        assert back["x"] >= front["x"] + front["width"] - 1, (front, back)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def state(page):
    return page.evaluate("async () => (await fetch('api/state')).json()")


LANGUAGES = ("de", "en", "es", "fr", "pt-BR", "zh-Hans")


def messages(language):
    path = ROOT / "tools" / "review_ui" / "locales" / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def choose_language(page, language):
    page.locator("select#ui-language").select_option(language)
    expect(page.locator("html")).to_have_attribute("lang", language)
    return messages(language)


def check_languages(browser, url, work):
    assert not urlsplit(url).query
    for locale in ("fr-CA", "zh-SG"):
        page = open_page(browser, url, 390, locale)
        expect(page.locator("#ui-language")).to_have_value("en")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.context.close()

    page = open_page(browser, url + "?view=card%20review&lang=es-MX#karte=note-1%3Ac1", 320, "de-DE")
    expect(page.locator("#ui-language")).to_have_value("es")
    fragment = urlsplit(page.url).fragment
    assert parse_qs(fragment)["karte"] == ["note-1:c1"]
    assert set(page.locator("#ui-language option").evaluate_all("opts => opts.map(o => o.value)")) == set(LANGUAGES)
    before = state(page)
    writes = []
    page.on("request", lambda request: writes.append(request.url) if request.method == "POST" else None)
    text = "Unverändert: acción, révision, português, 原样。"
    page.locator("#comment").fill(text)
    page.locator("#comment").evaluate("el => el.setSelectionRange(1, 5)")
    for language in LANGUAGES:
        msg = choose_language(page, language)
        location = urlsplit(page.url)
        assert parse_qs(location.query) == {"view": ["card review"], "lang": [language]}
        assert location.fragment == fragment
        expect(page).to_have_title(msg["deckTitle"].format(deck=before["deck"]))
        expect(page.locator("#card-status")).to_have_text(msg["open"])
        expect(page.locator("#card-heading")).to_have_text(msg["cardHeading"].format(number=1, total=2))
        expect(page.get_by_role("progressbar")).to_have_attribute("aria-label", msg["progressName"])
        expect(page.locator("#zoom-front")).to_have_attribute("aria-label", msg["zoomFront"])
        expect(page.locator("#ui-language")).to_have_accessible_name(msg["language"])
        expect(page.locator("#save-status")).to_have_text(msg["unsaved"])
        expect(page.locator("#comment")).to_have_value(text)
        assert page.locator("#comment").evaluate("el => [el.selectionStart,el.selectionEnd]") == [1, 5]
        for side in ("front", "back"):
            expect(page.locator("#" + side)).to_have_attribute("src", re.compile(re.escape(before["cards"][0][side]) + "$"))
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), language
    assert not writes and state(page) == before
    page.screenshot(path=work / "language-narrow.png", full_page=True)
    # A bare URL reuses the manual choice. A new chat link overrides it.
    clean = page.context.new_page()
    clean.goto(url)
    expect(clean.locator("#ui-language")).to_have_value("zh-Hans")
    for tag, expected in (("nl-NL", "en"), ("zh-Hant-TW", "en"), ("zh-TW", "en"),
                          ("pt-PT", "pt-BR"), ("zh-SG", "zh-Hans"), ("fr-CA", "fr")):
        clean.goto(url + "?lang=" + tag)
        expect(clean.locator("#review")).to_be_visible()
        expect(clean.locator("#ui-language"), f"Review language for {tag} at {clean.url}").to_have_value(expected)
        expect(clean.locator("#card-status")).to_have_text(messages(expected)["open"])
    choose_language(clean, "de")
    assert parse_qs(urlsplit(clean.url).query) == {"lang": ["de"]}
    clean.reload()
    expect(clean.locator("#ui-language")).to_have_value("de")
    expect(clean.locator("#card-status")).to_have_text(messages("de")["open"])
    check_language_history(clean, url)
    expect(page.locator("#comment")).to_have_value(text)
    page.context.close()


def check_language_history(page, url):
    def check_card(language, number):
        expect(page.locator("#card-heading")).to_have_text(messages(language)["cardHeading"].format(number=number, total=2))
        expect(page.locator("#ui-language")).to_have_value(language)
        expect(page.locator("html")).to_have_attribute("lang", language)
        assert parse_qs(urlsplit(page.url).query) == {"lang": [language]}, page.url

    page.goto(url + "?lang=fr")
    check_card("fr", 1)
    page.locator("#card-heading").focus()
    page.keyboard.press("ArrowRight")  # Browse to card two without confirming card one.
    check_card("fr", 2)
    choose_language(page, "es")
    check_card("es", 2)
    page.go_back()
    check_card("es", 1)
    page.reload()
    check_card("es", 1)
    page.go_forward()
    check_card("es", 2)
    page.goto(url + "?lang=fr")
    check_card("fr", 1)


def check_localized_handoff(page, path):
    original = path.read_bytes()
    before = state(page)
    page.set_viewport_size({"width": 320, "height": 844})
    for language in LANGUAGES:
        msg = choose_language(page, language)
        expect(page.locator("#finish-heading")).to_have_text(msg["submitted"])
        expect(page.locator("#submission-path")).to_have_text(str(path))
        page.locator("#copy").click()
        expect(page.locator("#copy")).to_have_text(msg["copied"])
        assert page.evaluate("() => navigator.clipboard.readText()") == msg["handoffPrompt"].format(path=path)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), language
    assert path.read_bytes() == original and state(page) == before
    choose_language(page, "de")


def overview_filter(page, status, count):
    button = page.locator(f'[data-filter="{status}"]')
    expect(button).to_contain_text(re.compile(rf"\b{count}\b"))
    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")
    rows = page.locator("#overview [data-card-id]")
    expect(rows).to_have_count(count)
    return rows


def check_routing_and_shortcuts(page):
    heading = page.locator("#card-heading")
    comment = page.locator("#comment")
    heading.focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#variant")).to_contain_text("c3")
    assert not state(page)["feedback"], "Arrow browsing confirmed an untouched card"
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#variant")).to_contain_text("c1")
    page.keyboard.press("c")
    expect(comment).to_be_focused()
    comment.fill("Zum Hashwechsel merken.")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#variant")).to_contain_text("c1")
    heading.focus()
    page.keyboard.press("p")
    expect(comment).to_have_value("Zum Hashwechsel merken.")
    expect(page.locator("#variant")).to_contain_text("c1")
    previous = page.evaluate("location.hash")
    overview = "#ansicht=uebersicht&filter=change_requested"
    page.route("**/api/save", lambda route: route.fulfill(status=503), times=1)
    page.evaluate("hash => { location.hash = hash }", overview)
    expect(page.get_by_role("alert")).to_be_visible()
    expect(comment).to_have_value("Zum Hashwechsel merken.")
    expect(page.locator("#variant")).to_contain_text("c1")
    assert page.evaluate("location.hash") == previous
    page.evaluate("hash => { location.hash = hash }", overview)
    expect(page.locator("#overview")).to_be_visible()
    expect(page.locator("[data-card-id]").first).to_contain_text("Zum Hashwechsel merken.")
    page.evaluate("history.back()")
    expect(comment).to_have_value("Zum Hashwechsel merken.")
    expect(comment).to_be_visible()
    page.evaluate("history.forward()")
    expect(page.locator("#overview")).to_be_visible()
    page.evaluate("location.hash = '#karte=note-1%3Ac1'")
    expect(page.locator("#card-view")).to_be_visible()
    expect(page.locator("#variant")).to_contain_text("c1")
    heading.focus()
    # Playwright's keyboard mapper uses a US layout. Dispatch the key value a
    # German layout supplies to the browser for the alternate letter shortcut.
    heading.dispatch_event("keydown", {"key": "ä", "bubbles": True})
    expect(comment).to_be_focused()


def check_preview(page, work):
    data = state(page)["cards"][1]
    previews = page.locator(".previews")
    colors = {}
    for theme in ("light", "dark"):
        button = page.locator(f'#preview-theme [data-theme="{theme}"]')
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        expect(previews).to_have_attribute("data-theme", theme)
        colors[theme] = []
        for side in ("front", "back"):
            image = page.locator("#" + side)
            path = data[side + "_light" if theme == "light" else side]
            expect(image).to_have_js_property("src", urljoin(page.url, path))
            image.evaluate("img => img.decode()")
            # Sample the actual decoded background, independent of file names.
            pixel = image.evaluate("""img => {
                const ctx = document.createElement("canvas").getContext("2d");
                ctx.drawImage(img, 0, 0);
                return ctx.getImageData(0, 0, 1, 1).data[0];
            }""")
            colors[theme].append(pixel)
            zoom = page.locator("#zoom-" + side)
            zoom.click()
            dialog = page.get_by_role("dialog")
            expect(dialog).to_be_visible()
            assert image.evaluate("""img => {
                const copy = document.createElement("canvas");
                copy.width = img.naturalWidth;
                copy.height = img.naturalHeight;
                copy.getContext("2d").drawImage(img, 0, 0);
                return copy.toDataURL() === document.querySelector("#zoom-image").toDataURL();
            }"""), "Zoom displays different pixels from the selected card face"
            area = page.locator("#zoom-scroll")
            assert area.evaluate("n => n.scrollWidth <= n.clientWidth + 1")
            if theme == "light" and side == "front":
                page.screenshot(path=work / "zoom-narrow.png")
                page.keyboard.press("ArrowLeft")
                expect(page.locator("#variant")).to_contain_text("c3")
                page.locator("#zoom-size").click()
                expect(page.locator("#zoom-size")).to_be_focused()
                page.locator("#zoom-size").click()
                assert area.evaluate("n => n.scrollWidth <= n.clientWidth + 1")
            page.keyboard.press("Escape")
            expect(dialog).to_be_hidden()
            expect(zoom).to_be_focused()
    assert all(light > dark + 100 for light, dark in zip(colors["light"], colors["dark"])), colors
    # A switch immediately followed by navigation still has to display the
    # requested theme for the new variant on both sides.
    page.locator('#preview-theme [data-theme="light"]').click()
    page.locator("#card-heading").focus()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#variant")).to_contain_text("c1")
    expect(previews).to_have_attribute("aria-busy", "false")
    first = state(page)["cards"][0]
    for side in ("front", "back"):
        expect(page.locator("#" + side)).to_have_attribute("src", re.compile(re.escape(first[side + "_light"]) + "$"))
    page.locator('#preview-theme [data-theme="dark"]').click()
    page.locator("#card-heading").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#variant")).to_contain_text("c3")
    expect(previews).to_have_attribute("aria-busy", "false")


def check_progress(page, counts):
    bar = page.get_by_role("progressbar")
    checked = counts["accepted"] + counts["change_requested"]
    total = sum(counts.values())
    expect(bar).to_have_attribute("aria-valuenow", str(checked))
    expect(bar).to_have_attribute("aria-valuemax", str(total))
    for detail in (f"{counts['accepted']} pass", f"{counts['change_requested']} mit Änderungswunsch",
                   f"{counts['open']} offen"):
        assert detail in bar.get_attribute("aria-valuetext")
    expect(bar.locator("rect")).to_have_count(1)
    fill = bar.locator("#progress-fill")
    track_width = bar.locator("svg").bounding_box()["width"]
    fill_width = fill.evaluate("el => el.getBoundingClientRect().width")
    assert track_width > 100 and abs(fill_width - track_width * checked / total) < 2
    red, green, blue = map(int, re.findall(r"\d+", fill.evaluate("el => getComputedStyle(el).fill")))
    assert red > green > blue, "Expected one orange progress indicator"


def submit(page):
    expect(page.locator("#overview")).to_be_visible()
    page.get_by_role("button", name="Review abschicken").click()
    expect(page.locator("#copy")).to_be_visible()


def copy_submitted_path(page):
    copy = page.locator("#copy")
    copy.click()
    expect(copy).to_contain_text("Kopiert")
    prompt = page.evaluate("() => navigator.clipboard.readText()")
    prefix, suffix = messages("de")["handoffPrompt"].split("{path}")
    assert prompt.startswith(prefix) and prompt.endswith(suffix), prompt
    path = Path(prompt.removeprefix(prefix).removesuffix(suffix))
    assert path.is_absolute() and path.is_file(), path
    details = page.locator("#submission-file")
    expect(details).to_have_js_property("open", False)
    expect(page.locator("#submission-path")).to_be_hidden()
    details.locator("summary").click()
    expect(page.locator("#submission-path")).to_have_text(str(path))
    details.locator("summary").click()
    expect(copy).to_have_text("Prompt kopieren", timeout=5000)
    return path


def check_handoff_revision(document, source):
    workspace = Path(document["review_project_root"])
    assert workspace == ROOT and Path(document["source"]) == source
    revision = subprocess.check_output(
        [str(workspace / "forge.cmd"), "review", str(source), "--show-revision"],
        cwd=workspace, text=True, encoding="utf-8", timeout=30).strip()
    assert revision == document["revision"] == document["current_revision_at_submission"]


COMMENTS = ["Einheiten bei der ersten Lücke ausschreiben.", "Für Millimeter ein Beispiel ergänzen."]
LEGACY_COMMENT = "Passt, das Zahlenbeispiel ist hilfreich."
REVISED_COMMENT = "Bitte die erste Einheit ausschreiben."


def first_pass(browser, url, work):
    page = open_page(browser, url, 1200)
    check_layout(page, narrow=False)
    check_progress(page, {"accepted": 0, "change_requested": 0, "open": 30})
    expect(page.locator("#submit")).to_be_hidden()
    page.screenshot(path=work / "editor-wide.png", full_page=True)
    check_routing_and_shortcuts(page)
    other = open_page(browser, url + "#karte=note-1%3Ac1", 1200)
    other.locator("#comment").fill("Eingabe im zweiten Fenster.")
    page.locator("#comment").fill(COMMENTS[0])
    page.get_by_role("button", name="Speichern und weiter", exact=True).click()
    expect(page.locator("#variant")).to_contain_text("c3")
    with other.expect_response(lambda r: r.url.endswith("/api/save") and r.status == 409):
        other.get_by_role("button", name="Speichern und weiter", exact=True).click()
    expect(other.get_by_role("alert")).to_contain_text(COMMENTS[0])
    expect(other.locator("#comment")).to_have_value("Eingabe im zweiten Fenster.")
    expect(other.locator("#variant")).to_contain_text("c1")
    spanish = choose_language(other, "es")
    expect(other.get_by_role("alert")).to_contain_text(spanish["cardConflict"])
    expect(other.get_by_role("alert")).to_contain_text(COMMENTS[0])
    expect(other.locator("#comment")).to_have_value("Eingabe im zweiten Fenster.")
    other.context.close()
    page.set_viewport_size({"width": 390, "height": 844})
    check_layout(page, narrow=True)
    check_preview(page, work)
    page.locator("#comment").fill(COMMENTS[1])
    page.screenshot(path=work / "editor-narrow.png", full_page=True)
    page.get_by_role("button", name="Zurück", exact=True).click()
    expect(page.locator("#comment")).to_have_value(COMMENTS[0])
    page.locator("#next").click()
    expect(page.locator("#comment")).to_have_value(COMMENTS[1])
    page.locator("#next").click()
    page.locator("#card-heading").focus()
    page.keyboard.press("p")
    expect(page.locator("#card-heading")).to_contain_text("4 von")
    page.keyboard.press("Escape")  # Current card remains open.
    overview_filter(page, "accepted", 1)
    overview_filter(page, "change_requested", 2)
    overview_filter(page, "open", 27)
    overview_filter(page, "all", 30)
    check_progress(page, {"accepted": 1, "change_requested": 2, "open": 27})
    current = state(page)
    assert current["submission"] is None
    # The previous UI let reviewers mark a card "Passt" and leave a comment.
    # Persist that valid combination through the same API the previous UI used.
    response = page.request.post(urljoin(url, "api/save"), data={"id": current["cards"][2]["id"],
                                 "ok": True, "comment": LEGACY_COMMENT, "version": current["version"]})
    assert response.ok, response.text()


def edit_in_overview(browser, url, work):
    page = open_page(browser, url + "#ansicht=uebersicht&filter=accepted", 360)
    expect(page.locator('[data-filter="accepted"]')).to_have_attribute("aria-pressed", "true")
    start = page.locator("#sequence-start")
    expect(start).to_have_text("Karten durchgehen")
    start.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#card-heading")).to_be_focused()
    expect(page.locator("#variant")).to_contain_text("c1")
    expect(page.locator("#comment")).to_have_value(COMMENTS[0])
    expect(page.locator("#next")).to_have_text("Speichern und weiter")
    page.locator("#next").click()
    expect(page.locator("#variant")).to_contain_text("c3")
    page.locator("#overview-link").click()
    expect(start).to_contain_text("Karte 2")
    start.click()
    expect(page.locator("#variant")).to_contain_text("c3")
    page.locator("#overview-link").click()
    legacy = overview_filter(page, "accepted", 1).first
    legacy.click()
    expect(page.locator("#comment")).to_have_value(LEGACY_COMMENT)
    page.locator("#overview-link").click()
    expect(page.locator('[data-filter="accepted"]')).to_have_attribute("aria-pressed", "true")
    expect(legacy).to_contain_text(LEGACY_COMMENT)
    rows = overview_filter(page, "change_requested", 2)
    expect(rows.nth(0)).to_contain_text(COMMENTS[0])
    expect(rows.nth(1)).to_contain_text(COMMENTS[1])
    rows.nth(1).click()
    expect(page.locator("#variant")).to_contain_text("c3")
    expect(page.locator("#card-heading")).to_be_focused()
    assert page.locator("#card-heading").evaluate("n => getComputedStyle(n).outlineStyle") == "none"
    expect(page.locator("#comment")).to_have_value(COMMENTS[1])
    expect(page.locator("#prev")).to_be_enabled()
    expect(page.get_by_role("button", name=re.compile("Übersicht"))).to_have_count(1)
    expect(page.locator("#overview-link")).to_have_text("Speichern und zur Übersicht")
    page.locator("#comment").fill("")
    page.locator("#overview-link").click()
    expect(page.locator('[data-filter="change_requested"]')).to_have_attribute("aria-pressed", "true")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text(COMMENTS[0])

    # From the filtered list continue in physical deck order. A failed save
    # must preserve the current editor and its text for the successful retry.
    rows.first.click()
    advance = page.get_by_role("button", name="Speichern und weiter", exact=True)
    page.locator("#comment").fill(REVISED_COMMENT)
    page.route("**/api/save", lambda route: route.fulfill(status=503), times=1)
    advance.click()
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page.locator("#variant")).to_contain_text("c1")
    expect(page.locator("#comment")).to_have_value(REVISED_COMMENT)
    advance.click()
    expect(page.locator("#variant")).to_contain_text("c3")
    expect(page.locator("#next")).to_have_text("Speichern und weiter")
    page.locator("#overview-link").click()
    expect(page.locator('[data-filter="change_requested"]')).to_have_attribute("aria-pressed", "true")
    expect(rows.first).to_contain_text(REVISED_COMMENT)
    overview_filter(page, "accepted", 2)

    # After opening a card well below the fold, return to the same part
    # of the filtered list, including when the opened row drops out.
    rows = overview_filter(page, "open", 27)
    target = rows.nth(18)
    anchor = rows.nth(19).get_attribute("data-card-id")
    neighbor = page.locator(f'[data-card-id="{anchor}"]')
    target.evaluate("row => row.scrollIntoView({block:'center'})")
    previous_y = neighbor.bounding_box()["y"]
    target.click()
    page.locator("#comment").fill("Bitte die Einheit im Beispiel ergänzen.")
    page.locator("#overview-link").click()
    expect(page.locator('[data-filter="open"]')).to_have_attribute("aria-pressed", "true")
    expect(rows).to_have_count(26)
    expect(neighbor).to_be_in_viewport()
    expect(neighbor).to_be_focused()
    assert abs(previous_y - neighbor.bounding_box()["y"]) < 200, "Review jumped within the filtered list"

    overview_filter(page, "all", 30)
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("window.scrollTo(0, 0)")
    expect(page.locator("#submit")).to_be_in_viewport()
    page.screenshot(path=work / "overview-narrow.png")
    boxes = [b.bounding_box() for b in page.locator("[data-filter]").all()]
    assert all(box["height"] >= 44 for box in boxes), boxes
    assert max(b["width"] for b in boxes) - min(b["width"] for b in boxes) < 2, boxes
    expect(page.locator("[data-card-id]").first).to_contain_text("Ein Meter entspricht")
    check_progress(page, {"accepted": 2, "change_requested": 2, "open": 26})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1200, "height": 820})
    page.screenshot(path=work / "overview-wide.png")
    return page


def run(playwright, source, work, executable):
    def launch():
        return playwright.chromium.launch(executable_path=executable, headless=True, chromium_sandbox=True)

    timed_out = subprocess.run(command(source, "--wait", "--timeout", "1"), cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert timed_out.returncode == 3, timed_out
    with server(source, work / "first.log", "--ui-language", "de-DE") as url:
        assert parse_qs(urlsplit(url).query) == {"lang": ["de-DE"]}
        browser = launch()
        print(f"Browser {executable or 'Chromium'} {browser.version}", flush=True)
        first_pass(browser, url, work)
        browser.close()

    with server(source, work / "restart.log", "--ui-language", "de") as url:
        browser = launch()
        page = edit_in_overview(browser, url, work)
        old_revision = state(page)["revision"]
        with subprocess.Popen(command(source, "--wait", "--revision", old_revision, "--timeout", "20"), cwd=ROOT,
                              stdout=subprocess.PIPE, text=True, encoding="utf-8") as waiter:
            time.sleep(2)
            assert waiter.poll() is None, "Waiter exited before submission"
            submit(page)
            stdout, _ = waiter.communicate(timeout=30)
            assert waiter.returncode == 0, stdout
            path = Path(stdout.strip())
            assert path.is_absolute() and path.is_file() and path == Path(state(page)["submission"]["path"])
        handoff = json.loads(path.read_text(encoding="utf-8"))
        check_handoff_revision(handoff, source)
        assert handoff["revision"] == old_revision
        assert handoff["summary"] == {"accepted": 2, "change_requested": 2, "open": 26}
        first, second = handoff["cards"][:2]
        assert (first["note"], first["variant"], first["status"]) == (1, "c1", "change_requested")
        assert first["feedback"] == {"ok": False, "comment": REVISED_COMMENT}
        assert (second["note"], second["variant"], second["status"]) == (1, "c3", "accepted")
        assert second["feedback"] == {"ok": True, "comment": ""}
        assert handoff["cards"][2]["feedback"] == {"ok": True, "comment": LEGACY_COMMENT}
        assert handoff["cards"][3]["status"] == "open" and handoff["cards"][3]["feedback"] is None

        data = json.loads(source.read_text(encoding="utf-8"))
        data["cards"] = data["cards"][:1]
        source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        page.get_by_role("button", name="Prompt kopieren").click()
        expect(page.locator("#revision-notice")).to_contain_text("Das Deck hat sich geändert.")
        expect(page.locator("#revision-notice")).to_contain_text(old_revision[:10])
        assert str(path) in page.evaluate("() => navigator.clipboard.readText()")
        browser.close()

    with server(source, work / "revised.log") as url:
        browser = launch()
        check_languages(browser, url, work)
        page = open_page(browser, url + "?lang=de", 390)
        expect(page.locator("#revision-notice")).to_be_visible()
        expect(page.locator("#comment")).to_have_value("")
        revised = state(page)
        assert revised["current_revision"] == revised["revision"] != old_revision
        assert Path(revised["previous_submission"]["path"]) == path
        page.get_by_role("button", name="Speichern und weiter", exact=True).click()
        expect(page.locator("#next")).to_be_hidden()
        page.locator("#comment").fill("Auch die zweite Lücke in der Kurzfassung prüfen.")
        page.locator("#overview-link").click()
        expect(page.locator("#overview")).to_be_visible()
        assert state(page)["submission"] is None
        overview_filter(page, "change_requested", 1).first.click()
        expect(page.locator("#next")).to_be_hidden()
        page.get_by_role("button", name="Speichern und zur Übersicht", exact=True).click()
        expect(page.locator("#submit")).to_be_visible()
        submit(page)  # This revision has never had a waiter.
        new_path = copy_submitted_path(page)
        check_progress(page, {"accepted": 1, "change_requested": 1, "open": 0})
        page.screenshot(path=work / "submitted-narrow.png", full_page=True)
        new_handoff = json.loads(new_path.read_text(encoding="utf-8"))
        assert new_path != path and new_handoff["revision"] == revised["revision"]
        check_handoff_revision(new_handoff, source)
        assert new_handoff["summary"] == {"accepted": 1, "change_requested": 1, "open": 0}
        assert new_handoff["cards"][1]["feedback"]["comment"] == "Auch die zweite Lücke in der Kurzfassung prüfen."
        check_localized_handoff(page, new_path)
        writes = []
        def record_post(request):
            if request.method == "POST":
                writes.append(request.url)
        page.on("request", record_post)
        overview_filter(page, "open", 0)
        expect(page.locator("#empty-list")).to_be_visible()
        page.locator("#sequence-start").click()
        expect(page.locator("#comment")).to_be_hidden()
        expect(page.locator("#saved-comment")).to_be_hidden()
        expect(page.get_by_role("button", name=re.compile("Speichern"))).to_have_count(0)
        page.get_by_role("button", name="Weiter", exact=True).click()
        expect(page.locator("#variant")).to_contain_text("c3")
        expect(page.locator("#saved-comment")).to_contain_text("Auch die zweite Lücke")
        expect(page.locator("#comment")).to_be_hidden()
        page.get_by_role("button", name="Zur Übersicht", exact=True).click()
        expect(page.locator("#overview")).to_be_visible()
        assert not writes, f"Read-only navigation wrote to {writes}"
        assert json.loads(new_path.read_text(encoding="utf-8")) == new_handoff
        browser.close()
    again = subprocess.check_output(command(source, "--wait", "--timeout", "1", "--revision", old_revision),
                                    cwd=ROOT, text=True, encoding="utf-8", timeout=30)
    assert Path(again.strip()) == path and json.loads(path.read_text(encoding="utf-8")) == handoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-executable", type=Path, help="An installed Chromium-based browser")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(dir=ROOT / ".forge", prefix="review-qa-"))
    temporary = work / "tmp"
    temporary.mkdir()
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(temporary)
    source = work / "werkstatt.cards.json"
    cards = [{"type": "cloze", "text": "Ein Meter entspricht {{c1::100}} cm oder {{c3::1000}} mm."}]
    measures = [("Zentimeter", "Meter", 100), ("Gramm", "Kilogramm", 1000),
                ("Milliliter", "Liter", 1000), ("Minuten", "Stunden", 60)]
    for amount in range(2, 9):
        for smaller, larger, factor in measures:
            cards.append({"type": "basic", "front": f"Wie viele {smaller} sind {amount} {larger}?",
                          "back": f"{amount * factor} {smaller}."})
    # The render cache is keyed by deck contents. Give each run a fresh snapshot.
    deck = {"deck": "Werkstatt::Maßeinheiten", "description": f"Synthetic review {work.name}", "cards": cards}
    source.write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
    print(f"Synthetic source and local evidence: {work}", flush=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".forge" / "browsers"))
    with sync_playwright() as playwright:
        run(playwright, source, work, args.browser_executable)
    print("PASS: review navigation, drafts, six UI languages, wait, clipboard and revision handoff.")


if __name__ == "__main__":
    main()
