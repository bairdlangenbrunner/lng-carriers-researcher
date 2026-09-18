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


# ---- write-back (milestone 3) ------------------------------------------------------

def post(base, body, ctype="application/json"):
    req = urllib.request.Request(base + "/api/decide", data=json.dumps(body).encode(),
                                 headers={"Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def rows(path):
    import csv
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def snapshot(bdirs):
    return {p: p.read_bytes() for d in bdirs for p in sorted(d.iterdir()) if p.is_file()}


def test_decide_changes_only_the_decision_cells(running):
    base, _, b = running
    path = b["fix_a"] / "decisions.csv"
    before_bytes, before = path.read_bytes(), rows(path)
    status, body = post(base, [{"key": f"{b['fix_a'].name}::10|Price", "decision": "accept"}])
    assert status == 200 and body["saved"][0]["reviewer"] == "tester" and body["saved"][0]["ts"]
    after = rows(path)
    assert [r["id"] for r in after] == [r["id"] for r in before]
    for r0, r1 in zip(before, after):
        for col in r0:
            if not (col == "decision" and r0["id"] == "10|Price"):
                assert r0[col] == r1[col], (r0["id"], col)
    assert next(r for r in after if r["id"] == "10|Price")["decision"] == "accept"
    # byte-level: only the one line differs, and it differs only in the decision field
    old_lines, new_lines = before_bytes.split(b"\r\n"), path.read_bytes().split(b"\r\n")
    diff = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
    assert len(old_lines) == len(new_lines) and len(diff) == 1
    assert diff[0][0].replace(b",hold,hold,", b",hold,accept,") == diff[0][1]


def test_following_apply_batch_keeps_decisions_and_patches(running, tmp_path):
    base, _, b = running
    from review_fixture import _run_apply
    key = f"{b['fix_b'].name}::10|Other names"
    assert post(base, [{"key": key, "decision": "accept"}])[0] == 200
    _run_apply(b["fix_b"], tmp_path / "backend.csv")
    dec = {r["id"]: r["decision"] for r in rows(b["fix_b"] / "decisions.csv")}
    assert dec["10|Other names"] == "accept" and dec["10|Status"] == "hold"
    patch = rows(b["fix_b"] / "apply_patch.csv")
    assert [(p["column"], p["value"]) for p in patch if p["column"] == "Other names"] == \
        [("Other names", json.loads((b["fix_b"] / "fix.json").read_text())["corrections"][0]["cells"][0]["new_value"])]
    assert not any(p["column"] == "Status" for p in patch)


def test_suggest_is_reject_in_csv_and_full_in_log(running):
    base, _, b = running
    key = f"{b['fix_a'].name}::10|Name"
    rec = {"key": key, "decision": "suggest", "suggested_value": "Atlantic Star II",
           "suggest_kind": "cosmetic", "note": "spelling per class register", "via": "single"}
    assert post(base, [rec])[0] == 200
    assert next(r for r in rows(b["fix_a"] / "decisions.csv") if r["id"] == "10|Name")["decision"] == "reject"
    log = [json.loads(x) for x in (b["fix_a"] / "review_log.jsonl").read_text().splitlines()]
    assert log[-1]["decision"] == "suggest" and log[-1]["suggested_value"] == "Atlantic Star II"
    assert log[-1]["suggest_kind"] == "cosmetic" and log[-1]["reviewer"] == "tester"
    data = json.loads(get(base + "/api/data")[1])
    p = data["proposals"][key]
    assert p["decision"] == "suggest" and p["suggestion"]["value"] == "Atlantic Star II"


def test_undo_appends(running):
    base, _, b = running
    key = f"{b['fix_a'].name}::10|Status"
    post(base, [{"key": key, "decision": "reject"}])
    post(base, [{"key": key, "decision": "accept", "via": "undo"}])
    log = [json.loads(x) for x in (b["fix_a"] / "review_log.jsonl").read_text().splitlines()]
    assert [r["decision"] for r in log] == ["reject", "accept"] and log[1]["via"] == "undo"
    assert next(r for r in rows(b["fix_a"] / "decisions.csv") if r["id"] == "10|Status")["decision"] == "accept"


@pytest.mark.parametrize("body", [
    [{"key": "nope::1|Name", "decision": "accept"}],
    [{"key": "__A__::10|Name", "decision": "maybe"}],
    [{"key": "__A__::10|Name", "decision": "accept"}, {"key": "__A__::10|Status", "decision": "yes"}],
    [{"key": "__A__::10|Name", "decision": "suggest", "suggested_value": "X", "note": ""}],
    [{"key": "__A__::10|Name", "decision": "suggest", "suggested_value": "X", "note": "n",
      "suggest_kind": "other"}],
    [],
    {"key": "__A__::10|Name", "decision": "accept"},
])
def test_bad_request_is_400_and_writes_nothing(running, body):
    base, _, b = running
    body = json.loads(json.dumps(body).replace("__A__", b["fix_a"].name))
    before = snapshot(b.values())
    status, resp = post(base, body)
    assert status == 400 and resp["error"]
    assert snapshot(b.values()) == before


def test_wrong_content_type_refused(running):
    base, _, b = running
    before = snapshot(b.values())
    status, _ = post(base, [{"key": f"{b['fix_a'].name}::10|Name", "decision": "hold"}], "text/plain")
    assert status == 415 and snapshot(b.values()) == before


def test_failed_write_leaves_files_intact(running, monkeypatch):
    base, _, b = running
    import store

    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(store.os, "replace", boom)
    before = snapshot(b.values())
    status, resp = post(base, [{"key": f"{b['fix_a'].name}::10|Status", "decision": "reject"}])
    assert status == 500 and "disk full" in resp["error"]
    assert snapshot(b.values()) == before            # csv untouched, log append rolled back


def test_crlf_and_multiline_fields_survive(tmp_path):
    import store
    p = tmp_path / "decisions.csv"
    text = ('id,kind,decision,note\r\n1|A,fill,hold,"two\r\nlines"\r\n2|B,fill,hold,x y\r\n'
            '3|C,fill,hold,"quoted, comma"\r\n')
    p.write_bytes(text.encode())
    out = store.plan_csv(p, {"2|B": "accept", "1|A": "hold"})
    assert out == text.replace("2|B,fill,hold,", "2|B,fill,accept,")


# ---- items + bulk (milestone 4) ----------------------------------------------------

def post_item(base, body):
    req = urllib.request.Request(base + "/api/item", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def conflict_item(base):
    data = json.loads(get(base + "/api/data")[1])
    return next(it for it in data["items"] if it["type"] == "conflict")


def test_item_status_logged_and_conflict_call_written(running):
    base, _, b = running
    it = conflict_item(base)
    assert it["status"] == "open" and it["conflict_decision"] == "hold"
    path = b["data_fill"] / "conflicts.csv"
    before = path.read_bytes()
    status, body = post_item(base, [{"item_id": it["item_id"], "status": "resolved",
                                     "note": "backend right", "conflict_decision": "reject"}])
    assert status == 200 and body["saved"][0]["reviewer"] == "tester"
    after = path.read_bytes()
    # only the decision cell of that record changed
    assert after == before.replace(b",hold", b",reject", 1) and after.count(b",reject") == 1
    log = [json.loads(x) for x in (b["data_fill"] / "review_items.jsonl").read_text().splitlines()]
    assert log[-1]["status"] == "resolved" and log[-1]["conflict_decision"] == "reject"
    it2 = conflict_item(base)
    assert it2["status"] == "resolved" and it2["conflict_decision"] == "reject"
    assert it2["last"]["note"] == "backend right"
    # decisions.csv is not touched by an item call
    assert not (b["data_fill"] / "review_log.jsonl").exists()


def test_item_status_without_call_leaves_conflicts_csv(running):
    base, _, b = running
    it = conflict_item(base)
    before = (b["data_fill"] / "conflicts.csv").read_bytes()
    assert post_item(base, [{"item_id": it["item_id"], "status": "needs research"}])[0] == 200
    assert (b["data_fill"] / "conflicts.csv").read_bytes() == before


@pytest.mark.parametrize("body", [
    [{"item_id": "nope::conflict:0", "status": "open"}],
    [{"item_id": "__C__", "status": "done"}],
    [{"item_id": "__C__", "status": "open", "conflict_decision": "maybe"}],
    [],
])
def test_bad_item_request_is_400_and_writes_nothing(running, body):
    base, _, b = running
    body = json.loads(json.dumps(body).replace("__C__", conflict_item(base)["item_id"]))
    before = snapshot(b.values())
    status, resp = post_item(base, body)
    assert status == 400 and resp["error"]
    assert snapshot(b.values()) == before


def test_regenerated_conflicts_csv_is_refused(running):
    base, _, b = running
    it = conflict_item(base)
    path = b["data_fill"] / "conflicts.csv"
    text = path.read_text(encoding="utf-8").replace(it["conflict_match"][1], "Something else", 1)
    path.write_text(text, encoding="utf-8")
    before = snapshot(b.values())
    status, resp = post_item(base, [{"item_id": it["item_id"], "status": "resolved",
                                     "conflict_decision": "accept"}])
    assert status == 400 and "no longer" in resp["error"]
    assert snapshot(b.values()) == before


def test_bulk_records_across_batches(running):
    base, _, b = running
    keys = [f"{b['fix_a'].name}::10|Price", f"{b['fix_a'].name}::10|Status", f"{b['fix_b'].name}::10|Status"]
    recs = [{"key": k, "decision": "reject", "via": "bulk:decision hold · Status"} for k in keys]
    status, body = post(base, recs)
    assert status == 200 and len(body["saved"]) == 3
    assert len({r["ts"] for r in body["saved"]}) == 1
    for d in (b["fix_a"], b["fix_b"]):
        log = [json.loads(x) for x in (d / "review_log.jsonl").read_text().splitlines()]
        assert all(r["via"].startswith("bulk:") for r in log)
    data = json.loads(get(base + "/api/data")[1])
    assert all(data["proposals"][k]["decision"] == "reject" for k in keys)


def test_conflict_call_reset_by_apply_batch_is_shown(running, tmp_path):
    base, _, b = running
    from review_fixture import _run_apply
    it = conflict_item(base)
    post_item(base, [{"item_id": it["item_id"], "status": "resolved", "conflict_decision": "accept"}])
    _run_apply(b["data_fill"], tmp_path / "backend.csv")       # regenerates conflicts.csv at hold
    it2 = conflict_item(base)
    assert it2["conflict_decision"] == "hold" and it2["logged_call"] == "accept"
