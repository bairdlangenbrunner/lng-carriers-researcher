"""Shared fixture for the review app tests: a tiny backend + one batch dir per mode.

Row ids are deliberately out of line order (10, 5, 7) so a live sheet row never equals
its row_id. decisions.csv in each batch is written by apply_batch.py itself.
"""
import csv
import json
import sys

import apply_batch

HEADER = ["original order in sheet", "IMO number", "Name", "Name [ref]", "Other names",
          "Other names [ref]", "Status", "Status [ref]", "Shipowner", "Shipbuilder",
          "Capacity", "Capacity units", "Capacity [ref]", "Price", "Price currency",
          "Price [ref]", "Delivery year"]
COLMAP = {"_header_row_idx": 1, "_data_starts_at": 2, "row_id": 0, "name": 2,
          "capacity": 10, "capacity_ref": 12, "status": 6, "status_ref": 7}
ROWS = [
    ["10", "9900010", "Hull 1 (SHI)", "http://old/name", "", "", "on order", "http://old/st",
     "Owner A", "Samsung Heavy Industries", "174000", "cbm", "", "250", "$m", "http://p", "2026"],
    ["5", "9900005", "Vessel Five", "", "", "", "on order", "", "Owner B", "Hanwha Ocean",
     "", "", "", "", "", "", "2027"],
    ["7", "", "Vessel Seven", "", "", "", "active", "", "Owner C", "HD Hyundai",
     "170000", "cbm", "", "", "", "", "2024"],
]
LONG_OTHER = "; ".join(f"Former name number {i:02d}" for i in range(14))  # > 300 chars


def write_backend(tmp_path):
    path = tmp_path / "backend.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["preamble"])
        w.writerow(HEADER)
        w.writerows(ROWS)
    (tmp_path / "backend.colmap.json").write_text(json.dumps(COLMAP))
    return path


def _run_apply(batch, backend):
    argv = sys.argv
    sys.argv = ["apply_batch", "--batch", str(batch), "--backend", str(backend)]
    try:
        apply_batch.main()
    finally:
        sys.argv = argv


def make_batches(tmp_path):
    """-> (backend_path, {name: batch_dir})."""
    backend = write_backend(tmp_path)
    root = tmp_path / "batches"
    root.mkdir()
    out = {}

    fix_a = root / "b1_fix"
    fix_a.mkdir()
    (fix_a / "fix.json").write_text(json.dumps({"corrections": [
        {"row_id": "10", "cells": [
            {"field": "Name", "new_value": "Atlantic Star", "confidence": "G",
             "confidence_why": "a live record keyed to this vessel states the value",
             "refs": [{"url": "http://ship/10"}], "note": "named"},
            {"field": "Status", "new_value": "active", "confidence": "G",
             "refs": [{"url": "http://ship/10"}], "note": "delivered"},
            {"field": "Price", "new_value": "250000000", "confidence": "Y", "preserve_ref": True,
             "note": "unit conversion"},
            {"field": "Price currency", "new_value": "USD", "confidence": "Y", "preserve_ref": True,
             "note": "unit conversion"},
        ]}]}))
    (fix_a / "gate_log.json").write_text(json.dumps([
        {"row_id": "10", "field": "Name", "value": "Atlantic Star", "url": "http://ship/10",
         "ok": True, "reason": "OK", "grade": "ok"}]))
    out["fix_a"] = fix_a

    fix_b = root / "b2_fix_other_names"
    fix_b.mkdir()
    (fix_b / "fix.json").write_text(json.dumps({"corrections": [
        {"row_id": "10", "cells": [
            {"field": "Other names", "new_value": LONG_OTHER, "confidence": "Y",
             "append_ref": True, "refs": [{"url": "http://ship/10"}], "note": "former name " * 20},
            {"field": "Status", "new_value": "active", "confidence": "Y",
             "refs": [{"url": "http://press/10"}], "note": "same cell, second batch"},
        ]}]}))
    out["fix_b"] = fix_b

    df = root / "b3_data_fill"
    df.mkdir()
    (df / "data_fill.json").write_text(json.dumps({"fills": [
        {"row_id": "5", "field": "Capacity", "ref_field": "Capacity [ref]", "proposed_value": "174000",
         "new_urls": ["http://cap/5"], "confidence": "G", "derivable": False, "prev_state": "blank",
         "confidence_why": "a live page states the value (§3.8c) and the value is specific to this cell",
         "note": "press"},
        {"row_id": "5", "field": "Capacity units", "ref_field": "", "proposed_value": "cbm",
         "new_urls": [], "confidence": "G", "derivable": True, "prev_state": "blank", "note": ""},
    ], "candidate_findings": [{"row_id": "7", "field": "Capacity", "backend_value": "170000",
                               "proposed_value": "174000", "sources": "http://c/7",
                               "recommendation": "check"}]}))
    out["data_fill"] = df

    rf = root / "b4_ref_fill"
    rf.mkdir()
    (rf / "citations.json").write_text(json.dumps({"cells": [
        {"row_id": "7", "field": "capacity_ref", "url": "http://cap/7", "confidence": "Y",
         "note": "rule F"}]}))
    out["ref_fill"] = rf

    disc = root / "b5_discovery"
    disc.mkdir()
    (disc / "candidates.json").write_text(json.dumps({"candidates": [
        {"cluster_id": "C1", "cluster_label": "SHI - Owner D 2x", "confidence": "Y",
         "discovery_notes": "DART",
         "row_data": {"Name": "Samsung HI (Owner D 1)", "Status": "on order",
                      "Status [ref]": "http://dart/1", "Shipbuilder": "Samsung Heavy Industries",
                      "Shipowner": "Owner D"}}], "backend_status_flags": []}))
    out["discovery"] = disc

    for b in out.values():
        _run_apply(b, backend)
    return backend, out
