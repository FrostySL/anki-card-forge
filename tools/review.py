#!/usr/bin/env python3
"""Serve a local Forge card review or wait for its immutable submission."""
import argparse
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import urlencode

from review_store import (
    DEFAULT_ROOT, ReviewConflict, ReviewStore, deck_revision, source_revision,
    wait_for_submission,
)


ROOT = Path(__file__).resolve().parent.parent
UI = Path(__file__).resolve().with_name("review_ui")
HOST = "127.0.0.1"
ASSETS = {"index.html": "text/html; charset=utf-8", "review.css": "text/css; charset=utf-8",
          "review.js": "text/javascript; charset=utf-8"}
UI_LANGUAGES = ("de", "en", "es", "fr", "pt-BR", "zh-Hans")


def localization_script():
    """Deliver the local catalogs with the script so switching languages needs no request."""
    catalogs = {lang: json.loads((UI / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
                for lang in UI_LANGUAGES}
    data = json.dumps(catalogs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return (UI / "i18n.js").read_bytes() + b"\nconst ForgeLocale = createReviewLocale(" + data + b");\n"


def render_snapshot(raw, revision, storage=DEFAULT_ROOT):
    """Publish all sides and their source together. Concurrent renders may race safely."""
    cache = storage / "previews" / "v4"
    target = cache / revision
    if target.is_dir():
        return target
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="render-", dir=cache) as work:
        work = Path(work)
        snapshot = work / "source.json"
        snapshot.write_bytes(raw)
        output = work / "images"
        command = ([sys.executable, ROOT / "tools/preview.py"] if os.name == "nt"
                   else [ROOT / "tools/preview.sh"])
        subprocess.run([*command, snapshot, "--review-output", output], check=True, cwd=ROOT)
        if deck_revision(raw, ROOT) != revision:
            raise ValueError("A local image changed during rendering. Restart the review.")
        snapshot.rename(output / "source.json")
        try:
            output.rename(target)
        except OSError:
            if not target.is_dir():
                raise
    return target


class ReviewHandler(BaseHTTPRequestHandler):
    """Serve only this review's page, preview images and two JSON mutations."""

    def __init__(self, *args, store, prefix, images, **kwargs):
        self.store = store
        self.prefix = prefix
        self.images = images
        super().__init__(*args, **kwargs)

    def log_request(self, *args):
        pass  # Keep private session URLs and navigation out of terminal logs.

    def headers_for(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; img-src 'self'; script-src 'self'; "
                         "style-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'none'")
        self.end_headers()

    def json_response(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.headers_for(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def route_name(self):
        authority = f"{HOST}:{self.server.server_port}"
        canonical = HOST if self.server.server_port == 80 else authority
        if self.headers.get("Host") not in (canonical, authority) or not self.path.startswith(self.prefix):
            return None
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://{canonical}":
            return None
        return self.path[len(self.prefix):].partition("?")[0]

    def do_GET(self):
        name = self.route_name()
        try:
            if name == "api/state":
                self.json_response(self.store.state())
                return
            if name == "i18n.js":
                body = localization_script()
                self.headers_for(HTTPStatus.OK, "text/javascript; charset=utf-8", len(body))
                self.wfile.write(body)
                return
            if name in ("", *ASSETS):
                asset = name or "index.html"
                path, mime = UI / asset, ASSETS[asset]
            elif name in self.images:
                path, mime = self.images[name], "image/png"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            with path.open("rb") as stream:
                self.headers_for(HTTPStatus.OK, mime, os.fstat(stream.fileno()).st_size)
                shutil.copyfileobj(stream, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Changing cards can cancel outstanding image downloads.
        except (OSError, sqlite3.Error) as exc:
            self.json_response({"error": str(exc), "error_key": "apiStorage"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        name = self.route_name()
        if name not in ("api/save", "api/submit"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024 * 1024:
                self.json_response({"error": "Ungültige Anfragegröße.", "error_key": "apiTooLarge"}, HTTPStatus.BAD_REQUEST)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            fields = ("id", "ok", "comment", "version") if name == "api/save" else ("version",)
            if not isinstance(payload, dict) or set(payload) != set(fields):
                raise ValueError("Ungültige Felder für diese Anfrage.")
            if name == "api/save":
                result = self.store.save(payload["id"], payload["ok"], payload["comment"], payload["version"])
            else:
                result = self.store.submit(payload["version"])
            self.json_response(result)
        except ReviewConflict as exc:
            self.json_response({"error": str(exc), "error_key": "otherWindow"}, HTTPStatus.CONFLICT)
        except (ValueError, TypeError) as exc:
            self.json_response({"error": str(exc), "error_key": "apiInvalid"}, HTTPStatus.BAD_REQUEST)
        except (OSError, sqlite3.Error) as exc:
            self.json_response({"error": str(exc), "error_key": "apiStorage"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(source, port, ui_language=None):
    raw = source.read_bytes()
    revision = deck_revision(raw, ROOT)
    directory = render_snapshot(raw, revision)
    cards = json.loads((directory / "cards.json").read_text(encoding="utf-8"))
    if not cards:
        raise ValueError("The deck has no reviewable cards.")
    store = ReviewStore(source, revision, json.loads(raw)["deck"], cards, snapshot=directory / "source.json")
    prefix = f"/{secrets.token_urlsafe(24)}/"
    images = {card[side]: directory / card[side] for card in cards
              for side in ("front", "back", "front_light", "back_light") if side in card}
    handler = partial(ReviewHandler, store=store, prefix=prefix, images=images)
    with ThreadingHTTPServer((HOST, port), handler) as server:
        print(f"Deck revision: {revision}", flush=True)
        query = "?" + urlencode({"lang": ui_language}) if ui_language is not None else ""
        print(f"http://{HOST}:{server.server_port}{prefix}{query}", flush=True)
        print("Open this URL to review. Stop the server with Ctrl+C.", flush=True)
        server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path, help="path to the cards.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--wait", action="store_true", help="print the submitted review path when available")
    mode.add_argument("--show-revision", action="store_true", help="print the current deck revision")
    parser.add_argument("--timeout", type=float, help="seconds to wait (default: 300)")
    parser.add_argument("--revision", help="wait for this exact revision (default: current)")
    parser.add_argument("--port", type=int, help="loopback server port (default: automatically selected)")
    parser.add_argument("--ui-language", metavar="TAG",
                        help="open the review in the chat language (e.g. fr or fr-CA). "
                             "Unsupported languages use English.")
    args = parser.parse_args(argv)
    if (args.timeout is not None or args.revision is not None) and not args.wait:
        parser.error("--timeout and --revision require --wait")
    if args.port is not None and (args.wait or args.show_revision or not 0 <= args.port <= 65535):
        parser.error("--port requires server mode and a number from 0 to 65535")
    if args.ui_language is not None and (args.wait or args.show_revision):
        parser.error("--ui-language requires server mode")
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout < 0):
        parser.error("--timeout must be a finite, nonnegative number of seconds")
    if args.revision is not None and not re.fullmatch("[a-fA-F0-9]{64}", args.revision):
        parser.error("--revision must be a full SHA-256 digest")
    source = args.cards.resolve()
    try:
        if args.show_revision:
            print(source_revision(source))
        elif args.wait:
            revision = args.revision.lower() if args.revision else source_revision(source)
            timeout = 300 if args.timeout is None else args.timeout
            print(wait_for_submission(source, revision, timeout), flush=True)
        else:
            serve(source, args.port or 0, args.ui_language)
    except KeyboardInterrupt:
        return 130
    except TimeoutError as exc:
        print(exc, file=sys.stderr)
        return 3
    except (OSError, ValueError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"Review: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
