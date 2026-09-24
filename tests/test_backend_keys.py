"""Tests for the row key in scripts/backend_io.py — UUID column A, legacy ids as aliases.

Since 2026-09-23 the backend's key is the `UUID` column; the old "original order in
sheet" stamp is `legacy_row_id`. Batches built before the switch are keyed by the
legacy id and must still resolve, but the two forms must never make a row appear
twice (that would read as a duplicate vessel to dedupe_check and double qc counts).

Pure logic, no network.
"""
import csv
import json

from backend_io import load_backend, parse_row_spec

U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
SPARE = "33333333-3333-4333-8333-333333333333"
HEADER = ["UUID", "original order in sheet", "Name", "IMO number"]


def _backend(tmp_path, rows, *, uuid=True):
    path = tmp_path / "backend.csv"
    header = HEADER if uuid else HEADER[1:]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([str(i + 1) for i in range(len(header))])   # the =column() index row
        w.writerow(header)
        w.writerows(r if uuid else r[1:] for r in rows)
    cm = {"_header_row_idx": 1, "_data_starts_at": 2}
    if uuid:
        cm.update(row_id=0, legacy_row_id=1, name=2, imo=3)
    else:   # an older snapshot: pull_backend falls back to the legacy column as the key
        cm.update(row_id=0, legacy_row_id=0, name=1, imo=2)
    (tmp_path / "backend.colmap.json").write_text(json.dumps(cm))
    return load_backend(str(path))


ROWS = [
    [U1, "10", "Arctic One", "9000001"],
    [U2, "11", "Arctic Two", "9000002"],
    [SPARE, "", "", ""],
]


def test_legacy_id_resolves_without_double_listing(tmp_path):
    be = _backend(tmp_path, ROWS)
    rows = be.row_by_id()
    assert rows["10"] is rows[U1]
    assert "11" in rows and rows.get("11")[2] == "Arctic Two"
    assert sorted(rows) == sorted([U1, U2])          # legacy ids are never listed
    assert len(list(rows.values())) == 2


def test_sheet_row_map_is_live_row_for_either_form(tmp_path):
    srm = _backend(tmp_path, ROWS).sheet_row_map()
    assert srm[U1] == srm["10"] == 3                 # header on row 2, first data row 3
    assert srm.get("11") == 4
    assert srm.get("999") is None


def test_spare_rows_are_not_vessels(tmp_path):
    be = _backend(tmp_path, ROWS)
    assert be.is_spare(ROWS[2]) and not be.is_spare(ROWS[0])
    assert be.key_of(ROWS[2]) == ""
    assert SPARE not in be.row_by_id() and SPARE not in be.sheet_row_map()


def test_canonical_key_and_item_id(tmp_path):
    be = _backend(tmp_path, ROWS)
    assert be.canonical_key("10") == U1
    assert be.canonical_key(U1) == U1
    assert be.canonical_key("999") == "999"          # names no live row: unchanged
    assert be.canonical_item_id("11|Name") == f"{U2}|Name"
    assert be.canonical_item_id("C1") == "C1"        # no column part (a cluster id)


def test_map_rows_and_legacy_of(tmp_path):
    be = _backend(tmp_path, ROWS)
    imo = be.map_rows(lambda r: r[3])
    assert imo["10"] == "9000001" and len(imo) == 2
    assert be.legacy_of(ROWS[1]) == "11"


def test_assignment_through_a_legacy_id_updates_the_uuid_entry(tmp_path):
    rows = _backend(tmp_path, ROWS).row_by_id()
    rows["10"] = ["replaced"]
    assert rows[U1] == ["replaced"] and len(rows) == 2


def test_no_uuid_column_falls_back_to_legacy_key(tmp_path):
    be = _backend(tmp_path, ROWS[:2], uuid=False)
    rows = be.row_by_id()
    assert sorted(rows) == ["10", "11"]
    assert be.canonical_key("10") == "10"
    assert be.sheet_row_map()["11"] == 4


def test_rows_by_sheet_row_uses_live_rows(tmp_path):
    be = _backend(tmp_path, ROWS)
    assert [r[2] for r in be.rows_by_sheet_row("4-5")] == ["Arctic Two", ""]
    assert parse_row_spec("3-4,7") == {3, 4, 7}
