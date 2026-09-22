"""review_app/living.py: what `processed` means, the write plan, and the review app's sync.

No network anywhere — `Living` takes its reader and writer injected, so every test here
reads a fake tab and collects the ranges that would be written. Nothing in this file touches
the live sheet, the living workbook or the backend.
"""
import json
import re
import threading
import urllib.request

import pytest

import living
import review_data
import server
import store
from review_fixture import make_batches
from test_review_app import edit_backend

PROPS, SHAPE = living.PROPOSALS_SHEET, living.SHAPE_SHEET
INC, REJ = living.INCORPORATED, living.REJECTED


# ---- what a line's `processed` value is ----------------------------------------------

@pytest.mark.parametrize("proposal,expected", [
    ({"flags": ["in_backend"], "decision": "hold"}, INC),          # the backend holds it: settled
    ({"flags": ["in_backend"], "decision": "reject"}, INC),        # rejected but written anyway
    ({"flags": [], "decision": "reject"}, REJ),
    ({"flags": ["value_in_backend"], "decision": "accept"}, ""),   # value landed, ref did not
    ({"flags": [], "decision": "accept"}, ""),                     # accepted, not written yet
    ({"flags": [], "decision": "hold"}, ""),
    ({"flags": [], "decision": ""}, ""),
    ({"flags": [], "decision": "suggest", "current": "Atlantic Star",
      "suggestion": {"value": " Atlantic  Star "}}, INC),          # the reviewer's own value landed
    ({"flags": [], "decision": "suggest", "current": "Hull 1 (SHI)",
      "suggestion": {"value": "Atlantic Star"}}, ""),
    ({"flags": [], "decision": "suggest", "current": "x", "suggestion": {}}, ""),
])
def test_line_state(proposal, expected):
    assert living.line_state(proposal) == expected


@pytest.mark.parametrize("states,expected", [
    ([INC, INC], INC),
    ([REJ, REJ], REJ),
    ([INC, REJ], INC),                      # something of this vessel was incorporated
    ([INC, ""], "partly processed - 1 of 2"),
    (["", ""], ""),
    ([], ""),
])
def test_row_state(states, expected):
    assert living.row_state(states) == expected


def test_row_key_falls_back_to_the_cluster_of_a_row_not_in_the_backend():
    assert living.row_key({"row_id": "10", "batch": "b1", "cluster_id": "C1"}) == "row:10"
    assert living.row_key({"row_id": "", "batch": "b1", "cluster_id": "C1"}) == "cluster:b1:C1"


# ---- the states of a real dataset -----------------------------------------------------

@pytest.fixture
def dataset(tmp_path):
    """-> (dataset, {batch dir name: dir}) — keyed the way the server keys them."""
    backend, b = make_batches(tmp_path)
    data = review_data.build(list(b.values()), backend)
    return data, {d.name: d for d in b.values()}


def test_states_key_every_line_and_every_vessel(dataset):
    data, b = dataset
    want = living.states(data, b)
    assert set(want) == {PROPS, SHAPE}
    assert set(want[PROPS]) == set(data["proposals"])
    for key, p in data["proposals"].items():
        assert living.row_key(p) in want[SHAPE]
    assert set(want[PROPS].values()) <= {"", INC, REJ}
    # nothing is decided in a fresh fixture, so no vessel is finished
    assert all(v == "" or v.startswith("partly") for v in want[SHAPE].values())


def test_a_reject_reaches_both_tabs(dataset):
    data, b = dataset
    key = "b1_fix::10|Name"
    store.decide([{"key": key, "decision": "reject"}], data, b, "tester")
    want = living.states(data, b)
    assert want[PROPS][key] == REJ
    assert want[SHAPE]["row:10"].startswith("partly processed - ")


# ---- the write plan -------------------------------------------------------------------

def rows(pairs, first=2):
    return [(first + n, k, cur) for n, (k, cur) in enumerate(pairs)]


def test_plan_writes_only_changed_cells_in_contiguous_runs():
    r = rows([("a", ""), ("b", ""), ("c", INC), ("d", "")])
    got = living.plan(PROPS, 20, r, {"a": INC, "b": INC, "c": INC, "d": REJ})
    assert got == [("'all_proposals'!U2:U3", [[INC], [INC]]),
                   ("'all_proposals'!U5:U5", [[REJ]])]       # c is already right: skipped, runs split


def test_plan_leaves_a_key_it_does_not_know_and_writes_nothing_when_settled():
    r = rows([("a", INC), ("mystery", "hand typed"), ("b", REJ)])
    assert living.plan(PROPS, 3, r, {"a": INC, "b": REJ}) == []


def test_plan_clears_a_value_that_is_no_longer_true():
    r = rows([("a", INC)])
    assert living.plan(PROPS, 0, r, {"a": ""}) == [("'all_proposals'!A2:A2", [[""]])]


def test_plan_never_leaves_its_own_column():
    r = rows([("a", ""), ("b", "")])
    for a1, _vals in living.plan(PROPS, 7, r, {"a": INC, "b": REJ}):
        assert re.fullmatch(r"H\d+:H\d+", a1.split("!")[1])


def test_col_letter():
    assert [living.col_letter(i) for i in (0, 25, 26, 27, 51, 52)] == ["A", "Z", "AA", "AB", "AZ", "BA"]


# ---- the sync -------------------------------------------------------------------------

class FakeSheet:
    """Two tabs of (key, processed) pairs; collects what the sync writes."""

    def __init__(self, tabs):
        self.tabs, self.sent = tabs, []

    def read(self, title, key_column):
        return 1, 5, rows(self.tabs[title])

    def write(self, ranges):
        self.sent.append(ranges)
        return sum(len(v) for _a, v in ranges)


def make_living(sheet, batches, **cfg):
    config = {"spreadsheet_id": "SID", "url": "https://sheet", "name": "living",
              "batches": list(batches), **cfg}
    return living.Living(config, read=sheet.read, write=sheet.write)


def test_sync_writes_each_tab_and_reports(dataset):
    data, b = dataset
    key = "b1_fix::10|Name"
    store.decide([{"key": key, "decision": "reject"}], data, b, "tester")
    want = living.states(data, b)
    sheet = FakeSheet({PROPS: [(k, "") for k in list(want[PROPS])[:3]] + [("gone", INC)],
                       SHAPE: [(k, "") for k in want[SHAPE]]})
    out = make_living(sheet, b).sync(data, b)
    assert out["spreadsheet_id"] == "SID" and out["url"] == "https://sheet"
    assert out["tabs"][PROPS]["rows"] == 4 and out["tabs"][PROPS]["unknown"] == 1
    assert out["written"] == sum(t["changed"] for t in out["tabs"].values()) > 0
    written = {v for rs in sheet.sent for _a, vals in rs for row in vals for v in row}
    assert written == {REJ} or REJ in written          # the reject, and nothing for `gone`
    assert all(a1.startswith(("'" + PROPS, "'" + SHAPE)) for rs in sheet.sent for a1, _v in rs)


def test_sync_writes_nothing_when_the_sheet_already_agrees(dataset):
    data, b = dataset
    want = living.states(data, b)
    sheet = FakeSheet({PROPS: list(want[PROPS].items()), SHAPE: list(want[SHAPE].items())})
    out = make_living(sheet, b).sync(data, b)
    assert out["written"] == 0 and sheet.sent == []


def test_dry_run_plans_but_does_not_write(dataset):
    data, b = dataset
    want = living.states(data, b)
    sheet = FakeSheet({PROPS: [(k, "zzz") for k in want[PROPS]], SHAPE: []})
    out = make_living(sheet, b).sync(data, b, dry_run=True)
    assert out["dry_run"] and out["written"] > 0 and sheet.sent == []


def test_read_tab_finds_the_header_below_the_top_row(monkeypatch):
    calls = []

    def fake_gws(args, env, timeout=300):
        calls.append(args)
        if args[3] == "get":                       # the header scan
            return {"values": [["a title"], [], [living.LINE_ID, "x", living.PROCESSED]]}
        return {"valueRanges": [{"values": [["k1"], ["k2"]]}, {"values": [[INC]]}]}
    monkeypatch.setattr(living, "_gws", fake_gws)
    hrow, i_proc, rows_ = living.read_tab("SID", PROPS, living.LINE_ID)
    assert (hrow, i_proc) == (3, 2)
    assert rows_ == [(4, "k1", INC), (5, "k2", "")]        # a short processed column is padded
    assert "'all_proposals'!A4:A" in json.dumps(calls[1])  # only the key and processed columns


def test_a_tab_with_no_processed_header_is_a_living_error(monkeypatch):
    monkeypatch.setattr(living, "_gws", lambda *a, **k: {"values": [[living.LINE_ID, "note"]]})
    with pytest.raises(living.LivingError, match="rebuild the living workbook"):
        living.read_tab("SID", PROPS, living.LINE_ID)


def test_matches_only_the_reconciliation_it_was_built_from(dataset):
    _data, b = dataset
    sheet = FakeSheet({PROPS: [], SHAPE: []})
    assert make_living(sheet, b).matches(b)
    assert not make_living(sheet, ["some_other_batch"]).matches(b)
    assert not make_living(sheet, []).matches(b)


def test_from_config_is_off_without_a_config_or_with_the_kill_switch(tmp_path, monkeypatch):
    monkeypatch.delenv("LNGCT_LIVING_SYNC", raising=False)
    assert living.from_config(path=tmp_path / "nope.json") is None
    cfg = tmp_path / "living.json"
    cfg.write_text(json.dumps({"spreadsheet_id": "SID", "batches": ["b1_fix"]}))
    assert living.from_config(dirs={"b1_fix": tmp_path}, path=cfg) is not None
    assert living.from_config(dirs={"other": tmp_path}, path=cfg) is None
    monkeypatch.setenv("LNGCT_LIVING_SYNC", "0")
    assert living.from_config(dirs={"b1_fix": tmp_path}, path=cfg) is None


# ---- the review app's side --------------------------------------------------------------

def post_json(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())


@pytest.fixture
def app_with(tmp_path):
    """-> a factory: the running app with this living workbook attached."""
    backend, b = make_batches(tmp_path)
    data_path = tmp_path / "review_data.json"
    review_data.write(review_data.build(list(b.values()), backend), data_path)
    dirs = {d.name: d for d in b.values()}
    served = []

    def start(living_wb):
        app = server.App(data_path, "tester", batches_root=tmp_path / "batches",
                         living_wb=living_wb)
        app.backend_path = backend
        app.pull = lambda: None
        httpd = server.make_server(app, "127.0.0.1", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        served.append(httpd)
        return f"http://127.0.0.1:{httpd.server_address[1]}", app, dirs, backend
    yield start
    for httpd in served:
        httpd.shutdown()
        httpd.server_close()


def test_the_real_config_never_syncs_a_session_over_other_batches(app_with):
    """The fixture's batch dirs are not the reconciliation's, so the configured workbook
    (data/living_workbook.json, if present) must stay out of the tests."""
    _base, app, _dirs, _backend = app_with(None)
    assert app.living is None


def test_refresh_syncs_and_reports_it(app_with):
    base, app, b, _backend = app_with(False)
    sheet = FakeSheet({PROPS: [(k, "") for k in app.data["proposals"]], SHAPE: []})
    app.living = make_living(sheet, b)
    status, out = post_json(base, "/api/refresh", {})
    assert status == 200
    assert out["living"]["url"] == "https://sheet" and "error" not in out["living"]
    assert out["living"]["written"] == out["living"]["tabs"][PROPS]["changed"]


def test_push_syncs_after_the_backend_write(app_with):
    """A pushed cell is in the backend, so its line turns `processed - incorporated` in the
    living workbook without anyone touching it."""
    base, app, b, backend = app_with(False)
    sheet = FakeSheet({PROPS: [(k, "") for k in app.data["proposals"]], SHAPE: []})
    app.living = make_living(sheet, b)
    app.write = lambda writes: [edit_backend(backend, w["row_id"], **{w["column"]: w["new"]})
                                for w in writes]
    pre = [k for k, p in app.current()["proposals"].items() if p["decision"] == "accept"]
    post_json(base, "/api/decide", [{"key": k, "decision": "accept"} for k in pre])
    plan = post_json(base, "/api/push/plan", {})[1]
    out = post_json(base, "/api/push", {"token": plan["token"]})[1]
    landed = [k for k, p in app.current()["proposals"].items() if "in_backend" in p["flags"]]
    assert out["written"] == 7 and len(landed) == 4        # 7 sheet cells = 4 proposal lines
    assert out["living"]["written"] == len(landed)
    assert {v for rs in sheet.sent for _a, vals in rs for row in vals for v in row} == {INC}


def test_a_broken_living_workbook_never_fails_the_sync(app_with):
    base, app, b, _backend = app_with(False)

    class Broken(FakeSheet):
        def read(self, title, key_column):
            raise living.LivingError("'all_proposals' has no line id + processed header")
    app.living = make_living(Broken({}), b)
    status, out = post_json(base, "/api/refresh", {})
    assert status == 200                                   # the pull and the rebuild stand
    assert "no line id + processed header" in out["living"]["error"]
    assert out["living"]["written"] == 0 and "accepted" in out
