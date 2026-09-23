"""Item 1: `build_workbook.py --mode fix` writes the GATE-SURVIVING refs (not the raw
source refs) into `<out>/fix.json`, with what the gate dropped recorded in
`dropped_refs` — and that gated fix.json, not the --fix source file, is what
`apply_batch.py` reads. Offline: monkeypatches `igu_refs.corroborates_cell` so no
network is touched.
"""
import argparse
import csv
import json

import build_workbook
import igu_refs
from review_fixture import _run_apply, write_backend

PASS_URL = "https://passes.example/a"
FAIL_URL = "https://fails.example/b"


def _gate(u, v, field="", imo=""):
    if u == PASS_URL:
        return True, "OK"
    return False, "page does not contain value"


def _build(tmp_path, monkeypatch):
    monkeypatch.setattr(igu_refs, "corroborates_cell", _gate)
    backend = write_backend(tmp_path)
    fix = tmp_path / "fix.json"
    fix.write_text(json.dumps({"batch_label": "t", "reason": "t", "corrections": [
        {"row_id": "10", "cells": [
            {"field": "Capacity", "new_value": "180000", "confidence": "Y",
             "refs": [{"url": PASS_URL}, {"url": FAIL_URL}],
             "note": "capacity correction"}]}]}))
    out = tmp_path / "out"
    out.mkdir()
    build_workbook.build_fix(argparse.Namespace(
        fix=str(fix), backend=str(backend), base=None, out=str(out)))
    return fix, out, backend


def test_fix_json_keeps_only_the_passing_ref(tmp_path, monkeypatch):
    fix, out, _backend = _build(tmp_path, monkeypatch)

    gated = json.loads((out / "fix.json").read_text())
    assert gated.get("gated", {}).get("by") == "build_workbook --mode fix"
    cell = gated["corrections"][0]["cells"][0]
    assert cell["refs"] == [PASS_URL]
    assert [d["url"] for d in cell["dropped_refs"]] == [FAIL_URL]
    assert cell["dropped_refs"][0]["reason"].startswith("DROPPED")
    # the computed grade landed in the gated copy too (one live pass, distinctive value)
    assert cell["confidence"] == "G"

    # the --fix SOURCE file is left byte-for-byte untouched (still lists both refs)
    source = json.loads(fix.read_text())
    source_cell = source["corrections"][0]["cells"][0]
    assert [r["url"] for r in source_cell["refs"]] == [PASS_URL, FAIL_URL]
    assert "gated" not in source
    assert "dropped_refs" not in source_cell


def test_apply_batch_emits_only_the_passing_ref(tmp_path, monkeypatch):
    _fix, out, backend = _build(tmp_path, monkeypatch)

    _run_apply(out, backend)

    patch_rows = list(csv.DictReader((out / "apply_patch.csv").open(encoding="utf-8")))
    ref_sets = [r for r in patch_rows if r["column"] == "Capacity [ref]"]
    assert len(ref_sets) == 1
    assert ref_sets[0]["value"] == PASS_URL
    assert FAIL_URL not in ref_sets[0]["value"]

    value_sets = [r for r in patch_rows if r["column"] == "Capacity"]
    assert len(value_sets) == 1
    assert value_sets[0]["value"] == "180000"

    rows_csv = list(csv.DictReader((out / "apply_rows.csv").open(encoding="utf-8")))
    row10 = next(r for r in rows_csv if r["original order in sheet"] == "10")
    assert row10["Capacity [ref]"] == PASS_URL
