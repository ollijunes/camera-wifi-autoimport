import contextlib
import hashlib
import json
import os
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

import camera_import as app

ASSET = "00000000-0000-4000-8000-000000000001"
ALBUM = "00000000-0000-4000-8000-000000000002"
SYNTHETIC_KEY = hashlib.sha256(b"camera importer public test fixture").hexdigest()
JPEG = b"\xff\xd8synthetic marker fixture; not a photograph\xff\xd9"


@pytest.fixture
def cfg(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    key = tmp_path / "immich.key"
    key.write_text(SYNTHETIC_KEY)
    key.chmod(0o600)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    return {
        "inbox": inbox,
        "state_dir": state,
        "api_key_file": key,
        "immich_url": "http://127.0.0.1:2283/api",
        "album": "Test camera",
        "settle_seconds": 60,
        "max_file_mb": 1,
        "timeout_seconds": 2,
        "allow_insecure_http": False,
    }


class FakeImmich:
    def __init__(self):
        self.assets = set()
        self.uploads = []
        self.adds = []
        self.fail_album = False

    def check(self, digest):
        return ASSET if digest in self.assets else None

    def ensure_album(self):
        return ALBUM

    def upload(self, snapshot, name, timestamp):
        snapshot.seek(0)
        data = snapshot.read()
        self.uploads.append(data)
        self.assets.add(hashlib.sha1(data, usedforsecurity=False).hexdigest())
        return ASSET, "created"

    def add_to_album(self, asset):
        if self.fail_album:
            raise app.ImportErrorSafe("Album addition failed; source retained for retry.")
        self.adds.append(asset)


def invoke(cfg, client, now, dry=False):
    with (
        patch.object(app, "Immich", return_value=client),
        patch.object(app.time, "time", return_value=now),
    ):
        return app.run(cfg, dry)


def test_upload_duplicate_and_repeat_keep_sources(cfg):
    photo = cfg["inbox"] / "IMG_0001.JPG"
    photo.write_bytes(JPEG)
    os.utime(photo, (100, 100))  # Camera may restore an old capture timestamp.
    client = FakeImmich()
    assert invoke(cfg, client, 1000) == 0
    assert not client.uploads
    assert invoke(cfg, client, 1059) == 0
    assert not client.uploads
    assert invoke(cfg, client, 1060) == 0
    assert client.uploads == [JPEG]
    assert client.adds == [ASSET]
    assert invoke(cfg, client, 1200) == 0
    assert len(client.uploads) == 1
    (cfg["inbox"] / "renamed.jpeg").write_bytes(JPEG)
    invoke(cfg, client, 1300)
    invoke(cfg, client, 1360)
    assert len(client.uploads) == 1
    assert client.adds == [ASSET, ASSET]
    assert photo.read_bytes() == JPEG
    assert (cfg["inbox"] / "renamed.jpeg").read_bytes() == JPEG


def test_album_failure_is_retried_without_second_upload(cfg):
    (cfg["inbox"] / "photo.jpg").write_bytes(JPEG)
    client = FakeImmich()
    invoke(cfg, client, 1000)
    client.fail_album = True
    assert invoke(cfg, client, 1060) == 1
    client.fail_album = False
    assert invoke(cfg, client, 1120) == 0
    assert client.uploads == [JPEG]
    assert client.adds == [ASSET]


def test_lost_upload_response_is_recovered_by_checksum(cfg):
    (cfg["inbox"] / "photo.jpg").write_bytes(JPEG)
    client = FakeImmich()
    upload = client.upload

    def disconnected(*args):
        upload(*args)
        raise app.ImportErrorSafe("Immich connection failed; check network, TLS and server.")

    invoke(cfg, client, 1000)
    with patch.object(client, "upload", side_effect=disconnected):
        assert invoke(cfg, client, 1060) == 1
    assert invoke(cfg, client, 1120) == 0
    assert client.uploads == [JPEG]
    assert client.adds == [ASSET]


def test_source_changed_while_copying_is_not_uploaded(cfg):
    (cfg["inbox"] / "photo.jpg").write_bytes(JPEG)
    client = FakeImmich()
    invoke(cfg, client, 1000)
    real_fingerprint = app.fingerprint
    calls = 0

    def changed(st):
        nonlocal calls
        calls += 1
        return real_fingerprint(st) if calls == 1 else "changed-during-snapshot"

    with patch.object(app, "fingerprint", side_effect=changed):
        assert invoke(cfg, client, 1060) == 0
    assert not client.uploads


def test_changed_file_restarts_settle_and_imports_new_content(cfg):
    photo = cfg["inbox"] / "same-name.jpg"
    photo.write_bytes(JPEG)
    client = FakeImmich()
    invoke(cfg, client, 1000)
    photo.write_bytes(b"\xff\xd8replacement\xff\xd9")
    invoke(cfg, client, 1060)
    assert not client.uploads
    invoke(cfg, client, 1120)
    assert client.uploads == [photo.read_bytes()]
    photo.write_bytes(JPEG)
    invoke(cfg, client, 1200)
    invoke(cfg, client, 1260)
    assert client.uploads[-1] == JPEG


@pytest.mark.parametrize("data", [b"", b"x", b"\xff\xd8unfinished", b"not jpeg\xff\xd9"])
def test_incomplete_jpeg_never_uploads(cfg, data):
    photo = cfg["inbox"] / "photo.jpg"
    photo.write_bytes(data)
    client = FakeImmich()
    invoke(cfg, client, 1000)
    assert invoke(cfg, client, 1060) == 1
    assert not client.uploads
    assert photo.read_bytes() == data


def test_oversize_file_retained(cfg):
    photo = cfg["inbox"] / "large.jpg"
    photo.write_bytes(b"\xff\xd8" + b"x" * 1024 * 1024 + b"\xff\xd9")
    client = FakeImmich()
    invoke(cfg, client, 1000)
    assert invoke(cfg, client, 1060) == 1
    assert not client.uploads


def test_dry_run_does_not_upload_create_album_or_mark_done(cfg, capsys):
    (cfg["inbox"] / "photo.jpg").write_bytes(JPEG)
    client = FakeImmich()
    invoke(cfg, client, 1000, dry=True)
    invoke(cfg, client, 1060, dry=True)
    assert "would_upload=1" in capsys.readouterr().out
    assert not client.uploads and not client.adds
    invoke(cfg, client, 1120)
    assert client.uploads == [JPEG]


def test_hidden_raw_and_symlink_directories_are_not_imported(cfg, tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    (external / "private.jpg").write_bytes(JPEG)
    (cfg["inbox"] / "linked").symlink_to(external, target_is_directory=True)
    (cfg["inbox"] / "RAW.ARW").write_bytes(JPEG)
    (cfg["inbox"] / ".private.jpg").write_bytes(JPEG)
    for directory in ("@eaDir", "#recycle", ".hidden"):
        (cfg["inbox"] / directory).mkdir()
        (cfg["inbox"] / directory / "photo.jpg").write_bytes(JPEG)
    assert list(app.candidates(cfg["inbox"])) == []


def test_symlink_file_refused_without_reading_target(cfg, tmp_path):
    external = tmp_path / "private.jpg"
    external.write_bytes(JPEG)
    (cfg["inbox"] / "linked.jpg").symlink_to(external)
    client = FakeImmich()
    assert invoke(cfg, client, 1000) == 1
    assert not client.uploads


def test_fifo_is_skipped_without_blocking(cfg):
    os.mkfifo(cfg["inbox"] / "pipe.jpg")
    assert invoke(cfg, FakeImmich(), 1000) == 0


def test_lock_prevents_second_runner(cfg):
    with app.state_db(cfg, SYNTHETIC_KEY):
        with pytest.raises(app.ImportErrorSafe, match="Another importer"):
            with app.state_db(cfg, SYNTHETIC_KEY):
                pytest.fail("lock was bypassed")


def test_state_bound_to_destination_and_key(cfg):
    with app.state_db(cfg, SYNTHETIC_KEY):
        pass
    for changed in (
        {**cfg, "album": "Another"},
        {**cfg, "immich_url": "https://example.invalid/api"},
    ):
        with pytest.raises(app.ImportErrorSafe, match="another configuration"):
            with app.state_db(changed, SYNTHETIC_KEY):
                pass
    with pytest.raises(app.ImportErrorSafe, match="another configuration"):
        with app.state_db(cfg, "different-test-token"):
            pass


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o666])
def test_key_permissions_refused(cfg, mode):
    cfg["api_key_file"].chmod(mode)
    with pytest.raises(app.ImportErrorSafe, match="mode 600"):
        app.private_file(cfg["api_key_file"])


@pytest.mark.parametrize("key", ["", "one\ntwo", "one two", "a" * 4097])
def test_invalid_key_rejected(cfg, key):
    cfg["api_key_file"].write_text(key)
    with pytest.raises(app.ImportErrorSafe):
        app.private_file(cfg["api_key_file"])


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"results": []},
        {"results": [{"id": "wrong", "action": "accept"}]},
        {"results": [{"id": "candidate", "action": "reject", "reason": "unsupported-format"}]},
        {
            "results": [
                {"id": "candidate", "action": "reject", "reason": "duplicate", "assetId": ASSET}
            ]
        },
        {
            "results": [
                {
                    "id": "candidate",
                    "action": "reject",
                    "reason": "duplicate",
                    "assetId": ASSET,
                    "isTrashed": True,
                }
            ]
        },
    ],
)
def test_duplicate_check_fails_closed(cfg, reply):
    client = app.Immich(cfg, SYNTHETIC_KEY)
    with patch.object(client, "json", return_value=reply), pytest.raises(app.ImportErrorSafe):
        client.check("0" * 40)


@pytest.mark.parametrize(
    "row,okay",
    [
        ({"id": ASSET, "success": True}, True),
        ({"id": ASSET, "success": False, "error": "duplicate"}, True),
        ({"id": ASSET, "success": False, "error": "no_permission"}, False),
        ({"id": ALBUM, "success": True}, False),
        ({"id": ASSET, "success": "true"}, False),
    ],
)
def test_album_result_checked(cfg, row, okay):
    client = app.Immich({**cfg, "album_id": ALBUM}, SYNTHETIC_KEY)
    with patch.object(client, "json", return_value=[row]):
        if okay:
            client.add_to_album(ASSET)
        else:
            with pytest.raises(app.ImportErrorSafe):
                client.add_to_album(ASSET)


@pytest.mark.parametrize(
    "albums",
    [
        [{"albumName": "Test camera", "id": ALBUM, "shared": True}],
        [{"albumName": "Test camera", "id": ALBUM, "shared": False}] * 2,
    ],
)
def test_shared_or_ambiguous_album_requires_explicit_id(cfg, albums):
    client = app.Immich(cfg, SYNTHETIC_KEY)
    with patch.object(client, "json", return_value=albums), pytest.raises(app.ImportErrorSafe):
        client.ensure_album()


def write_config(cfg, tmp_path, **updates):
    values = {**cfg, **updates}
    text = "\n".join(
        f"{k} = {json.dumps(str(v) if isinstance(v, Path) else v)}" for k, v in values.items()
    )
    path = tmp_path / "settings.toml"
    path.write_text(text)
    return path


def test_config_defaults_and_api_normalization(cfg, tmp_path):
    path = write_config(cfg, tmp_path, immich_url="https://immich.example.invalid/")
    assert app.load_config(path)["immich_url"] == "https://immich.example.invalid/api"


@pytest.mark.parametrize(
    "updates",
    [
        {"immich_url": "http://example.invalid"},
        {"immich_url": "https://user:password@example.invalid"},
        {"immich_url": "https://example.invalid?token=private"},
        {"immich_url": "file:///etc/passwd"},
        {"immich_url": "https://example.invalid/custom/path"},
        {"settle_seconds": 0},
        {"settle_seconds": True},
        {"state_dir": "relative"},
        {"allow_insecure_http": "false"},
        {"unknown": "value"},
    ],
)
def test_invalid_config_rejected(cfg, tmp_path, updates):
    with pytest.raises(app.ImportErrorSafe):
        app.load_config(write_config(cfg, tmp_path, **updates))


def test_state_or_key_inside_inbox_rejected(cfg, tmp_path):
    for field in ("state_dir", "api_key_file"):
        with pytest.raises(app.ImportErrorSafe, match="outside"):
            app.load_config(write_config(cfg, tmp_path, **{field: cfg["inbox"] / "private"}))


def test_cli_does_not_echo_invalid_arguments_or_config(cfg, tmp_path, capsys):
    with pytest.raises(SystemExit):
        app.main(["--api-key", SYNTHETIC_KEY])
    assert SYNTHETIC_KEY not in capsys.readouterr().err
    path = write_config(cfg, tmp_path)
    path.write_text("broken = " + SYNTHETIC_KEY)
    assert app.main(["--config", str(path)]) == 1
    assert SYNTHETIC_KEY not in capsys.readouterr().err


@contextlib.contextmanager
def mock_server():
    state = {"requests": [], "assets": {}, "album": False, "members": set(), "mode": "normal"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state["requests"].append((self.command, self.path, self.headers, body))
            if state["mode"] == "redirect":
                self.send_response(302)
                self.send_header("Location", "/stolen")
                self.end_headers()
                return
            if state["mode"] == "error":
                self.send_response(403)
                self.end_headers()
                self.wfile.write(SYNTHETIC_KEY.encode())
                return
            status = 200
            if self.path.endswith("bulk-upload-check"):
                digest = json.loads(body)["assets"][0]["checksum"]
                result = {"id": "candidate", "action": "accept"}
                if digest in state["assets"]:
                    result.update(
                        action="reject", reason="duplicate", assetId=ASSET, isTrashed=False
                    )
                response = {"results": [result]}
            elif self.path == "/api/assets":
                raw = b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body
                parts = list(BytesParser(policy=policy.default).parsebytes(raw).iter_parts())
                assert [p.get_param("name", header="content-disposition") for p in parts] == [
                    "fileCreatedAt",
                    "fileModifiedAt",
                    "assetData",
                ]
                photo = parts[-1].get_payload(decode=True)
                state["assets"][hashlib.sha1(photo, usedforsecurity=False).hexdigest()] = photo
                response = {"id": ASSET, "status": "created"}
                status = 201
            elif self.path == "/api/albums":
                album = {"id": ALBUM, "albumName": "Test camera", "shared": False}
                if self.command == "POST":
                    state["album"] = True
                    response = album
                else:
                    response = [album] if state["album"] else []
            else:
                asset = json.loads(body)["ids"][0]
                response = [{"id": asset, "success": asset not in state["members"]}]
                if asset in state["members"]:
                    response[0]["error"] = "duplicate"
                state["members"].add(asset)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        do_GET = handle_request
        do_POST = handle_request
        do_PUT = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_http_upload_album_duplicate_and_filename_injection(cfg):
    name = 'image"\r\nX-Injected: yes\\.jpg'
    photo = cfg["inbox"] / name
    photo.write_bytes(JPEG)
    with mock_server() as (url, state):
        cfg["immich_url"] = url
        with patch.object(app.time, "time", return_value=1000):
            assert app.run(cfg) == 0
        with patch.object(app.time, "time", return_value=1060):
            assert app.run(cfg) == 0
        assert list(state["assets"].values()) == [JPEG]
        assert state["members"] == {ASSET}
        upload = next(r for r in state["requests"] if r[1] == "/api/assets")
        assert b"\r\nX-Injected:" not in upload[3]
        assert all(r[2]["x-api-key"] == SYNTHETIC_KEY for r in state["requests"])
        (cfg["inbox"] / "copy.jpg").write_bytes(JPEG)
        with patch.object(app.time, "time", return_value=1200):
            app.run(cfg)
        with patch.object(app.time, "time", return_value=1260):
            app.run(cfg)
        assert len([r for r in state["requests"] if r[1] == "/api/assets"]) == 1
        assert photo.read_bytes() == JPEG


@pytest.mark.parametrize("mode", ["redirect", "error"])
def test_http_errors_hide_body_and_redirects_never_forward_key(cfg, mode):
    with mock_server() as (url, state):
        state["mode"] = mode
        client = app.Immich({**cfg, "immich_url": url}, SYNTHETIC_KEY)
        with pytest.raises(app.ImportErrorSafe) as caught:
            client.check("0" * 40)
        assert SYNTHETIC_KEY not in str(caught.value)
        assert len(state["requests"]) == 1


def test_cli_smoke_uses_no_network_for_empty_inbox(cfg, tmp_path, capsys):
    path = write_config(cfg, tmp_path)
    with patch.object(app.Immich, "request", side_effect=AssertionError("network")):
        assert app.main(["--config", str(path), "--dry-run"]) == 0
    assert "failed=0" in capsys.readouterr().out
