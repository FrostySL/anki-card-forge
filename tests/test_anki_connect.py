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


class TestSafeActions(unittest.TestCase):
    def test_destructive_action_is_locked(self):
        fake, payloads = urlopen_mock()
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "safe list"):
                ac.invoke("deleteDecks", decks=["X"], cardsToo=True)
        self.assertEqual(payloads, [])  # never reached the network

    def test_env_override_allows_it_consciously(self):
        fake, payloads = urlopen_mock({"result": None, "error": None})
        with mock.patch.dict(os.environ, {"ANKICONNECT_ALLOW_UNSAFE": "1"}):
            with mock.patch.object(ac.urllib.request, "urlopen", fake):
                ac.invoke("deleteDecks", decks=["X"])
        self.assertEqual(payloads[0]["action"], "deleteDecks")


class TestPush(unittest.TestCase):
    def test_sends_absolute_path(self):
        fake, payloads = urlopen_mock({"result": True, "error": None})
        with tempfile.NamedTemporaryFile(suffix=".apkg") as f:
            rel = os.path.relpath(f.name)
            with mock.patch.object(ac.urllib.request, "urlopen", fake):
                with redirect_stdout(io.StringIO()):
                    ac.push(rel, backup=False)
        self.assertEqual(payloads[0]["action"], "importPackage")
        self.assertTrue(os.path.isabs(payloads[0]["params"]["path"]))

    def test_missing_file_raises_before_any_request(self):
        fake, payloads = urlopen_mock()
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaises(FileNotFoundError):
                ac.push("does/not/exist.apkg")
        self.assertEqual(payloads, [])

    def _push_with_backup(self, package_decks, anki_decks, responses):
        """Runs push(backup=True) in a temp cwd with the apkg inspection mocked;
        returns (payloads, stdout)."""
        fake, payloads = urlopen_mock(
            {"result": anki_decks, "error": None},  # deckNames
            *responses)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                open("in.apkg", "wb").close()
                with mock.patch.object(ac.urllib.request, "urlopen", fake), \
                        mock.patch.object(ac, "_decks_in_apkg",
                                          lambda p: set(package_decks)):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        ac.push("in.apkg")
            finally:
                os.chdir(cwd)
        return payloads, out.getvalue()

    def test_backup_exports_affected_decks_before_import(self):
        payloads, out = self._push_with_backup(
            package_decks=["Bio::Resp"], anki_decks=["Bio", "Bio::Resp", "Other"],
            responses=[
                {"result": True, "error": None},  # exportPackage (backup)
                {"result": True, "error": None},  # importPackage
            ])
        actions = [p["action"] for p in payloads]
        self.assertEqual(actions, ["deckNames", "exportPackage", "importPackage"])
        backup = payloads[1]["params"]
        self.assertEqual(backup["deck"], "Bio::Resp")
        self.assertTrue(backup["includeSched"])
        self.assertIn(ac.BACKUP_DIR, backup["path"])
        self.assertIn("Backup: 'Bio::Resp'", out)

    def test_backup_skips_new_decks(self):
        payloads, out = self._push_with_backup(
            package_decks=["Brand::New"], anki_decks=["Other"],
            responses=[{"result": True, "error": None}])  # importPackage only
        self.assertEqual([p["action"] for p in payloads],
                         ["deckNames", "importPackage"])
        self.assertIn("nothing to save", out)

    def test_backup_uses_minimal_covering_set(self):
        payloads, _ = self._push_with_backup(
            package_decks=["A", "A::B", "C"], anki_decks=["A", "A::B"],
            responses=[
                {"result": True, "error": None},  # exportPackage A (covers A::B)
                {"result": True, "error": None},  # importPackage
            ])
        exports = [p["params"]["deck"] for p in payloads
                   if p["action"] == "exportPackage"]
        self.assertEqual(exports, ["A"])


class TestOrphans(unittest.TestCase):
    """Pure diff logic of push --prune (which notes may be deleted)."""

    def test_only_removed_guids_in_package_decks(self):
        anki_notes = {
            "g1": (11, "A", "kept card"),
            "g2": (12, "A", "<b>removed</b> card"),
            "g3": (13, "A::Other", "sibling deck, not in package"),
        }
        orphans = ac._orphans(anki_notes, package_guids={"g1", "gNew"},
                              package_decks={"A"})
        self.assertEqual(orphans, [(12, "A", "removed card")])  # HTML stripped

    def test_moved_note_is_kept(self):
        # guid still in the package (in another deck) -> not an orphan
        anki_notes = {"g1": (11, "A", "x"), "g2": (12, "A", "y")}
        orphans = ac._orphans(anki_notes, package_guids={"g1", "g2"},
                              package_decks={"A", "B"})
        self.assertEqual(orphans, [])

    def test_zero_guid_overlap_refused(self):
        # no shared GUID = rebuild lost the GUIDs -> refuse instead of wiping
        anki_notes = {"old1": (11, "A", "x"), "old2": (12, "A", "y")}
        with self.assertRaisesRegex(ac.AnkiConnectError, "0 shared GUIDs"):
            ac._orphans(anki_notes, package_guids={"new1", "new2"},
                        package_decks={"A"})


class TestPushPrune(unittest.TestCase):
    def test_prune_requires_backup(self):
        with self.assertRaisesRegex(ac.AnkiConnectError, "--no-backup"):
            with tempfile.NamedTemporaryFile(suffix=".apkg") as f:
                ac.push(f.name, backup=False, prune=True)

    def _push_prune(self, anki_notes, package_guids, responses):
        fake, payloads = urlopen_mock(
            {"result": ["A"], "error": None},  # deckNames
            *responses)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                open("in.apkg", "wb").close()
                with mock.patch.object(ac.urllib.request, "urlopen", fake), \
                        mock.patch.object(ac, "_decks_in_apkg", lambda p: {"A"}), \
                        mock.patch.object(ac, "_package_guids",
                                          lambda p: set(package_guids)), \
                        mock.patch.object(ac, "_notes_with_decks",
                                          lambda p: dict(anki_notes)):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        ac.push("in.apkg", prune=True)
            finally:
                os.chdir(cwd)
        return payloads, out.getvalue()

    def test_prune_deletes_orphans_after_import(self):
        payloads, out = self._push_prune(
            anki_notes={"g1": (11, "A", "kept"), "g2": (12, "A", "removed")},
            package_guids={"g1"},
            responses=[
                {"result": True, "error": None},  # exportPackage (backup)
                {"result": True, "error": None},  # importPackage
                {"result": None, "error": None},  # deleteNotes
            ])
        actions = [p["action"] for p in payloads]
        self.assertEqual(actions,
                         ["deckNames", "exportPackage", "importPackage", "deleteNotes"])
        self.assertEqual(payloads[3]["params"]["notes"], [12])
        self.assertIn("removed", out)

    def test_refusal_aborts_before_import(self):
        # zero GUID overlap -> the push must fail WITHOUT importing anything
        fake, payloads = urlopen_mock(
            {"result": ["A"], "error": None},  # deckNames
            {"result": True, "error": None},   # exportPackage (backup)
        )
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                open("in.apkg", "wb").close()
                with mock.patch.object(ac.urllib.request, "urlopen", fake), \
                        mock.patch.object(ac, "_decks_in_apkg", lambda p: {"A"}), \
                        mock.patch.object(ac, "_package_guids", lambda p: {"new"}), \
                        mock.patch.object(ac, "_notes_with_decks",
                                          lambda p: {"old": (11, "A", "x")}):
                    with redirect_stdout(io.StringIO()):
                        with self.assertRaisesRegex(ac.AnkiConnectError, "Prune refused"):
                            ac.push("in.apkg", prune=True)
            finally:
                os.chdir(cwd)
        self.assertEqual([p["action"] for p in payloads],
                         ["deckNames", "exportPackage"])  # no importPackage

    def test_prune_with_nothing_removed_deletes_nothing(self):
        payloads, out = self._push_prune(
            anki_notes={"g1": (11, "A", "kept")},
            package_guids={"g1", "gNew"},
            responses=[
                {"result": True, "error": None},  # exportPackage (backup)
                {"result": True, "error": None},  # importPackage
            ])
        self.assertNotIn("deleteNotes", [p["action"] for p in payloads])
        self.assertIn("nothing to delete", out)


class TestUpdateNote(unittest.TestCase):
    NOTE_INFO = {
        "noteId": 42, "modelName": "Einfach-b7fab", "cards": [420],
        "fields": {
            "Vorderseite": {"value": "Frage?", "order": 0},
            "Rückseite": {"value": "Antwort", "order": 1},
        },
    }

    def _run(self, responses, fields, backup=True):
        fake, payloads = urlopen_mock(*responses)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                with mock.patch.object(ac.urllib.request, "urlopen", fake):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        ac.update_note(42, fields, backup=backup)
            finally:
                os.chdir(cwd)
        return payloads, out.getvalue()

    def test_updates_after_backup_of_containing_deck(self):
        payloads, out = self._run(
            [
                {"result": [self.NOTE_INFO], "error": None},               # notesInfo
                {"result": [{"deckName": "S::SWT::01"}], "error": None},   # cardsInfo
                {"result": True, "error": None},                          # exportPackage
                {"result": None, "error": None},                          # updateNoteFields
            ],
            fields={"Rückseite": "Antwort<br>NEU"})
        actions = [p["action"] for p in payloads]
        self.assertEqual(actions,
                         ["notesInfo", "cardsInfo", "exportPackage", "updateNoteFields"])
        self.assertEqual(payloads[2]["params"]["deck"], "S::SWT::01")
        note = payloads[3]["params"]["note"]
        self.assertEqual(note, {"id": 42, "fields": {"Rückseite": "Antwort<br>NEU"}})
        self.assertIn("Einfach-b7fab", out)  # note type shown for verification

    def test_unknown_field_refused_before_any_write(self):
        payloads = []
        fake, payloads = urlopen_mock({"result": [self.NOTE_INFO], "error": None})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "no field"):
                ac.update_note(42, {"Back": "x"})  # note type has 'Rückseite', not 'Back'
        self.assertEqual([p["action"] for p in payloads], ["notesInfo"])

    def test_missing_note_raises(self):
        fake, _ = urlopen_mock({"result": [{}], "error": None})
        with mock.patch.object(ac.urllib.request, "urlopen", fake):
            with self.assertRaisesRegex(ac.AnkiConnectError, "not found"):
                ac.update_note(999, {"Rückseite": "x"})

    def test_no_backup_skips_export(self):
        payloads, _ = self._run(
            [
                {"result": [self.NOTE_INFO], "error": None},  # notesInfo
                {"result": None, "error": None},              # updateNoteFields
            ],
            fields={"Rückseite": "neu"}, backup=False)
        self.assertEqual([p["action"] for p in payloads],
                         ["notesInfo", "updateNoteFields"])


class TestBackupHelpers(unittest.TestCase):
    def test_covering(self):
        self.assertEqual(ac._covering({"A", "A::B", "A::B::C", "D::E"}),
                         ["A", "D::E"])
        self.assertEqual(ac._covering(set()), [])

    def test_prune_keeps_newest(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                for i in range(12):
                    os.makedirs(os.path.join(ac.BACKUP_DIR, f"20260702-0000{i:02d}"))
                ac._prune_backups(keep=10)
                left = sorted(os.listdir(ac.BACKUP_DIR))
            finally:
                os.chdir(cwd)
        self.assertEqual(len(left), 10)
        self.assertEqual(left[0], "20260702-000002")  # the two oldest are gone


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
