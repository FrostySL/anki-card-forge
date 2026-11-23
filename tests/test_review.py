"""Exercise the actual HTTP boundary and the publication of a complete preview."""
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from _tools import load

review = load("review")


class TestReview(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source file.json"
        self.source.write_text(json.dumps({"deck": "D", "cards": [
            {"type": "cloze", "text": "{{c1::One}} and {{c3::three}}"}
        ]}), encoding="utf-8")
        self.revision = review.source_revision(self.source)

    def test_review_locales_cover_each_message_and_its_placeholders(self):
        directory = review.UI / "locales"
        english = json.loads((directory / "en.json").read_text(encoding="utf-8"))
        for language in review.UI_LANGUAGES:
            with self.subTest(language=language):
                translated = json.loads((directory / f"{language}.json").read_text(encoding="utf-8"))
                self.assertEqual(translated.keys(), english.keys())
                for key, value in translated.items():
                    self.assertTrue(value.strip(), key)
                    self.assertCountEqual(re.findall(r"{\w+}", value),
                                          re.findall(r"{\w+}", english[key]), key)

    def test_snapshot_publication_and_reuse(self):
        raw = self.source.read_bytes()
        previous = self.root / "previews" / "v3" / self.revision
        previous.mkdir(parents=True)
        (previous / "source.json").write_bytes(raw)

        def render(command, **kwargs):
            self.assertEqual(Path(command[-3]).read_bytes(), raw)
            directory = Path(command[-1])
            directory.mkdir()
            (directory / "cards.json").write_text("[]", encoding="utf-8")

        with patch.object(review.subprocess, "run", side_effect=render) as run:
            cache = review.render_snapshot(raw, self.revision, self.root)
            self.assertNotEqual(cache, previous)
            self.assertEqual((previous / "source.json").read_bytes(), raw)
            self.assertEqual((cache / "source.json").read_bytes(), raw)
            self.assertTrue((cache / "cards.json").is_file())
            self.assertEqual(review.render_snapshot(raw, self.revision, self.root), cache)
            run.assert_called_once()

    def test_media_change_during_render_does_not_publish(self):
        with patch.object(review.subprocess, "run"), patch.object(review, "deck_revision", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "image changed"):
                review.render_snapshot(self.source.read_bytes(), self.revision, self.root)
        self.assertEqual(list(self.root.rglob("source.json")), [])

    def test_cli_modes(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(review.main([str(self.source), "--show-revision"]), 0)
        self.assertEqual(output.getvalue().strip(), self.revision)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(review.main([str(self.source), "--wait", "--timeout", "0"]), 3)
            for options in (["--revision", self.revision], ["--wait", "--port", "9"],
                            ["--wait", "--revision", "bad"], ["--timeout", "5"],
                            ["--wait", "--timeout", "nan"], ["--wait", "--ui-language", "fr"],
                            ["--show-revision", "--ui-language", "fr"]):
                with self.subTest(options=options), self.assertRaises(SystemExit):
                    review.main([str(self.source), *options])

    def test_review_session_reads_images_saves_and_submits(self):
        cards = [{"id": f"note-1:c{n}", "note": 1, "variant": f"c{n}", "label": "Gap",
                  "front": f"{n}-front.png", "back": f"{n}-back.png"} for n in (1, 3)]
        store = review.ReviewStore(self.source, self.revision, "D", cards, root=self.root)
        image = self.root / "1-front.png"
        image.write_bytes(b"preview")
        handler = partial(review.ReviewHandler, store=store, prefix="/session/", images={image.name: image})
        with ThreadingHTTPServer((review.HOST, 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                def request(path, data=None, **headers):
                    connection = HTTPConnection(review.HOST, server.server_port, timeout=5)
                    try:
                        body = json.dumps(data) if data is not None else None
                        connection.request("POST" if body else "GET", path, body,
                                           {"Content-Type": "application/json", **headers})
                        response = connection.getresponse()
                        return response.status, response.read()
                    finally:
                        connection.close()

                self.assertEqual(request("/session/1-front.png"), (200, b"preview"))
                self.assertEqual(request("/session/")[0], 200)
                self.assertEqual(request("/session/?lang=fr-CA"), request("/session/"))
                status, script = request("/session/i18n.js")
                self.assertEqual(status, 200)
                self.assertIn(b'"zh-Hans":', script)
                self.assertEqual(request("/")[0], 404)
                self.assertEqual(request("/session/source.json")[0], 404)
                status, body = request("/session/api/state")
                self.assertEqual(status, 200)
                state = json.loads(body)
                self.assertEqual(state["cards"], cards)
                self.assertEqual(state["statuses"], {card["id"]: "open" for card in cards})
                save = {"version": 0, "id": cards[1]["id"], "ok": False, "comment": "Frage kürzen."}
                self.assertEqual(request("/session/api/save", save, Origin="null")[0], 404)
                status, body = request("/session/api/save", save)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["statuses"],
                                 {cards[0]["id"]: "open", cards[1]["id"]: "change_requested"})
                status, body = request("/session/api/save", save)
                self.assertEqual(status, 409)
                self.assertEqual(json.loads(body)["error_key"], "otherWindow")
                status, body = request("/session/api/submit", {"version": 1})
                self.assertEqual(status, 200)
                path = Path(json.loads(body)["submission"]["path"])
                handoff = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsNone(handoff["cards"][0]["feedback"])
                self.assertEqual(handoff["cards"][1]["feedback"]["comment"], save["comment"])
                self.assertEqual(handoff["summary"], {"accepted": 0, "change_requested": 1, "open": 1})
            finally:
                server.shutdown()
                thread.join()

    def test_default_http_port_uses_the_browser_origin(self):
        request = SimpleNamespace(server=SimpleNamespace(server_port=80), prefix="/session/",
                                  path="/session/api/state", headers={"Origin": "http://127.0.0.1"})
        for host in ("127.0.0.1", "127.0.0.1:80"):
            with self.subTest(host=host):
                request.headers["Host"] = host
                self.assertEqual(review.ReviewHandler.route_name(request), "api/state")
