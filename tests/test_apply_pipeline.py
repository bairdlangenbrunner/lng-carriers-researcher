"""Tests for the review->apply->verify pipeline (apply_batch.py + verify_apply.py).

The load-bearing guarantees: accepted values land in the CORRECT column of the
full-row paste artifact (offset-proof), only Green/derivable proposals are accepted
by default while Yellow is held, editing decisions.csv changes what gets applied, and
verify_apply correctly classifies landed / mismatch / missing. Pure logic, no network.
"""
import csv
import json
import sys

import apply_batch
import verify_apply

HEADER = ["original order in sheet", "Shipowner", "Shipowner country/area",
          "Shipowner country/area [ref]", "Shipbuilder", "Cargo type",
          "Cargo type [ref]", "Name", "Hull number"]
COLMAP = {"_header_row_idx": 0, "_data_starts_at": 1, "row_id": 0}


def _backend(tmp_path, rows):
    csv_path = tmp_path / "backend.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    (tmp_path / "backend.colmap.json").write_text(json.dumps(COLMAP))
    return csv_path


def _data_fill_batch(tmp_path):
    batch = tmp_path / "batch"
    batch.mkdir()
    payload = {
        "fills": [
            {"row_id": "1", "field": "Shipowner country/area",
             "ref_field": "Shipowner country/area [ref]", "proposed_value": "United States",
             "new_urls": ["http://u"], "confidence": "G", "derivable": True, "prev_state": "blank"},
            {"row_id": "1", "field": "Cargo type", "ref_field": "Cargo type [ref]",
             "proposed_value": "membrane", "new_urls": ["http://m"], "confidence": "Y",
             "derivable": False, "prev_state": "blank"},
        ],
        "candidate_findings": [],
    }
    (batch / "data_fill.json").write_text(json.dumps(payload))
    return batch


def _run_apply(monkeypatch, batch, backend):
    monkeypatch.setattr(sys, "argv",
                        ["apply_batch", "--batch", str(batch), "--backend", str(backend)])
    apply_batch.main()


def _rows_by_id(path):
    rows = list(csv.reader(open(path)))
    H = {h: i for i, h in enumerate(rows[0])}
    return H, {r[0]: r for r in rows[1:]}


class TestApplyBatchDataFill:
    def test_green_accepted_yellow_held_and_offset_proof(self, tmp_path, monkeypatch):
        backend = _backend(tmp_path, [
            ["1", "Hanwha Shipping", "", "", "Hanwha Philly SY", "", "", "Vessel A", "H1"],
        ])
        batch = _data_fill_batch(tmp_path)
        _run_apply(monkeypatch, batch, backend)

        # decisions.csv: green->accept, yellow->hold
        dec = {r["id"]: r["decision"] for r in csv.DictReader(open(batch / "decisions.csv"))}
        assert dec["1|Shipowner country/area"] == "accept"
        assert dec["1|Cargo type"] == "hold"

        # apply_rows.csv: accepted value in the CORRECT column; held value absent
        H, by_id = _rows_by_id(batch / "apply_rows.csv")
        assert by_id["1"][H["Shipowner country/area"]] == "United States"
        assert by_id["1"][H["Shipowner country/area [ref]"]] == "http://u"
        assert by_id["1"][H["Cargo type"]] == ""        # yellow held, not applied

        # apply.json counts
        doc = json.loads((batch / "apply.json").read_text())
        assert doc["counts"]["accepted"] == 1 and doc["counts"]["hold"] == 1

    def test_editing_decisions_applies_the_held_fill(self, tmp_path, monkeypatch):
        backend = _backend(tmp_path, [
            ["1", "Hanwha Shipping", "", "", "Hanwha Philly SY", "", "", "Vessel A", "H1"],
        ])
        batch = _data_fill_batch(tmp_path)
        _run_apply(monkeypatch, batch, backend)

        # flip the Yellow cargo fill to accept, re-run
        lines = list(csv.DictReader(open(batch / "decisions.csv")))
        for ln in lines:
            if ln["id"] == "1|Cargo type":
                ln["decision"] = "accept"
        with open(batch / "decisions.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=lines[0].keys())
            w.writeheader(); w.writerows(lines)
        _run_apply(monkeypatch, batch, backend)

        H, by_id = _rows_by_id(batch / "apply_rows.csv")
        assert by_id["1"][H["Cargo type"]] == "membrane"        # now applied
        assert by_id["1"][H["Cargo type [ref]"]] == "http://m"


class TestVerifyApply:
    def test_landed_mismatch_missing(self, tmp_path, monkeypatch, capsys):
        backend = _backend(tmp_path, [
            ["1", "Hanwha Shipping", "United States", "http://u", "Hanwha Philly SY", "", "", "A", "H1"],
            ["2", "GasLog", "Greece", "http://g", "Samsung", "spherical", "http://s", "B", "H2"],
        ])
        batch = tmp_path / "batch"
        batch.mkdir()
        (batch / "apply.json").write_text(json.dumps({
            "batch": "t", "mode": "data_fill",
            "accepted_cells": [
                {"row_id": "1", "column": "Shipowner country/area", "value": "United States"},  # landed
                {"row_id": "2", "column": "Cargo type", "value": "membrane"},                   # mismatch (spherical)
                {"row_id": "1", "column": "Cargo type", "value": "membrane"},                   # missing (blank)
            ],
            "accepted_new_rows": [], "counts": {},
        }))
        monkeypatch.setattr(sys, "argv",
                            ["verify_apply", "--batch", str(batch), "--backend", str(backend)])
        verify_apply.main()

        status = {(r["row_id"], r["column"]): r["status"]
                  for r in csv.DictReader(open(batch / "verify_report.csv"))}
        assert status[("1", "Shipowner country/area")] == "landed"
        assert status[("2", "Cargo type")] == "MISMATCH"
        assert status[("1", "Cargo type")] == "MISSING"
