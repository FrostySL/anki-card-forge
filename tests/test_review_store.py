"""Exercise review persistence, revision boundaries and handoff without a browser."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from _tools import load


review = load("review_store")


class TestReviewStore(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()
        self.root = self.project / "reviews"
        self.source = self.project / "Übung eins.cards.json"
        self.data = {"deck": "Test", "cards": [
            {"type": "cloze", "guid": "g123", "text": "{{c1::eins}} und {{c3::drei}}"}
        ]}
        self.source.write_text(json.dumps(self.data), encoding="utf-8")
        self.revision = review.source_revision(self.source, self.project)
        self.cards = [
            {"id": f"1:c{n}", "note": 1, "variant": f"c{n}", "guid": "g123",
             "label": f"Lücke {n}", "front": f"f{n}.png", "back": f"b{n}.png"}
            for n in (1, 3)
        ]

    def store(self, revision=None, **kwargs):
        return review.ReviewStore(self.source, revision or self.revision, "Test", self.cards,
                                  root=self.root, project_root=self.project, **kwargs)

    def test_restart_then_submit_two_variants(self):
        snapshot = self.project / "source.json"
        snapshot.write_bytes(self.source.read_bytes())
        self.cards[0]["context"] = "Satz zum ersten Lückentext"
        store = self.store(snapshot=snapshot)
        store.save("1:c1", True, "Passt für mich.", 0)
        store.save("1:c3", False, "Bitte umformulieren.", 1)
        restarted = self.store(snapshot=snapshot)
        state = restarted.state()
        self.assertEqual(state["feedback"], {
            "1:c1": {"ok": True, "comment": "Passt für mich."},
            "1:c3": {"ok": False, "comment": "Bitte umformulieren."},
        })
        self.assertEqual(state["statuses"], {"1:c1": "accepted", "1:c3": "change_requested"})
        submission = restarted.submit(state["version"])["submission"]
        path = Path(submission["path"])
        self.assertTrue(path.is_absolute())
        self.assertIn(str(path), submission["prompt"])
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["source"], str(self.source))
        self.assertEqual(Path(doc["review_project_root"]), self.project)
        self.assertIn("review_project_root", doc["revision_check"])
        self.assertEqual(doc["reviewed_source_snapshot"], str(snapshot))
        self.assertEqual(doc["revision"], self.revision)
        self.assertEqual(doc["current_revision_at_submission"], self.revision)
        self.assertEqual(doc["summary"], {"accepted": 1, "change_requested": 1, "open": 0})
        self.assertEqual({c["id"]: c["status"] for c in doc["cards"]}, state["statuses"])
        self.assertEqual(set(doc["cards"][0]), {"id", "note", "variant", "label", "guid", "status", "feedback"})
        self.assertEqual([(c["note"], c["variant"], c["guid"], c["feedback"]) for c in doc["cards"]],
                         [(1, "c1", "g123", state["feedback"]["1:c1"]),
                          (1, "c3", "g123", state["feedback"]["1:c3"])])
        raw = path.read_bytes()
        self.assertEqual(self.store().submit(0)["submission"], submission)
        with self.assertRaises(review.ReviewConflict):
            store.save("1:c1", False, "late change", state["version"])
        self.assertEqual(path.read_bytes(), raw)

    def test_wait_before_submit_timeout_cancel_and_later_pickup(self):
        def wait(timeout):
            return review.wait_for_submission(self.source, self.revision, timeout, self.root)

        with self.assertRaises(TimeoutError):
            wait(0.01)
        with patch.object(review.time, "sleep", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            wait(10)
        self.assertFalse(self.root.exists())
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(wait, 5)
            path = self.store().submit(0)["submission"]["path"]
            self.assertEqual(pending.result(), Path(path))
        self.assertEqual(wait(0), Path(path))
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(doc["summary"], {"accepted": 0, "change_requested": 0, "open": 2})
        self.assertTrue(all(c["status"] == "open" for c in doc["cards"]))
        self.assertTrue(all(c["feedback"] is None for c in doc["cards"]))
        other = self.project / "copy.cards.json"
        other.write_bytes(self.source.read_bytes())
        with self.assertRaises(TimeoutError):
            review.wait_for_submission(other, self.revision, 0, self.root)

    def test_legacy_draft_reports_statuses_and_preserves_feedback_until_edited(self):
        store = self.store()
        raw = {"1:c1": {"ok": True, "comment": "Schon passend!"},
               "1:c3": {"ok": False, "comment": ""}}
        with closing(sqlite3.connect(store.database)) as db, db:
            db.execute("UPDATE drafts SET version=?, feedback=? WHERE revision=?",
                       (2, json.dumps(raw), self.revision))
        reopened = self.store()
        before = reopened.state()
        self.assertEqual(before["feedback"], raw)
        self.assertEqual(before["statuses"], {"1:c1": "accepted", "1:c3": "change_requested"})
        after = reopened.save("1:c3", True, "", before["version"])
        self.assertEqual(after["feedback"], {"1:c1": raw["1:c1"], "1:c3": {"ok": True, "comment": ""}})
        self.assertEqual(after["statuses"], {"1:c1": "accepted", "1:c3": "accepted"})

    def test_legacy_submission_is_readable_without_rewriting_its_file(self):
        store = self.store()
        raw = {"ok": True, "comment": "Mit Kommentar akzeptiert."}
        legacy = {
            "deck": "Test", "revision": self.revision, "source": str(self.source),
            "cards": [{"id": "1:c1", "note": 1, "variant": "c1", "feedback": raw},
                      {"id": "1:c3", "note": 1, "variant": "c3", "feedback": None}],
        }
        original_bytes = json.dumps(legacy, indent=2).encode("utf-8")
        store.path.write_bytes(original_bytes)
        self.cards[0].update(front_light="c1-light.png", context="Die [erste] Lücke.")
        reopened = self.store()
        state = reopened.state()
        self.assertEqual(state["cards"][0]["front_light"], "c1-light.png")
        self.assertEqual(state["cards"][0]["context"], "Die [erste] Lücke.")
        self.assertEqual(state["feedback"], {"1:c1": raw})
        self.assertEqual(state["statuses"], {"1:c1": "accepted", "1:c3": "open"})
        self.assertEqual(reopened.submit(0)["submission"]["path"], str(store.path))
        path = review.wait_for_submission(self.source, self.revision, 0, self.root)
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_stale_revision_is_identifiable_during_and_after_handoff(self):
        store = self.store()
        self.source.write_bytes(self.source.read_bytes() + b" ")
        changed = review.source_revision(self.source)
        self.assertNotEqual(changed, self.revision)
        path = Path(store.submit(0)["submission"]["path"])
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((doc["revision"], doc["current_revision_at_submission"]), (self.revision, changed))
        self.assertIn("--show-revision", doc["revision_check"])
        fresh = self.store(changed).state()
        self.assertIsNone(fresh["submission"])
        self.assertEqual(fresh["previous_submission"], {"revision": self.revision, "path": str(path)})
        self.assertEqual(fresh["feedback"], {})
        with self.assertRaises(TimeoutError):
            review.wait_for_submission(self.source, changed, 0, self.root)
        self.source.write_text("{", encoding="utf-8")
        self.assertIsNone(store.state()["current_revision"])
        self.source.unlink()
        self.assertIsNone(store.state()["current_revision"])
        self.assertEqual(review.wait_for_submission(self.source, self.revision, 0, self.root), path)

    def test_media_changes_alter_revision_including_occlusion_and_embedded_images(self):
        self.assertEqual(self.revision, hashlib.sha256(self.source.read_bytes()).hexdigest())
        image = self.project / "figure.png"
        image.write_bytes(b"first figure")
        for card in ({"type": "occlusion", "image": "figure.png", "regions": []},
                     {"type": "basic", "front": "Q", "back": "A",
                      "explanation": "<img src='figure.png'>"}):
            with self.subTest(card=card):
                self.data["cards"] = [card]
                self.source.write_text(json.dumps(self.data), encoding="utf-8")
                first = review.source_revision(self.source, self.project)
                image.write_bytes(image.read_bytes() + b"!")
                store = self.store(first)
                self.assertNotEqual(first, store.state()["current_revision"])
                path = Path(store.submit(0)["submission"]["path"])
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["revision"], first)
        image.unlink()
        self.assertIsNone(store.state()["current_revision"])

    def test_two_writers_cannot_overwrite_a_newer_draft(self):
        first, second = self.store(), self.store()
        barrier = threading.Barrier(2)

        def save(store, comment):
            barrier.wait(timeout=5)
            try:
                store.save("1:c1", True, comment, 0)
            except review.ReviewConflict:
                return None
            return comment

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(save, store, text)
                       for store, text in ((first, "first"), (second, "second"))]
            winners = [winner for f in futures if (winner := f.result()) is not None]
        self.assertEqual(len(winners), 1)
        state = first.state()
        self.assertEqual(state["feedback"]["1:c1"]["comment"], winners[0])
        self.assertEqual(state["version"], 1)
        with self.assertRaises(review.ReviewConflict):
            second.submit(0)

    def test_failed_publication_keeps_draft_editable_and_waiter_idle(self):
        store = self.store()
        store.save("1:c3", True, "", 0)
        with patch.object(review.os, "replace", side_effect=PermissionError), self.assertRaises(PermissionError):
            store.submit(1)
        self.assertIsNone(store.state()["submission"])
        with self.assertRaises(TimeoutError):
            review.wait_for_submission(self.source, self.revision, 0, self.root)
        self.assertFalse(list(self.root.rglob("*.tmp")))
        self.assertIsNotNone(store.submit(1)["submission"])

    def test_invalid_comment_is_rejected_and_escaped_deck_label_can_be_handed_off(self):
        self.cards[0]["label"] = "Lücke \ud800"
        store = self.store()
        with self.assertRaisesRegex(ValueError, "Unicode-Zeichen"):
            store.save("1:c1", True, "Kommentar \ud800", 0)
        self.assertEqual(store.state()["feedback"], {})
        store.save("1:c1", True, "Grüße 🔥", 0)
        path = Path(store.submit(1)["submission"]["path"])
        raw = path.read_text(encoding="utf-8")
        self.assertIn("Grüße 🔥", raw)
        self.assertEqual(json.loads(raw)["cards"][0]["label"], self.cards[0]["label"])


if __name__ == "__main__":
    unittest.main()
