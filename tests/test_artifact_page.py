"""review_app/build_static.py and import_log.py: the single-file page and the way its calls come back into the batch dirs.
Records here are shaped the way the page's store (review_core/web/static_store.js) writes them. Nothing reaches the sheet."""
import csv
import json

import pytest
import build_static
import core_store as store
import import_log
from review_core.build_static import read_blob
from review_fixture import make_batches

EMAIL = "tester.person@globalenergymonitor.org"   # initials TP


@pytest.fixture
def batches(tmp_path):
    backend, b = make_batches(tmp_path)
    return backend, b, tmp_path / "batches"


def ds_for(backend, b, root):
    return import_log.dataset(list(b.values()), backend, root=root)


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def page_line(ds, key, decision, rid="r1", ts="2026-10-29T12:00:00-04:00", **kw):
    card, obj, _ = store.index(ds)[key]
    rec = {"id": rid, "key": key, "dir": obj["dir"], "pid": card["pid"], "kind": obj["kind"], "decision": decision,
           "suggested_value": "", "note": "", "reviewer": "TP", "ts": ts, "undecided": False}
    rec.update(kw)
    return rec


def page_item(ds, key, call, rid="i1", ts="2026-10-29T12:00:00-04:00"):
    card, obj, _ = store.index(ds)[key]
    return {"id": rid, "key": key, "dir": obj["dir"], "pid": card["pid"], "kind": obj["kind"], "call": call,
            "note": "", "reviewer": "TP", "ts": ts, "undecided": False}


def run(docs, ds, dirs):
    pl = import_log.plan(docs, ds, dirs, emails={"TP": EMAIL})
    return pl, import_log.write(pl, ds, dirs)


def test_page_carries_the_dataset_and_no_local_paths(batches):
    backend, b, root = batches
    data = build_static.dataset(list(b.values()), backend)
    store.overlay(data, store.dir_paths(data, root))
    html = build_static.render(data, "TP")
    got = read_blob(html)["data"]
    assert [c["pid"] for c in got["vessels"]] == [c["pid"] for c in data["vessels"]]
    assert "LNG carriers reviewer" in html and str(root.parent) not in html


def test_line_decision_lands_in_decisions_csv_once(batches):
    backend, b, root = batches
    ds, dirs = ds_for(backend, b, root)
    key = f"{b['fix_a'].name}::10|Price"
    docs = [{"reviewer": "TP", "records": [page_line(ds, key, "reject")]}]
    pl, saved = run(docs, ds, dirs)
    assert len(saved) == 1 and saved[0]["origin"] == "artifact" and saved[0]["record_id"] == "10|Price"
    assert next(r for r in rows(b["fix_a"] / "decisions.csv") if r["id"] == "10|Price")["decision"] == "reject"
    ds, dirs = ds_for(backend, b, root)
    pl = import_log.plan(docs, ds, dirs, emails={"TP": EMAIL})
    assert pl["dup"] == 1 and not pl["new"]                    # a second import skips it by id


def test_conflict_call_lands_in_conflicts_csv_and_is_skipped_again(batches):
    backend, b, root = batches
    ds, dirs = ds_for(backend, b, root)
    key = next(k for k, (_, o, g) in store.index(ds).items() if g == "items" and o["kind"] == "conflict")
    docs = [{"reviewer": "TP", "records": [page_item(ds, key, "reject")]}]
    run(docs, ds, dirs)
    assert [r["decision"] for r in rows(b["data_fill"] / "conflicts.csv")].count("reject") == 1
    log = [json.loads(x) for x in (b["data_fill"] / "review_items.jsonl").read_text().splitlines()]
    assert log[-1]["item_id"] == key and log[-1]["conflict_decision"] == "reject" and log[-1]["id"] == "i1"
    ds, dirs = ds_for(backend, b, root)
    assert import_log.plan(docs, ds, dirs, emails={"TP": EMAIL})["dup"] == 1


def test_later_server_call_supersedes_the_page(batches):
    backend, b, root = batches
    ds, dirs = ds_for(backend, b, root)
    key = f"{b['fix_a'].name}::10|Price"
    store.decide([{"key": key, "decision": "accept"}], ds, "Server Person", dirs, sink=store.sink)
    ds, dirs = ds_for(backend, b, root)
    docs = [{"reviewer": "TP", "records": [page_line(ds, key, "reject", ts="2020-01-01T00:00:00-05:00")]}]
    pl = import_log.plan(docs, ds, dirs, emails={"TP": EMAIL})
    assert not pl["new"] and len(pl["stale"]) == 1


def test_unknown_key_or_wrong_call_stops_before_writing(batches):
    backend, b, root = batches
    ds, dirs = ds_for(backend, b, root)
    before = {p: p.read_bytes() for d in b.values() for p in d.iterdir() if p.is_file()}
    key = f"{b['fix_a'].name}::10|Price"
    bad = page_line(ds, key, "accept")
    bad["key"] = f"{b['fix_a'].name}::99|Price"
    with pytest.raises(SystemExit):
        import_log.plan([{"reviewer": "TP", "records": [bad]}], ds, dirs, emails={"TP": EMAIL})
    item = next(k for k, (_, o, g) in store.index(ds).items() if g == "items" and o["kind"] == "conflict")
    with pytest.raises(SystemExit):           # a conflict is accepted, held, rejected or resolved
        import_log.plan([{"reviewer": "TP", "records": [page_item(ds, item, "needs_research")]}], ds, dirs, emails={"TP": EMAIL})
    rec = page_item(ds, item, "accept")
    del rec["call"]
    rec["decision"] = "accept"
    with pytest.raises(SystemExit):           # a line decision on an item
        import_log.plan([{"reviewer": "TP", "records": [rec]}], ds, dirs, emails={"TP": EMAIL})
    assert before == {p: p.read_bytes() for d in b.values() for p in d.iterdir() if p.is_file()}


def test_record_fields_come_from_the_dataset_not_the_page(batches):
    backend, b, root = batches
    ds, dirs = ds_for(backend, b, root)
    key = f"{b['fix_a'].name}::10|Price"
    rec = page_line(ds, key, "reject", record_id="10|Name")      # a page that sent the wrong csv id
    run([{"reviewer": "TP", "records": [rec]}], ds, dirs)
    got = {r["id"]: r["decision"] for r in rows(b["fix_a"] / "decisions.csv")}
    assert got["10|Price"] == "reject" and got["10|Name"] == "accept"
