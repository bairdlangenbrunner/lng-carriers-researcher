"""review_app/server.py + store.py: loopback-only server, data overlay, write-back."""
import json
import threading
import urllib.error
import urllib.request

import pytest

import review_data
import server
import store
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
    assert data["proposals"][k]["reviewed"] is None       # pre-filled by the batch, nobody decided


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


def test_reviewed_is_the_researchers_call_not_the_prefill(running):
    base, _, b = running
    key = f"{b['fix_a'].name}::10|Status"
    prop = lambda: json.loads(get(base + "/api/data")[1])["proposals"][key]
    before = prop()["decision"]
    assert prop()["reviewed"] is None
    post(base, [{"key": key, "decision": "reject"}])
    assert prop()["reviewed"] == "reject"
    # undo back to a line nobody had decided: the csv gets its pre-fill back, reviewed is None again
    post(base, [{"key": key, "decision": before, "via": "undo", "undecided": True}])
    assert prop()["decision"] == before and prop()["reviewed"] is None
    post(base, [{"key": key, "decision": "hold"}])
    assert prop()["reviewed"] == "hold"
    # decisions.csv edited behind the log: the log no longer describes the line
    path = b["fix_a"] / "decisions.csv"
    text = store.plan_csv(path, {"10|Status": "accept"})
    path.write_text(text, encoding="utf-8", newline="")
    assert prop()["decision"] == "accept" and prop()["reviewed"] is None


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


# ---- backend sync (the refresh button) -----------------------------------------------

def edit_backend(path, row_id, **cells):
    import csv
    from review_fixture import HEADER
    with open(path, newline="", encoding="utf-8") as f:
        grid = list(csv.reader(f))
    for r in grid[2:]:
        if r[0] == row_id:
            for col, v in cells.items():
                r[HEADER.index(col.replace("_ref", " [ref]").replace("_", " "))] = v
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(grid)


def post_refresh(base):
    req = urllib.request.Request(base + "/api/refresh", data=b"{}",
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_refresh_accepts_holds_the_backend_already_holds(running, tmp_path):
    base, app, b = running
    backend = tmp_path / "backend.csv"
    app.backend_path = backend
    # by hand in the sheet: the batch-2 Status fix (a hold) incl. its ref, and the conflict's value
    app.pull = lambda: (edit_backend(backend, "10", Status="active", Status_ref="http://press/10"),
                        edit_backend(backend, "7", Capacity="174000"))
    held = f"{b['fix_b'].name}::10|Status"
    other = f"{b['fix_b'].name}::10|Other names"
    assert json.loads(get(base + "/api/data")[1])["proposals"][held]["decision"] == "hold"
    status, out = post_refresh(base)
    assert status == 200 and out["accepted"] == [held]
    assert out["resolved"] == [conflict_item(base)["item_id"]]
    data = json.loads(get(base + "/api/data")[1])
    p = data["proposals"][held]
    assert p["decision"] == "accept" and "in_backend" in p["flags"] and p["current"] == "active"
    assert p["last"]["reviewer"] == "backend sync" and p["last"]["via"] == "sync:backend"
    assert data["proposals"][other]["decision"] == "hold"          # not in the backend: untouched
    assert {r["id"]: r["decision"] for r in rows(b["fix_b"] / "decisions.csv")}["10|Status"] == "accept"
    assert conflict_item(base)["status"] == "resolved"
    assert post_refresh(base)[1]["accepted"] == []                 # idempotent


def test_refresh_leaves_a_decided_line_and_a_value_without_its_ref(running, tmp_path):
    base, app, b = running
    backend = tmp_path / "backend.csv"
    app.backend_path = backend
    held = f"{b['fix_b'].name}::10|Status"
    app.pull = lambda: edit_backend(backend, "10", Status="active")   # value only, old ref
    assert post_refresh(base)[1]["accepted"] == []
    p = json.loads(get(base + "/api/data")[1])["proposals"][held]
    assert p["decision"] == "hold" and "value_in_backend" in p["flags"]
    post(base, [{"key": held, "decision": "reject"}])
    app.pull = lambda: edit_backend(backend, "10", Status_ref="http://press/10")
    assert post_refresh(base)[1]["accepted"] == []                 # a human's reject stands
    assert json.loads(get(base + "/api/data")[1])["proposals"][held]["decision"] == "reject"


def test_failed_pull_changes_nothing(running):
    base, app, b = running
    before = snapshot(b.values())

    def boom():
        raise server.PullFailed("backend pull failed: gws not found")
    app.pull = boom
    status, out = post_refresh(base)
    assert status == 502 and "gws not found" in out["error"]
    assert snapshot(b.values()) == before


# ---- push accepted (the one backend write) -------------------------------------------

def post_json(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture
def pushing(running, tmp_path):
    """The running app with a no-op pull and a writer that edits the backend csv."""
    base, app, b = running
    backend = tmp_path / "backend.csv"
    app.backend_path = backend
    app.pull = lambda: None
    sent = []

    def write(writes):
        sent.append(writes)
        for w in writes:
            edit_backend(backend, w["row_id"], **{w["column"]: w["new"]})
    app.write = write
    # only a clicked accept is pushed: click every line apply_batch pre-filled as accept
    pre = [k for k, p in app.current()["proposals"].items() if p["decision"] == "accept"]
    assert post(base, [{"key": k, "decision": "accept"} for k in pre])[0] == 200
    return base, app, b, backend, sent


def cells(plan, group="writes"):
    return {(w["row_id"], w["column"]): w for w in plan[group]}


def test_push_plan_lists_accepted_cells_only(pushing):
    base, app, b, backend, sent = pushing
    status, plan = post_json(base, "/api/push/plan", {})
    assert status == 200 and sent == []
    c = cells(plan)
    assert set(c) == {("10", "Name"), ("10", "Name [ref]"), ("10", "Status"), ("10", "Status [ref]"),
                      ("5", "Capacity"), ("5", "Capacity [ref]"), ("5", "Capacity units")}
    w = c[("10", "Name")]
    assert (w["old"], w["new"], w["batch"]) == ("Hull 1 (SHI)", "Atlantic Star", b["fix_a"].name)
    assert w["a1"] == f"C{w['live_row']}" and w["live_row"] != 10
    assert c[("10", "Name [ref]")]["new"] == "http://ship/10"          # a fix replaces the ref
    assert plan["applied_writes"] == [] and plan["skipped"] == []       # holds are not skips


def test_push_writes_verifies_and_logs(pushing):
    base, app, b, backend, sent = pushing
    plan = post_json(base, "/api/push/plan", {})[1]
    status, out = post_json(base, "/api/push", {"token": plan["token"]})
    assert status == 200 and out["written"] == 7 and out["mismatches"] == [] and not out["error"]
    assert len(sent) == 1 and len(sent[0]) == 7
    log = [json.loads(l) for l in (b["fix_a"] / "push_log.jsonl").read_text().splitlines()]
    assert {(r["row_id"], r["column"]) for r in log} == {("10", "Name"), ("10", "Name [ref]"),
                                                          ("10", "Status"), ("10", "Status [ref]")}
    assert all(r["reviewer"] == "tester" for r in log)
    data = json.loads(get(base + "/api/data")[1])
    assert "in_backend" in data["proposals"][f"{b['fix_a'].name}::10|Name"]["flags"]
    again = post_json(base, "/api/push/plan", {})[1]
    assert again["writes"] == []
    assert post_json(base, "/api/push", {"token": plan["token"]})[0] == 409    # the old plan is gone
    assert len(sent) == 1


def test_push_refuses_a_stale_plan(pushing):
    base, app, b, backend, sent = pushing
    plan = post_json(base, "/api/push/plan", {})[1]
    app.pull = lambda: edit_backend(backend, "10", Name="Hand Edited")        # the sheet moved on
    status, out = post_json(base, "/api/push", {"token": plan["token"]})
    assert status == 409 and "nothing was written" in out["error"] and sent == []


def test_push_never_overwrites_a_filled_cell_from_a_fill_batch(pushing):
    base, app, b, backend, sent = pushing
    edit_backend(backend, "5", Capacity="180000")
    plan = post_json(base, "/api/push/plan", {})[1]
    assert ("5", "Capacity") not in cells(plan) and ("5", "Capacity [ref]") not in cells(plan)
    assert [s["why"] for s in plan["skipped"] if s["column"] == "Capacity"][0].startswith("cell is no longer blank")


def test_push_holds_back_lines_of_an_applied_batch(pushing):
    base, app, b, backend, sent = pushing
    (b["fix_a"] / "verify_report.csv").write_text("status\n")
    plan = post_json(base, "/api/push/plan", {})[1]
    assert {k[0] for k in cells(plan)} == {"5"}
    assert {k[0] for k in cells(plan, "applied_writes")} == {"10"}
    out = post_json(base, "/api/push", {"token": plan["token"]})[1]
    assert out["written"] == 3 and all(w["row_id"] == "5" for w in sent[0])
    plan = post_json(base, "/api/push/plan", {})[1]
    out = post_json(base, "/api/push", {"token": plan["token_all"], "include_applied": True})[1]
    assert out["written"] == 4


def test_failed_sheet_write_is_reported_not_logged(pushing):
    import push

    base, app, b, backend, sent = pushing

    def boom(writes):
        raise push.PushFailed("sheet write failed after 0 of 7 cells: 403")
    app.write = boom
    plan = post_json(base, "/api/push/plan", {})[1]
    status, out = post_json(base, "/api/push", {"token": plan["token"]})
    assert status == 200 and out["written"] == 0 and len(out["mismatches"]) == 7 and "403" in out["error"]
    assert not (b["fix_a"] / "push_log.jsonl").exists()


def test_sheet_value_types():
    import push

    assert push.sheet_value("250000000") == 250000000 and push.sheet_value("1.5") == 1.5
    assert push.sheet_value("0123") == "0123" and push.sheet_value("2027-03") == "2027-03"
    assert push.a1(0, 2) == "A2" and push.a1(26, 10) == "AA10"


def test_push_scoped_to_one_batch(pushing):
    base, app, b, backend, sent = pushing
    plan = post_json(base, "/api/push/plan", {"batch": b["data_fill"].name})[1]
    assert {k[0] for k in cells(plan)} == {"5"}
    out = post_json(base, "/api/push", {"token": plan["token"], "batch": b["data_fill"].name})[1]
    assert out["written"] == 3
    assert {k[0] for k in cells(post_json(base, "/api/push/plan", {})[1])} == {"10"}


def test_push_leaves_an_accept_nobody_clicked(running, tmp_path):
    base, app, b = running
    app.backend_path, app.pull = tmp_path / "backend.csv", lambda: None
    plan = post_json(base, "/api/push/plan", {})[1]
    assert plan["writes"] == [] and plan["unclicked"] > 0           # pre-filled accepts only
    n = plan["unclicked"]
    assert post(base, [{"key": f"{b['fix_a'].name}::10|Name", "decision": "accept"}])[0] == 200
    plan = post_json(base, "/api/push/plan", {})[1]
    assert set(cells(plan)) == {("10", "Name"), ("10", "Name [ref]")} and plan["unclicked"] == n - 1
    assert post(base, [{"key": f"{b['fix_a'].name}::10|Name", "decision": "hold"}])[0] == 200
    assert post_json(base, "/api/push/plan", {})[1]["writes"] == []
