"""Tests for scripts/dedup_index.py — the four backend match indexes.

The load-bearing guarantee is the stub row (dedup_index's own docstring): a
vessel pasted into the sheet as columns A-E only is invisible to the two
builder-keyed indexes, so without imo_index / name_index a completeness sweep
re-reports it as missing. These tests pin the stub detection, the
placeholder-safe name key, and the --pending mapping that says which of a
batch's candidates are already in the sheet. Pure logic, no network.
"""
import csv
import json

import pytest
from dedup_index import build_indexes, match_pending, name_key

HEADER = [
    "id", "Name", "Name [ref]", "IMO number", "IMO number [ref]", "Status",
    "Shipowner", "Shipbuilder", "Hull number", "Contract date", "Capacity",
]
I = {h: i for i, h in enumerate(HEADER)}


def _row(**vals):
    r = [""] * len(HEADER)
    for k, v in vals.items():
        r[I[k.replace("_", " ")] if k.replace("_", " ") in I else I[k]] = v
    return r


def _backend(tmp_path, rows, preamble=1):
    """Write a backend CSV + colmap in the real shape (header on row 1)."""
    path = tmp_path / "backend.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        for _ in range(preamble):
            w.writerow(["" for _ in HEADER])
        w.writerow(HEADER)
        w.writerows(rows)
    colmap = {
        "_header_row_idx": preamble, "_data_starts_at": preamble + 1,
        "row_id": I["id"], "name": I["Name"], "imo": I["IMO number"],
        "status": I["Status"], "shipowner": I["Shipowner"],
        "shipbuilder": I["Shipbuilder"], "hull": I["Hull number"],
        "contract_date": I["Contract date"],
    }
    (tmp_path / "backend.colmap.json").write_text(json.dumps(colmap))
    return str(path)


FILLED = _row(id="1", Name="Energy Glory", **{"IMO number": "9900000"},
              Status="active", Shipowner="JERA", Shipbuilder="Samsung Heavy Industries",
              **{"Hull number": "2301", "Contract date": "01-May-2024"})
STUB = _row(id="2", Name="Samsung HI (Dynagas 1)")
STUB_IMO = _row(id="3", Name="Hull H2706", **{"IMO number": "9193579"})


def test_filled_row_indexed_by_builder_and_not_a_stub(tmp_path):
    idx = build_indexes(_backend(tmp_path, [FILLED]))
    assert idx["stubs"] == []
    assert len(idx["hull_index"]) == 1
    assert len(idx["cluster_index"]) == 1
    entry = idx["imo_index"]["9900000"][0]
    assert entry["sheet_row"] == 3       # 1 preamble + header + first data row
    assert not entry.get("stub")


def test_stub_row_is_flagged_and_reachable_only_by_name_or_imo(tmp_path):
    idx = build_indexes(_backend(tmp_path, [STUB, STUB_IMO]))
    assert [s["sheet_row"] for s in idx["stubs"]] == [3, 4]
    # Invisible to the builder-keyed indexes — the whole reason for this work.
    assert idx["hull_index"] == {}
    assert idx["cluster_index"] == {}
    assert idx["name_index"]["samsung hi dynagas 1"][0]["stub"] is True
    assert idx["imo_index"]["9193579"][0]["sheet_row"] == 4


def test_unknown_status_row_is_not_a_stub(tmp_path):
    """Blank Status means "not filled in"; a researched row always carries one."""
    row = _row(id="4", Name="Mystery", Status="unknown", Shipowner="MOL")
    idx = build_indexes(_backend(tmp_path, [row]))
    assert idx["stubs"] == []


class TestNameKey:
    def test_keeps_parentheticals_that_distinguish_placeholders(self):
        assert name_key("Samsung HI (Dynagas 1)") != name_key("Samsung HI (Dynagas 2)")

    def test_folds_the_yard_abbreviation_variants(self):
        assert (name_key("HD Hyundai HI (HHI) Ulsan (Tsakos 2)")
                == name_key("HD Hyundai HI (HDHHI) Ulsan (Tsakos 2)"))

    def test_case_and_punctuation_insensitive(self):
        assert name_key("Hull H2706") == name_key("hull  h2706")

    def test_blank(self):
        assert name_key("") == ""
        assert name_key(None) == ""


def _batch(tmp_path, candidates):
    d = tmp_path / "batchdir"
    d.mkdir()
    (d / "candidates.json").write_text(json.dumps({"candidates": candidates}))
    return d


def test_pending_candidate_matches_its_stub_row_by_imo_then_name(tmp_path):
    idx = build_indexes(_backend(tmp_path, [STUB, STUB_IMO]))
    batch = _batch(tmp_path, [
        {"cluster_id": "C1.1", "row_data": {"Name": "Samsung HI (Dynagas 1)"}},
        {"cluster_id": "C4.1", "row_data": {"Name": "Hull H2706", "IMO number": "9193579"}},
    ])
    got = {r["cluster_id"]: r for r in match_pending(idx, [batch])}
    assert got["C1.1"]["state"] == "stub"
    assert got["C1.1"]["matched_by"] == "name"
    assert got["C4.1"]["matched_by"] == "imo"
    assert got["C4.1"]["sheet_rows"] == [4]


def test_pending_candidate_absent_from_the_sheet_is_reported_absent(tmp_path):
    idx = build_indexes(_backend(tmp_path, [FILLED]))
    batch = _batch(tmp_path, [{"cluster_id": "C9", "row_data": {"Name": "Hull H9999"}}])
    assert match_pending(idx, [batch])[0]["state"] == "absent"


def test_candidate_on_a_researched_row_is_filled_not_stub(tmp_path):
    idx = build_indexes(_backend(tmp_path, [FILLED]))
    batch = _batch(tmp_path, [
        {"cluster_id": "C0", "row_data": {"Name": "Energy Glory", "IMO number": "9900000"}}])
    assert match_pending(idx, [batch])[0]["state"] == "filled"


def test_lone_ordinal_is_dropped_only_when_it_cannot_over_merge(tmp_path):
    """C3 of the 2026-09-17 batch: `(unknown shipowner 1)` pasted without the 1."""
    sheet = _row(id="5", Name="HD Hyundai HI (HDHHI) Ulsan (unknown shipowner)")
    idx = build_indexes(_backend(tmp_path, [sheet]))
    solo = _batch(tmp_path, [{"cluster_id": "C3", "row_data": {
        "Name": "HD Hyundai HI (HHI) Ulsan (unknown shipowner 1)"}}])
    got = match_pending(idx, [solo])[0]
    assert got["state"] == "stub" and got["matched_by"] == "name-ordinal"


def test_a_numbered_cluster_never_collapses_onto_one_row(tmp_path):
    """`Dynagas 1`..`4` must NOT all land on a single `Dynagas` row."""
    sheet = _row(id="6", Name="Samsung HI (Dynagas)")
    idx = build_indexes(_backend(tmp_path, [sheet]))
    batch = _batch(tmp_path, [
        {"cluster_id": f"C1.{n}", "row_data": {"Name": f"Samsung HI (Dynagas {n})"}}
        for n in (1, 2, 3, 4)])
    assert {r["state"] for r in match_pending(idx, [batch])} == {"absent"}


def test_missing_candidates_file_is_not_an_error(tmp_path):
    idx = build_indexes(_backend(tmp_path, [FILLED]))
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert match_pending(idx, [empty]) == []
