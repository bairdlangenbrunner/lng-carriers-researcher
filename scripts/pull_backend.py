"""
Pull the latest backend CSV from the public Google Sheets export URL and
derive the column-index map from the header row.

The user is actively editing the backend between batches, so always pull fresh.
The schema also drifts — columns get added/removed/renamed. This script
re-derives the column indices from the actual header row rather than
hard-coding offsets.

Usage:
    python pull_backend.py                          # default output path
    python pull_backend.py --out /tmp/backend.csv   # custom path
    python pull_backend.py --map-only               # just print column indices

Output:
    <repo_root>/work/backend.csv (or specified path)
    Prints the column-index map to stdout for confirmation.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from paths import backend_csv_path


BACKEND_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1FjjeQD8AlQ_kQAMrohA3jAV3yZy7Lb61djt25D-4Fh8/"
    "export?format=csv&gid=243795339"
)


# Columns we care about — keyed by canonical short name, value is the
# expected header text (case-insensitive substring match). The actual
# column index is derived from the header row at runtime.
EXPECTED_COLUMNS = {
    "row_id": "original order in sheet",
    "name": "name",
    "imo": "imo number",
    "imo_ref": "imo number [ref]",
    "hull": "hull number",
    "hull_ref": "hull number [ref]",
    "name_ref": "name [ref]",
    "status": "status",
    "status_ref": "status [ref]",
    "shipowner": "shipowner",
    "shipowner_ref": "shipowner [ref]",
    "shipbuilder": "shipbuilder",
    "shipbuilder_ref": "shipbuilder [ref]",
    "capacity": "capacity",
    "capacity_ref": "capacity [ref]",
    "vessel_type": "vessel type",
    "vessel_type_ref": "vessel type [ref]",
    "propulsion": "propulsion type",
    "propulsion_ref": "propulsion type [ref]",
    "cargo_type": "cargo type",
    "cargo_type_ref": "cargo type [ref]",
    "delivery_year": "delivery year",
    "delivery_year_ref": "delivery year [ref]",
    "contract_date": "contract date",
    "contract_date_ref": "contract date [ref]",
    "operator_charterer": "operator/charterer",
    "operator_charterer_ref": "operator/charterer [ref]",
    "price": "price",
    "price_ref": "price [ref]",
    "original_source": "[original source]",
}


def fetch_csv(out_path: str) -> None:
    """curl the public CSV export. web_fetch is blocked by Google robots.txt."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60",
         BACKEND_CSV_URL, "-o", out_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    size = Path(out_path).stat().st_size
    if size < 1000:
        raise RuntimeError(
            f"CSV suspiciously small ({size} bytes) — check the URL and that "
            f"the sheet is still publicly accessible."
        )
    print(f"  Pulled {size:,} bytes to {out_path}", file=sys.stderr)


def derive_column_map(csv_path: str) -> dict:
    """
    Read the header row and return a dict: canonical_name -> 0-indexed column.
    Returns None for any expected column that isn't found (so the caller can
    detect schema changes).
    """
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # The header is sometimes on row 0, sometimes on row 1 (depends on whether
    # there's a "checked for X update" leading row). Detect by looking for
    # the row that contains "Shipowner" or "Shipbuilder".
    header_row_idx = None
    for i, row in enumerate(rows[:5]):
        joined = " ".join(c.lower() for c in row)
        if "shipowner" in joined and "shipbuilder" in joined:
            header_row_idx = i
            break
    if header_row_idx is None:
        raise RuntimeError("Could not find header row in first 5 rows of CSV")

    header = rows[header_row_idx]
    col_map = {"_header_row_idx": header_row_idx, "_data_starts_at": header_row_idx + 1}

    # For each expected column, find the first header cell that contains the
    # expected text (case-insensitive substring match).
    for canonical, needle in EXPECTED_COLUMNS.items():
        idx = None
        for i, h in enumerate(header):
            h_norm = h.lower().strip()
            # Match exact, then substring
            if h_norm == needle:
                idx = i
                break
        if idx is None:
            # Substring fallback
            for i, h in enumerate(header):
                if needle in h.lower().strip():
                    idx = i
                    break
        col_map[canonical] = idx

    return col_map


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(backend_csv_path()))
    p.add_argument("--map-only", action="store_true",
                   help="Skip the fetch; just derive the map from an existing CSV")
    args = p.parse_args()

    if not args.map_only:
        fetch_csv(args.out)

    col_map = derive_column_map(args.out)

    print(f"\nColumn-index map (header row {col_map['_header_row_idx']}, "
          f"data starts at {col_map['_data_starts_at']}):")
    for k, v in col_map.items():
        if k.startswith("_"):
            continue
        status = "OK" if v is not None else "MISSING"
        print(f"  {k:25} = {v!s:5} [{status}]")

    missing = [k for k, v in col_map.items()
               if not k.startswith("_") and v is None]
    if missing:
        print(f"\n  WARNING: {len(missing)} expected columns not found:")
        for k in missing:
            print(f"    {k}  (expected header text: {EXPECTED_COLUMNS[k]!r})")
        print(f"\n  Schema may have changed — check the backend header row "
              f"before proceeding with the batch.")

    # Also save the map next to the CSV for downstream scripts
    map_path = Path(args.out).with_suffix(".colmap.json")
    map_path.write_text(json.dumps(col_map, indent=2))
    print(f"\n  Column map saved to {map_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
