"""review_app/server.py + store.py: loopback-only server, data overlay, write-back."""
import json
import threading
import urllib.error
import urllib.request

import pytest

import review_data
import server
from review_fixture import make_batches


@pytest.fixture
def running(tmp_path):
    backend, b = make_batches(tmp_path)
    data_path = tmp_path / "review_data.json"
    review_data.write(review_data.build(list(b.values()), backend), data_path)
    app = server.App(data_path, "tester", batches_root=tmp_path / "batches")
    httpd = server.make_server(app, "127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, app, b
    httpd.shutdown()
    httpd.server_close()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as r:
        return r.status, r.read()


def test_refuses_non_loopback():
    for host in ("0.0.0.0", "192.168.1.5", "example.com", "::"):
        with pytest.raises(ValueError):
            server.ensure_loopback(host)
    for host in ("127.0.0.1", "localhost", "::1"):
        server.ensure_loopback(host)
    with pytest.raises(SystemExit):
        server.main(["--host", "0.0.0.0", "--no-open"])


def test_serves_static_and_api(running):
    base, app, b = running
    status, body = get(base + "/")
    assert status == 200 and b"<script src=\"app.js\">" in body
    assert json.loads(get(base + "/api/whoami")[1]) == {"reviewer": "tester"}
    data = json.loads(get(base + "/api/data")[1])
    k = f"{b['fix_a'].name}::10|Name"
    assert data["proposals"][k]["decision"] == "accept" and data["proposals"][k]["last"] is None


def test_static_does_not_escape_web_dir(running):
    base, _, _ = running
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/../server.py")
    assert e.value.code == 404


def test_rejects_foreign_host_header(running):
    base, _, _ = running
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/api/data", {"Host": "evil.example:8765"})
    assert e.value.code == 403
