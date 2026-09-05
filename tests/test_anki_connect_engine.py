"""AnkiConnect safety regressions in disposable real Anki collections.

Only the HTTP boundary is replaced. Exports, imports, GUID matching, restore
verification and scheduling are exercised by Anki's actual engine. No network
requests, desktop collection, credentials or AnkiWeb sync are involved.
"""
import importlib.util
import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from _tools import load

ac = load("anki_connect")
HAS_ENGINE = importlib.util.find_spec("anki") is not None and importlib.util.find_spec("genanki") is not None


@unittest.skipUnless(HAS_ENGINE, "needs optional anki and genanki packages")
class TestAnkiConnectEngine(unittest.TestCase):
    def setUp(self):
        import anki.lang
        from anki.collection import Collection
        anki.lang.set_lang("en")
        self.original_cwd = os.getcwd()
        self.temp = tempfile.TemporaryDirectory(prefix="forge-anki-connect-test-")
        self.col = Collection(os.path.join(self.temp.name, "collection.anki2"))
        self.actions = []
        self.patches = [mock.patch.object(ac, "BACKUP_DIR", os.path.join(self.temp.name, "backups")),
                        mock.patch.object(ac, "invoke", self.invoke)]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.col.close()
        os.chdir(self.original_cwd)
        self.temp.cleanup()

    def invoke(self, action, **params):
        from anki.exporting import AnkiPackageExporter
        from anki.importing.apkg import AnkiPackageImporter
        self.actions.append(action)
        if action == "deckNames":
            return [deck.name for deck in self.col.decks.all_names_and_ids()]
        if action == "exportPackage":
            exporter = AnkiPackageExporter(self.col)
            exporter.did = self.col.decks.by_name(params["deck"])["id"]
            exporter.includeSched = params["includeSched"]
            exporter.exportInto(params["path"])
            return True
        if action == "importPackage":
            AnkiPackageImporter(self.col, params["path"]).run()
            return True
        raise AssertionError(f"Unexpected API action: {action}")

    def package(self, filename, deck_name, notes, modified=None):
        import genanki
        builder = load("build_deck")
        deck = genanki.Deck(builder.stable_id(deck_name), deck_name)
        for guid, back in notes:
            deck.add_note(genanki.Note(model=builder.BASIC_MODEL, fields=["Question", back],
                                      guid=guid, tags=["original"]))
        path = os.path.join(self.temp.name, filename + ".apkg")
        genanki.Package(deck).write_to_file(path, timestamp=modified or time.time() - 100)
        return path

    def note(self, guid):
        nid = self.col.db.scalar("SELECT id FROM notes WHERE guid=?", guid)
        return self.col.get_note(nid)

    def schedule(self, guid):
        return self.col.db.all("SELECT c.id,c.ord,c.type,c.queue,c.due,c.ivl,c.factor,c.reps,c.lapses,c.data "
                               "FROM cards c JOIN notes n ON n.id=c.nid WHERE n.guid=? ORDER BY c.ord", guid)

    def test_cross_deck_guid_update_has_original_deck_backup(self):
        original = self.package("original", "Original", [("same-guid", "old")])
        incoming = self.package("incoming", "Renamed", [("same-guid", "changed")], time.time() + 5)
        with redirect_stdout(io.StringIO()):
            self.invoke("importPackage", path=original)
            ac.push(incoming)
        self.assertEqual(self.note("same-guid")["Back"], "changed")
        self.assertEqual(len(self.col.find_notes("")), 1)
        stamp = ac._backup_stamps()[-1]
        saved = os.path.join(ac.BACKUP_DIR, stamp, "Original.apkg")
        notes = ac._raw_package_notes(saved)
        self.assertEqual(notes[0]["guid"], "same-guid")
        self.assertEqual(notes[0]["fields"][1], "old")

    def test_restore_old_content_recovers_deleted_notes_preserves_current_progress(self):
        original = self.package("original", "A", [("kept", "old answer"), ("deleted", "deleted answer")])
        with redirect_stdout(io.StringIO()):
            self.invoke("importPackage", path=original)
            deleted = self.note("deleted")
            self.col.db.execute("UPDATE cards SET type=2,queue=2,due=222,ivl=14,reps=6,factor=2500 WHERE nid=?", deleted.id)
            deleted_schedule = self.schedule("deleted")
            paths = ac._backup_decks(["A"])
        with open(paths[0], "rb") as stream:
            backup_bytes = stream.read()
        kept = self.note("kept")
        kept["Back"] = "new answer"
        kept.tags = ["changed"]
        self.col.update_note(kept)
        self.col.db.execute("UPDATE notes SET mod=mod+20 WHERE id=?", kept.id)
        self.col.db.execute("UPDATE cards SET type=2,queue=2,due=999,ivl=33,reps=17,factor=2500 WHERE nid=?", kept.id)
        cid = self.schedule("kept")[0][0]
        self.col.db.execute("INSERT INTO revlog VALUES (?,?,?,?,?,?,?,?,?)",
                            int(time.time() * 1000), cid, -1, 3, 33, 14, 2500, 5000, 1)
        reviews = self.col.db.all("SELECT id,cid,ease,ivl,lastIvl,factor,time,type FROM revlog WHERE cid=?", cid)
        self.col.remove_notes([self.note("deleted").id])
        introduced = self.col.new_note(self.col.models.by_name("Anki-Karten Basic"))
        introduced["Front"], introduced["Back"] = "New question", "keep me"
        self.col.add_note(introduced, self.col.decks.id("A"))
        before = self.schedule("kept")
        with redirect_stdout(io.StringIO()) as output:
            ac.restore(os.path.basename(os.path.dirname(paths[0])))
        self.assertIn("restored and verified", output.getvalue())
        self.assertEqual(self.note("kept")["Back"], "old answer")
        self.assertEqual(self.note("kept").tags, ["original"])
        self.assertEqual(self.note("deleted")["Back"], "deleted answer")
        self.assertEqual(self.schedule("deleted"), deleted_schedule)
        self.assertEqual(self.col.get_note(introduced.id)["Back"], "keep me")
        self.assertEqual(self.schedule("kept"), before)
        self.assertEqual(self.col.db.all("SELECT id,cid,ease,ivl,lastIvl,factor,time,type FROM revlog WHERE cid=?", cid), reviews)
        with open(paths[0], "rb") as stream:
            self.assertEqual(stream.read(), backup_bytes)
        self.assertNotIn("sync", self.actions)

    def test_restore_detects_silently_ignored_import(self):
        import shutil
        original = self.package("original", "A", [("kept", "old answer")])
        with redirect_stdout(io.StringIO()):
            self.invoke("importPackage", path=original)
            paths = ac._backup_decks(["A"])
        kept = self.note("kept")
        kept["Back"] = "new answer"
        self.col.update_note(kept)
        self.col.db.execute("UPDATE notes SET mod=mod+20 WHERE id=?", kept.id)
        with mock.patch.object(ac, "_force_restore_package", lambda src, dst, modified: shutil.copy2(src, dst)), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ac.AnkiConnectError, "verification failed"):
                ac.restore(os.path.basename(os.path.dirname(paths[0])))
        self.assertNotIn("restored and verified", output.getvalue())

    def test_restore_accepts_modern_compressed_snapshot(self):
        from anki.collection import ExportAnkiPackageOptions
        original = self.package("original", "A", [("kept", "old answer")])
        with redirect_stdout(io.StringIO()):
            self.invoke("importPackage", path=original)
        kept = self.note("kept")
        kept["Back"] = '<img src="asset.png"> old answer'
        self.col.update_note(kept)
        media_bytes = b"synthetic media fixture"
        self.col.media.write_data("asset.png", media_bytes)
        snapshot = os.path.join(ac.BACKUP_DIR, "20260905-120000")
        os.makedirs(snapshot)
        self.col.export_anki_package(out_path=os.path.join(snapshot, "A.apkg"),
                                     options=ExportAnkiPackageOptions(with_scheduling=True, with_media=True),
                                     limit=None)
        kept = self.note("kept")
        kept["Back"] = "new answer"
        self.col.update_note(kept)
        os.unlink(os.path.join(self.col.media.dir(), "asset.png"))
        with redirect_stdout(io.StringIO()):
            ac.restore("20260905-120000")
        self.assertEqual(self.note("kept")["Back"], '<img src="asset.png"> old answer')
        with open(os.path.join(self.col.media.dir(), "asset.png"), "rb") as stream:
            self.assertEqual(stream.read(), media_bytes)


if __name__ == "__main__":
    unittest.main()
