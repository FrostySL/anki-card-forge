"""Disk-backed drafts and immutable, revision-specific card review submissions."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from _card_media import local_image_sources
from _card_schema import TEXT_FIELDS, validate_schema
from runtime_assets import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "decks" / "_reviews"
_SUFFIX = ".review.json"


class ReviewConflict(ValueError):
    """The caller edited an older draft version or an already submitted review."""


def _status(feedback):
    if feedback is None:
        return "open"
    return "accepted" if feedback["ok"] else "change_requested"


def deck_revision(raw, project_root=PROJECT_ROOT):
    """Hash the exact JSON bytes and the contents of each referenced local image."""
    data = json.loads(raw.decode("utf-8"))
    validate_schema(data)
    paths = set()
    for card in data["cards"]:
        if card.get("type") == "occlusion":
            paths.add(card["image"])
        for key in TEXT_FIELDS:
            # The occlusion header, like the source citation, renders as plain text.
            markup = card.get(key, "")
            if key != "header" and "<img" in markup.lower():
                paths.update(local_image_sources(markup))
    digest = hashlib.sha256(raw).hexdigest()
    if not paths:
        return digest
    root = Path(project_root).resolve()
    images = []
    for name in sorted(paths):
        relative = Path(name)
        if relative.anchor:
            raise ValueError(f"Review image paths must be project-relative: {name}")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Review image is outside the project: {name}")
        images.append((name, sha256_file(path)))
    manifest = json.dumps(["forge-review-v1", digest, images], separators=(",", ":"))
    return hashlib.sha256(manifest.encode("ascii")).hexdigest()


def source_revision(source, project_root=PROJECT_ROOT):
    return deck_revision(Path(source).read_bytes(), project_root)


def _submission_path(source, revision, root):
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise ValueError("Invalid SHA-256 revision.")
    source_key = os.fsencode(os.path.normcase(str(Path(source).resolve())))
    directory = Path(root).resolve() / hashlib.sha256(source_key).hexdigest()
    return directory / (revision + _SUFFIX)


def wait_for_submission(source, revision, timeout, root=DEFAULT_ROOT):
    """Wait for this exact deck and revision, including an earlier submission."""
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("Timeout must be a finite, nonnegative number of seconds.")
    target = _submission_path(source, revision, root)
    deadline = time.monotonic() + timeout
    while not target.is_file():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"No submission within {timeout:g} seconds for revision {revision}.")
        time.sleep(min(remaining, 0.25))
    return target


class ReviewStore:
    def __init__(self, source, revision, deck, cards, root=DEFAULT_ROOT, *,
                 project_root=PROJECT_ROOT, snapshot=None):
        self.source = Path(source).resolve()
        self.revision = revision
        self.deck = deck
        self.cards = cards
        self.project_root = Path(project_root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot is not None else None
        self.ids = {card["id"] for card in cards}
        if len(self.ids) != len(cards):
            raise ValueError("Card variant IDs must be unique within a deck revision.")
        self.path = _submission_path(self.source, revision, root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.database = self.path.parent / "drafts.sqlite3"
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS drafts "
                       "(revision TEXT PRIMARY KEY, version INTEGER NOT NULL, feedback TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO drafts VALUES (?, 0, '{}')", (revision,))

    @contextmanager
    def _transaction(self):
        # One SQLite writer per source, including across CLI/server processes.
        # Hold this lock through publication of the immutable JSON so a pending
        # save always observes either the editable draft or its final submission.
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def _draft(self, db):
        version, feedback = db.execute("SELECT version, feedback FROM drafts WHERE revision=?",
                                       (self.revision,)).fetchone()
        if self.path.is_file():
            # The submitted JSON remains the record even if the draft DB is
            # subsequently removed. Earlier submissions also contain raw feedback.
            cards = json.loads(self.path.read_text(encoding="utf-8"))["cards"]
            return version, {card["id"]: card["feedback"] for card in cards if card["feedback"] is not None}
        return version, json.loads(feedback)

    def _current_revision(self):
        try:
            return source_revision(self.source, self.project_root)
        except (OSError, ValueError):
            return None

    def _state(self, version, feedback, current_revision):
        previous = max((p for p in self.path.parent.glob("*" + _SUFFIX) if p != self.path),
                       key=lambda p: p.stat().st_mtime_ns, default=None)
        submission = None
        if self.path.is_file():
            submission = {"path": str(self.path), "prompt": (
                f"Lies meine abgeschickte Kartenreview unter „{self.path}“ und fasse die gewünschten "
                "Änderungen pro Karte zusammen. Prüfe dabei die Deckrevision."
            )}
        return {
            "deck": self.deck, "revision": self.revision, "current_revision": current_revision,
            "cards": self.cards, "feedback": feedback,
            "statuses": {card_id: _status(feedback.get(card_id)) for card_id in self.ids},
            "version": version, "submission": submission,
            "previous_submission": {"revision": previous.name.removesuffix(_SUFFIX),
                                    "path": str(previous)} if previous else None,
        }

    def state(self):
        current_revision = self._current_revision()
        with self._transaction() as db:
            return self._state(*self._draft(db), current_revision)

    @staticmethod
    def _check_version(requested, current):
        if type(requested) is not int or requested < 0:
            raise ValueError("Ungültige Entwurfsversion.")
        if requested != current:
            raise ReviewConflict("Der Entwurf wurde in einem anderen Fenster geändert.")

    def save(self, card_id, ok, comment, version):
        if not isinstance(card_id, str) or card_id not in self.ids:
            raise ValueError("Unbekannte Kartenvariante.")
        if type(ok) is not bool or not isinstance(comment, str):
            raise ValueError("Ungültige Rückmeldung.")
        try:
            comment.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Der Kommentar enthält ein ungültiges Unicode-Zeichen.") from None
        current_revision = self._current_revision()
        with self._transaction() as db:
            if self.path.is_file():
                raise ReviewConflict("Diese Review wurde bereits abgeschickt.")
            current, feedback = self._draft(db)
            self._check_version(version, current)
            feedback[card_id] = {"ok": ok, "comment": comment}
            db.execute("UPDATE drafts SET version=?, feedback=? WHERE revision=?",
                       (current + 1, json.dumps(feedback), self.revision))
            return self._state(current + 1, feedback, current_revision)

    def submit(self, version):
        current_revision = self._current_revision()
        with self._transaction() as db:
            current, feedback = self._draft(db)
            if not self.path.is_file():
                self._check_version(version, current)
                # The JSON itself marks the submitted state. No DB update needs
                # to commit after publishing it, even if the server stops here.
                self._publish(feedback, current_revision)
            return self._state(current, feedback, current_revision)

    def _publish(self, feedback, current_revision):
        cards = []
        summary = {"accepted": 0, "change_requested": 0, "open": 0}
        for card in self.cards:
            identity = {key: card[key] for key in ("id", "note", "variant", "label", "guid") if key in card}
            response = feedback.get(card["id"])
            status = _status(response)
            summary[status] += 1
            cards.append({**identity, "feedback": response, "status": status})
        document = {
            "deck": self.deck, "source": str(self.source), "revision": self.revision,
            "current_revision_at_submission": current_revision,
            "review_project_root": str(self.project_root),
            "revision_check": 'From the review_project_root directory, run .\\forge.cmd review "<source>" --show-revision '
                              '(Linux: python3 tools/forge.py review "<source>" --show-revision) with the source path above. '
                              'Compare its output with revision before attributing feedback to the current deck. '
                              'The revision includes local image contents. Note numbers start at 1.',
            "submitted_at": datetime.now(timezone.utc).isoformat(), "summary": summary, "cards": cards,
        }
        if self.snapshot is not None:
            document["reviewed_source_snapshot"] = str(self.snapshot)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            # Preserve even an isolated surrogate from an escaped deck label as
            # a JSON escape, while keeping ordinary Unicode text readable.
            with os.fdopen(descriptor, "w", encoding="utf-8", errors="backslashreplace") as f:
                json.dump(document, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
