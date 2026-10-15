#!/usr/bin/env python3
"""Import stable JPEG files into Immich without changing the source files."""

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import http.client
import json
import os
import sqlite3
import stat
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

VERSION = "0.1.0"
MAX_RESPONSE = 2 * 1024 * 1024


class ImportErrorSafe(Exception):
    """An error whose message contains no server or user-supplied values."""


def fingerprint(st):
    return f"{st.st_dev}:{st.st_ino}:{st.st_size}:{st.st_mtime_ns}:{st.st_ctime_ns}"


def private_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ImportErrorSafe("Key file must be owned by this user with mode 600 or 400.")
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ImportErrorSafe("Key file is too large.")
    key = raw.decode("ascii").strip()
    if not key or any(not 33 <= ord(c) <= 126 for c in key):
        raise ImportErrorSafe("Key file must contain one nonempty ASCII token.")
    return key


def load_config(path):
    with open(path, "rb") as stream:
        cfg = tomllib.load(stream)
    allowed = {
        "immich_url",
        "api_key_file",
        "inbox",
        "state_dir",
        "album",
        "album_id",
        "settle_seconds",
        "max_file_mb",
        "allow_insecure_http",
        "timeout_seconds",
    }
    if set(cfg) - allowed:
        raise ImportErrorSafe("Unknown configuration option; compare with config.example.toml.")
    for name in ("immich_url", "api_key_file", "inbox", "state_dir", "album"):
        if not isinstance(cfg.get(name), str) or not cfg[name].strip():
            raise ImportErrorSafe("A required configuration string is missing.")
    for name, default, low, high in (
        ("settle_seconds", 60, 1, 86400),
        ("max_file_mb", 100, 1, 1024),
        ("timeout_seconds", 120, 1, 3600),
    ):
        cfg.setdefault(name, default)
        if type(cfg[name]) is not int or not low <= cfg[name] <= high:
            raise ImportErrorSafe("A numeric configuration option is outside its allowed range.")
    cfg.setdefault("allow_insecure_http", False)
    if type(cfg["allow_insecure_http"]) is not bool:
        raise ImportErrorSafe("allow_insecure_http must be a boolean.")
    if "album_id" in cfg:
        cfg["album_id"] = valid_id(cfg["album_id"])
    for name in ("api_key_file", "inbox", "state_dir"):
        p = Path(cfg[name])
        if not p.is_absolute():
            raise ImportErrorSafe("Filesystem paths in configuration must be absolute.")
        cfg[name] = p
    inbox = cfg["inbox"].resolve(strict=True)
    if not inbox.is_dir() or cfg["inbox"].is_symlink():
        raise ImportErrorSafe("Inbox must be a real directory.")
    for name in ("state_dir", "api_key_file"):
        resolved = cfg[name].resolve()
        if resolved == inbox or inbox in resolved.parents:
            raise ImportErrorSafe("State and key must be outside the camera inbox.")
    cfg["inbox"] = inbox
    url = urllib.parse.urlsplit(cfg["immich_url"])
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or url.path not in ("", "/", "/api", "/api/")
        or any(ord(c) < 33 or ord(c) > 126 for c in cfg["immich_url"])
    ):
        raise ImportErrorSafe("Use an HTTP(S) origin, optionally ending in /api; no credentials.")
    if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
        if not cfg["allow_insecure_http"]:
            raise ImportErrorSafe("Remote HTTP requires allow_insecure_http=true; prefer HTTPS.")
    cfg["immich_url"] = urllib.parse.urlunsplit((url.scheme, url.netloc, "/api", "", ""))
    return cfg


def valid_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ImportErrorSafe("Immich returned an invalid identifier.") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImportErrorSafe("Redirect refused; configure the final Immich URL.")


class Immich:
    def __init__(self, cfg, key):
        self.cfg = cfg
        self.key = key
        self.album_id = cfg.get("album_id")
        # Ignore environment proxies so an unrelated shell setting cannot route photo uploads.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None, headers=None):
        req = urllib.request.Request(  # noqa: S310 - load_config permits HTTP(S) only.
            self.cfg["immich_url"] + path,
            data=data,
            method=method,
            headers={"x-api-key": self.key, **(headers or {})},
        )
        try:
            with self.opener.open(req, timeout=self.cfg["timeout_seconds"]) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ImportErrorSafe("Immich response exceeded the size limit.")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise ImportErrorSafe(
                f"Immich HTTP {code}; check URL, API permissions and server."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise ImportErrorSafe(
                "Immich connection failed; check network, TLS and server."
            ) from None
        except (ValueError, UnicodeError):
            raise ImportErrorSafe("Immich returned invalid JSON.") from None

    def json(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        return self.request(method, path, data, {"Content-Type": "application/json"})

    def check(self, digest):
        reply = self.json(
            "POST",
            "/assets/bulk-upload-check",
            {
                "assets": [{"id": "candidate", "checksum": digest}],
            },
        )
        rows = reply.get("results") if isinstance(reply, dict) else None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ImportErrorSafe("Unexpected duplicate-check response.")
        result = rows[0]
        if result.get("id") != "candidate":
            raise ImportErrorSafe("Duplicate-check response did not match the request.")
        if result.get("action") == "accept":
            return None
        if result.get("action") == "reject" and result.get("reason") == "duplicate":
            if result.get("isTrashed") is not False:
                raise ImportErrorSafe(
                    "Duplicate is trashed or trash status is unknown; review in Immich."
                )
            return valid_id(result.get("assetId"))
        raise ImportErrorSafe("Immich rejected the file; source retained for review.")

    def upload(self, snapshot, name, timestamp):
        boundary = uuid.uuid4().hex
        safe_name = "".join(c for c in name if 32 <= ord(c) <= 126 and c not in '\\"/')[:180]
        safe_name = safe_name or "image.jpg"
        date = dt.datetime.fromtimestamp(timestamp, dt.UTC).isoformat()
        with tempfile.TemporaryFile(dir=self.cfg["state_dir"]) as body:
            for field in ("fileCreatedAt", "fileModifiedAt"):
                body.write(
                    (
                        f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"'
                        f"\r\n\r\n{date}\r\n"
                    ).encode()
                )
            body.write(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="assetData"; '
                    f'filename="{safe_name}"\r\nContent-Type: image/jpeg\r\n\r\n'
                ).encode()
            )
            snapshot.seek(0)
            while chunk := snapshot.read(1024 * 1024):
                body.write(chunk)
            body.write(f"\r\n--{boundary}--\r\n".encode())
            length = body.tell()
            body.seek(0)
            reply = self.request(
                "POST",
                "/assets",
                body,
                {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(length),
                },
            )
        if not isinstance(reply, dict) or reply.get("status") not in ("created", "duplicate"):
            raise ImportErrorSafe("Unexpected upload response; source retained for retry.")
        return valid_id(reply.get("id")), reply["status"]

    def ensure_album(self):
        if self.album_id:
            return self.album_id
        albums = self.json("GET", "/albums")
        if not isinstance(albums, list) or any(not isinstance(a, dict) for a in albums):
            raise ImportErrorSafe("Unexpected album list response.")
        matches = [a for a in albums if a.get("albumName") == self.cfg["album"]]
        if len(matches) > 1:
            raise ImportErrorSafe("Multiple albums have this name; configure album_id.")
        if matches:
            if matches[0].get("shared") is not False:
                raise ImportErrorSafe(
                    "Matching album is shared; use an explicit album_id to opt in."
                )
            album = matches[0]
        else:
            album = self.json("POST", "/albums", {"albumName": self.cfg["album"]})
        if not isinstance(album, dict):
            raise ImportErrorSafe("Unexpected album creation response.")
        self.album_id = valid_id(album.get("id"))
        return self.album_id

    def add_to_album(self, asset_id):
        album_id = self.ensure_album()
        result = self.json("PUT", f"/albums/{album_id}/assets", {"ids": [asset_id]})
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise ImportErrorSafe("Unexpected album update response.")
        row = result[0]
        if row.get("id") != asset_id or not (
            row.get("success") is True
            or (row.get("success") is False and row.get("error") == "duplicate")
        ):
            raise ImportErrorSafe("Album addition failed; source retained for retry.")


@contextlib.contextmanager
def state_db(cfg, key):
    directory = cfg["state_dir"]
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = directory.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ImportErrorSafe("State directory must be owned by this user with mode 700.")
    lock_fd = os.open(directory / "run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ImportErrorSafe("Another importer is using this state directory.") from None
        db_path = directory / "state.sqlite3"
        if db_path.is_symlink():
            raise ImportErrorSafe("State database must not be a symbolic link.")
        db = sqlite3.connect(db_path)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS meta (value TEXT)")
            identity = hashlib.sha256(
                json.dumps(
                    [
                        cfg["immich_url"],
                        str(cfg["inbox"]),
                        cfg["album"],
                        cfg.get("album_id"),
                        key,
                    ]
                ).encode()
            ).hexdigest()
            old = db.execute("SELECT value FROM meta").fetchone()
            if old and old[0] != identity:
                raise ImportErrorSafe(
                    "State belongs to another configuration/key; use a new state_dir."
                )
            if not old:
                db.execute("INSERT INTO meta VALUES (?)", (identity,))
            db.execute(
                "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, "
                "fingerprint TEXT, seen REAL, done INTEGER DEFAULT 0)"
            )
            db.commit()
            yield db
        finally:
            db.close()


def candidates(inbox):
    def walk_error(_):
        raise ImportErrorSafe("Cannot read part of the inbox; check folder permissions.")

    for root, dirs, files, fd in os.fwalk(inbox, follow_symlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "@", "#")))
        for name in sorted(files):
            if name.startswith(".") or Path(name).suffix.lower() not in (".jpg", ".jpeg"):
                continue
            yield str(Path(root).relative_to(inbox) / name), name, fd


def import_file(cfg, db, client, relative, name, dir_fd, dry_run, now):
    try:
        source_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return "waiting"
    with os.fdopen(source_fd, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            return "skipped"
        fp = fingerprint(before)
        row = db.execute(
            "SELECT fingerprint, seen, done FROM files WHERE path=?", (relative,)
        ).fetchone()
        if row is None or row[0] != fp:
            db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?, 0)", (relative, fp, now))
            db.commit()
            return "waiting"
        if row[2]:
            return "recorded"
        if now - row[1] < cfg["settle_seconds"]:
            return "waiting"
        if before.st_size < 4 or before.st_size > cfg["max_file_mb"] * 1024 * 1024:
            raise ImportErrorSafe("JPEG size is outside the configured limit; source retained.")
        with tempfile.TemporaryFile(dir=cfg["state_dir"]) as snapshot:
            digest = hashlib.sha1(usedforsecurity=False)
            remaining = before.st_size
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    return "waiting"
                snapshot.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            if source.read(1) or fingerprint(os.fstat(source.fileno())) != fp:
                return "waiting"
            snapshot.seek(0)
            start = snapshot.read(2)
            snapshot.seek(-2, os.SEEK_END)
            if start != b"\xff\xd8" or snapshot.read(2) != b"\xff\xd9":
                raise ImportErrorSafe(
                    "Incomplete JPEG markers; source retained for retransmission."
                )
            asset_id = client.check(digest.hexdigest())
            if dry_run:
                return "would_duplicate" if asset_id else "would_upload"
            # Resolve ambiguity before accepting new photos into the destination.
            client.ensure_album()
            status = "duplicate"
            if asset_id is None:
                asset_id, status = client.upload(snapshot, name, before.st_mtime)
            client.add_to_album(asset_id)
        db.execute("UPDATE files SET done=1 WHERE path=? AND fingerprint=?", (relative, fp))
        db.commit()
        return status


def run(cfg, dry_run=False):
    key = private_file(cfg["api_key_file"])
    client = Immich(cfg, key)
    counts = dict.fromkeys(
        (
            "created",
            "duplicate",
            "recorded",
            "waiting",
            "skipped",
            "would_upload",
            "would_duplicate",
            "failed",
        ),
        0,
    )
    with state_db(cfg, key) as db:
        for relative, name, fd in candidates(cfg["inbox"]):
            try:
                status = import_file(cfg, db, client, relative, name, fd, dry_run, time.time())
                counts[status] += 1
            except ImportErrorSafe as exc:
                counts["failed"] += 1
                print(f"error: {exc}", file=sys.stderr)
            except (OSError, ValueError, sqlite3.Error):
                counts["failed"] += 1
                print("error: local file operation failed; source retained.", file=sys.stderr)
    print(" ".join(f"{name}={count}" for name, count in counts.items()))
    return 1 if counts["failed"] else 0


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid arguments; use --help. Put credentials in a key file.\n")


def main(argv=None):
    os.umask(0o077)
    parser = SafeParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--config", required=True, help="path to your private TOML configuration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="check stable JPEGs against Immich; no uploads or album changes",
    )
    args = parser.parse_args(argv)
    try:
        return run(load_config(args.config), args.dry_run)
    except ImportErrorSafe as exc:
        print(f"error: {exc}", file=sys.stderr)
    except (OSError, ValueError, TypeError, sqlite3.Error):
        print(
            "error: invalid configuration or inaccessible local files; check setup.",
            file=sys.stderr,
        )
    except KeyboardInterrupt:
        print("Interrupted; source files retained. Run again to resume.", file=sys.stderr)
        return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
