"""shipvault_api_refs.py --backend-batch: the ADDED log must be a list.

review_data.gate_verdicts (review_app/) reads shipvault_api_refs.json's `added`
as a list of {"where", "value", "url", "result"} entries — the same shape the
--batch mode writes. Regression for the backend-batch mode once writing an int
count instead, which silently made every card in the review app show "not
checked" (batch 6, 2026-09-17). No network: renders_blank / corroborates are
stubbed the way a real blank-rendering, corroborating page would answer.
"""
import csv
import json

import shipvault_api_refs as sv
from backend_io import load_backend

HEADER = ["original order in sheet", "Name", "Name [ref]", "Shipbuilder", "Shipbuilder [ref]"]
COLMAP = {"_header_row_idx": 0, "_data_starts_at": 1, "row_id": 0}


def _backend(tmp_path, rows):
    csv_path = tmp_path / "backend.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    (tmp_path / "backend.colmap.json").write_text(json.dumps(COLMAP))
    return load_backend(csv_path)


def test_backend_batch_writes_added_as_a_list(tmp_path, monkeypatch):
    be = _backend(tmp_path, [
        ["1", "Test Vessel", "", "General Dynamics", "https://www.shipvault.com/ships/12345"],
    ])
    monkeypatch.setattr(sv, "load_backend", lambda: be)
    monkeypatch.setattr(sv, "renders_blank", lambda uid: True)
    monkeypatch.setattr(sv, "corroborates", lambda url, value: (True, "ok"))

    out_dir = tmp_path / "batch"
    sv.backend_batch(out_dir, [])

    result = json.loads((out_dir / "shipvault_api_refs.json").read_text())
    assert isinstance(result["added"], list)
    assert result["added"] == [{
        "where": "live row 2 (row_id 1) | Shipbuilder [ref]",
        "value": "General Dynamics",
        "url": "https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/12345",
        "result": "ADDED",
    }]
