"""Tests for tools/anki_connect.py (AnkiConnect client) — urllib fully mocked,
no real network, no running Anki needed (CI-safe)."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from _tools import load

ac = load("anki_connect")


class FakeResponse(io.BytesIO):
    """Minimal stand-in for urlopen's response (context manager + .read())."""

    def __init__(self, body):
        super().__init__(json.dumps(body).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def urlopen_mock(*responses):
    """Returns (mock for ac.urllib.request.urlopen, list of captured payloads).

    Each call pops the next canned response body; the JSON payload of every
    request is recorded for assertions.
    """
    payloads = []
    queue = list(responses)

    def fake(req, timeout=None):
        payloads.append(json.loads(req.data.decode("utf-8")))
        body = queue.pop(0)
        if isinstance(body, Exception):
            raise body
        return FakeResponse(body)

    return fake, payloads


class TestInvoke(unittest.TestCase):
    def test_envelope_and_result(self):
        fake, payloads = urlopen_mock({"result": ["Default"], "error": None})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            result = ac.invoke("deckNames", foo="bar")
        self.assertEqual(result, ["Default"])
        self.assertEqual(payloads, [
            {"action": "deckNames", "version": 6, "params": {"foo": "bar"}}
        ])

    def test_error_in_envelope_raises(self):
        fake, _ = urlopen_mock({"result": None, "error": "deck was not found"})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "deck was not found"):
                ac.invoke("exportPackage")

    def test_malformed_envelope_raises(self):
        fake, _ = urlopen_mock({"unexpected": True})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "Unexpected"):
                ac.invoke("version")

    def test_unreachable_raises_with_install_help(self):
        fake, _ = urlopen_mock(urllib.error.URLError("Connection refused"))
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "2055492159"):
                ac.invoke("version")


class TestPing(unittest.TestCase):
    def test_granted(self):
        fake, payloads = urlopen_mock(
            {"result": {"permission": "granted", "version": 6}, "error": None})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with redirect_stdout(io.StringIO()):
                ac.ping()
        self.assertEqual(payloads[0]["action"], "requestPermission")

    def test_denied_raises(self):
        fake, _ = urlopen_mock({"result": {"permission": "denied"}, "error": None})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "permission denied"):
                ac.ping()


class TestPush(unittest.TestCase):
    def test_sends_absolute_path(self):
        fake, payloads = urlopen_mock({"result": True, "error": None})
        with tempfile.NamedTemporaryFile(suffix=".apkg") as f:
            rel = os.path.relpath(f.name)
            with mock.patch.object(ac.urllib.request, "urlopen", fake):
                with redirect_stdout(io.StringIO()):
                    ac.push(rel)
        self.assertEqual(payloads[0]["action"], "importPackage")
        self.assertTrue(os.path.isabs(payloads[0]["params"]["path"]))

    def test_missing_file_raises_before_any_request(self):
        fake, payloads = urlopen_mock()
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaises(FileNotFoundError):
                ac.push("does/not/exist.apkg")
        self.assertEqual(payloads, [])


class TestExport(unittest.TestCase):
    def test_with_scheduling_and_creates_outdir(self):
        fake, payloads = urlopen_mock({"result": True, "error": None})
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "new", "sub", "deck.apkg")
            with mock.patch.object(ac.urllib.request, "urlopen", fake):
                with redirect_stdout(io.StringIO()):
                    ac.export("Topic::Deck", out)
            self.assertTrue(os.path.isdir(os.path.dirname(out)))
        params = payloads[0]["params"]
        self.assertEqual(payloads[0]["action"], "exportPackage")
        self.assertEqual(params["deck"], "Topic::Deck")
        self.assertTrue(params["includeSched"])
        self.assertTrue(os.path.isabs(params["path"]))


class TestMirror(unittest.TestCase):
    def _run(self, responses, decode, deck_names=None, check=None):
        """Runs mirror() in a temp cwd; returns (payloads, stdout, stderr).
        `check` runs while still inside the temp cwd (for filesystem asserts)."""
        fake, payloads = urlopen_mock(*responses)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                with mock.patch.object(ac.urllib.request, "urlopen", fake), \
                        mock.patch.object(ac, "_decode_apkg", decode):
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        ac.mirror(deck_names)
                if check:
                    check()
            finally:
                os.chdir(cwd)
        return payloads, out.getvalue(), err.getvalue()

    def test_top_level_decks_deduplicated(self):
        responses = [
            {"result": ["A", "A::Sub1", "A::Sub1::Deep", "B"], "error": None},  # deckNames
            {"result": True, "error": None},  # exportPackage A
            {"result": True, "error": None},  # exportPackage B
        ]
        payloads, _, _ = self._run(responses, lambda p, o: ([(o, "A", 3)], []))
        exports = [p for p in payloads if p["action"] == "exportPackage"]
        self.assertEqual([p["params"]["deck"] for p in exports], ["A", "B"])
        self.assertTrue(all(p["params"]["includeSched"] for p in exports))

    def test_safe_filenames(self):
        responses = [{"result": True, "error": None}]
        payloads, _, _ = self._run(
            responses, lambda p, o: ([(o, "x", 1)], []),
            deck_names=["Sommersemester 2026::SWT"])
        path = payloads[0]["params"]["path"]
        base = os.path.basename(path)
        self.assertEqual(base, "Sommersemester_2026_SWT.apkg")

    def test_one_failing_deck_does_not_stop_the_rest(self):
        responses = [
            {"result": None, "error": "deck is filtered"},  # exportPackage A fails
            {"result": True, "error": None},                # exportPackage B ok
        ]
        payloads, out, err = self._run(
            responses, lambda p, o: ([(o, "B", 2)], []), deck_names=["A", "B"])
        self.assertEqual(len(payloads), 2)
        self.assertIn("SKIPPED: 'A'", err)
        self.assertIn("OK: 'B'", out)

    def test_empty_deck_is_skipped_and_apkg_removed(self):
        # Two decks: "Empty" decodes to 0 notes (apkg gets removed), "Full" stays.
        responses = [
            {"result": True, "error": None},  # exportPackage Empty
            {"result": True, "error": None},  # exportPackage Full
        ]

        def decode(apkg_path, outdir):
            # exportPackage is mocked and writes nothing — simulate the file it
            # would have created, so mirror() can remove it for the empty deck.
            open(apkg_path, "wb").close()
            if "Empty" in apkg_path:
                return [], []  # no notes decoded
            return [(outdir, "Full", 2)], []

        def check():
            self.assertFalse(os.path.exists(os.path.join(ac.MIRROR_DIR, "Empty.apkg")))
            self.assertTrue(os.path.exists(os.path.join(ac.MIRROR_DIR, "Full.apkg")))

        _, out, err = self._run(responses, decode,
                                deck_names=["Empty", "Full"], check=check)
        self.assertIn("SKIPPED: 'Empty'", err)
        self.assertIn("empty deck", err)
        self.assertIn("OK: 'Full'", out)

    def test_all_failed_raises(self):
        responses = [{"result": None, "error": "boom"}]
        fake, _ = urlopen_mock(*responses)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                with mock.patch.object(ac.urllib.request, "urlopen", fake):
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        with self.assertRaisesRegex(ac.AnkiConnectError, "No deck"):
                            ac.mirror(["OnlyDeck"])
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
