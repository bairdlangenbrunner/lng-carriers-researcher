"""
Pull the latest backend data from the LNG Carrier Tracker Google Sheet and
derive the column-index map from the header row.

The user is actively editing the backend between batches, so always pull fresh.
The schema also drifts — columns get added/removed/renamed. This script
re-derives the column indices from the actual header row rather than
hard-coding offsets.

Anonymous/public CSV export endpoints (gviz `tqx=out:csv`, `/export?format=csv`,
`/pub`, `/htmlview`) were deliberately disabled org-wide on 2026-07-29 and now
return 401 by design. The only sanctioned read path is the authenticated `gws`
CLI work profile (read-only) — never reintroduce a public-URL fallback.

Usage:
    python pull_backend.py                          # default output path
    python pull_backend.py --out work/backend.csv   # custom path
    python pull_backend.py --map-only               # just print column indices
    python pull_backend.py --gid <tab-gid>          # pull a different tab

The backend spreadsheet ID and tab gid default to this project's "data -
backend" tab. To point the pipeline at a different sheet/tab, pass
--spreadsheet-id / --gid or set the LNGCT_BACKEND_SHEET_ID /
LNGCT_BACKEND_GID environment variables.

Output:
    <repo_root>/work/backend.csv (or specified path)
    Prints the column-index map to stdout for confirmation.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fetch import FetchError
from paths import backend_csv_path

DEFAULT_SPREADSHEET_ID = "1FjjeQD8AlQ_kQAMrohA3jAV3yZy7Lb61djt25D-4Fh8"
DEFAULT_GID = 243795339  # "data - backend" tab (docs/sops/discovery.md, ref_fill.md)

GWS_ENV = {
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": str(Path.home() / ".config" / "gws-gem"),
    "GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND": "file",
}


# Columns we care about — keyed by canonical short name, value is the
# expected header text (case-insensitive substring match). The actual
# column index is derived from the header row at runtime.
EXPECTED_COLUMNS = {
    # row_id is the row KEY: the UUID column (column A since 2026-09-23).
    # legacy_row_id is the old "original order in sheet" stamp, kept only while
    # the column exists (optional); data/legacy_row_ids.csv maps it to the UUID
    # forever, so batches keyed by the old numeric id still resolve.
    "row_id": "uuid",
    "legacy_row_id": "original order in sheet",
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

# Expected columns whose absence is not a schema problem.
OPTIONAL_COLUMNS = {"legacy_row_id"}


def require_gws() -> None:
    """Raise FetchError with a setup hint if the gws CLI isn't on PATH."""
    if shutil.which("gws") is None:
        raise FetchError(
            "gws (Google Workspace CLI) not found on PATH. It's the only "
            "sanctioned way to read this sheet — anonymous CSV export URLs "
            "were deliberately disabled org-wide 2026-07-29. Install gws and "
            "confirm ~/.config/gws-gem is configured for the work profile."
        )


def _gws(*args: str) -> dict:
    """Run a `gws` subcommand under the read-only work profile; return parsed
    JSON. Strips the CLI's non-JSON preamble line ("Using keyring backend:
    file") that precedes the actual JSON body."""
    require_gws()
    out = subprocess.run(
        ["gws", *args],
        env={**os.environ, **GWS_ENV},
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise FetchError(f"gws {' '.join(args)} failed: {out.stderr.strip()}")
    stdout = out.stdout
    if "{" not in stdout:
        raise FetchError(f"gws {' '.join(args)} returned no JSON: {stdout.strip()}")
    return json.loads(stdout[stdout.index("{"):])


def resolve_tab_title(spreadsheet_id: str, gid: int) -> str:
    """Map a tab gid to its current title via the Sheets API.

    Tabs are addressed by title, not gid, in the Sheets API — but gid is the
    stable identifier callers/docs reference, so this is a dynamic lookup
    (not a hardcoded mapping) that survives the tab being renamed.
    """
    data = _gws("sheets", "spreadsheets", "get", "--params",
                json.dumps({"spreadsheetId": spreadsheet_id,
                            "fields": "sheets.properties(sheetId,title)"}))
    for sheet in data.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("sheetId") == gid:
            return props["title"]
    raise FetchError(f"gid {gid} not found in spreadsheet {spreadsheet_id}")


def fetch_csv(out_path: str, spreadsheet_id: str = DEFAULT_SPREADSHEET_ID,
              gid: int = DEFAULT_GID) -> None:
    """Pull the backend tab via the authenticated Sheets API (`gws` CLI,
    read-only work profile) and cache it as a CSV grid matching the shape the
    old (now-dead) anonymous CSV export produced: full grid from row 1,
    ragged rows padded to a uniform width."""
    title = resolve_tab_title(spreadsheet_id, gid)
    print(f"  downloading backend tab {title!r} via gws ...", file=sys.stderr)
    data = _gws("sheets", "spreadsheets", "values", "get", "--params",
                json.dumps({"spreadsheetId": spreadsheet_id, "range": f"'{title}'"}))
    values = data.get("values", [])
    if len(values) < 5:
        raise FetchError(
            f"{title!r} returned a suspiciously small grid ({len(values)} "
            f"rows) — check the sheet is still shared with the work profile "
            f"and the spreadsheet ID / gid are still valid."
        )
    width = max(len(row) for row in values)
    rows = [row + [""] * (width - len(row)) for row in values]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    size = out_path.stat().st_size
    print(f"  Pulled {size:,} bytes ({len(rows)} rows) to {out_path}",
          file=sys.stderr)


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

    # A CSV without a UUID column (a pre-2026-09-23 snapshot, a test fixture)
    # keys rows by the legacy stamp instead.
    if col_map.get("row_id") is None:
        col_map["row_id"] = col_map.get("legacy_row_id")
    return col_map


def main():
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--out", default=str(backend_csv_path()))
    p.add_argument("--spreadsheet-id",
                   default=os.environ.get("LNGCT_BACKEND_SHEET_ID",
                                          DEFAULT_SPREADSHEET_ID),
                   help="Backend spreadsheet ID (default: this project's sheet; "
                        "also settable via LNGCT_BACKEND_SHEET_ID)")
    p.add_argument("--gid", type=int,
                   default=int(os.environ.get("LNGCT_BACKEND_GID", DEFAULT_GID)),
                   help="Backend tab gid (default: the 'data - backend' tab; "
                        "also settable via LNGCT_BACKEND_GID)")
    p.add_argument("--map-only", action="store_true",
                   help="Skip the fetch; just derive the map from an existing CSV")
    args = p.parse_args()

    if not args.map_only:
        try:
            fetch_csv(args.out, spreadsheet_id=args.spreadsheet_id, gid=args.gid)
        except FetchError as e:
            sys.exit(f"error: {e}")

    col_map = derive_column_map(args.out)

    print(f"\nColumn-index map (header row {col_map['_header_row_idx']}, "
          f"data starts at {col_map['_data_starts_at']}):")
    for k, v in col_map.items():
        if k.startswith("_"):
            continue
        status = "OK" if v is not None else ("absent, optional" if k in OPTIONAL_COLUMNS else "MISSING")
        print(f"  {k:25} = {v!s:5} [{status}]")

    missing = [k for k, v in col_map.items()
               if not k.startswith("_") and v is None and k not in OPTIONAL_COLUMNS]
    if missing:
        print(f"\n  WARNING: {len(missing)} expected columns not found:",
              file=sys.stderr)
        for k in missing:
            print(f"    {k}  (expected header text: {EXPECTED_COLUMNS[k]!r})",
                  file=sys.stderr)
        print("\n  Schema may have changed — check the backend header row "
              "before proceeding with the batch.", file=sys.stderr)

    # Also save the map next to the CSV for downstream scripts
    map_path = Path(args.out).with_suffix(".colmap.json")
    map_path.write_text(json.dumps(col_map, indent=2))
    print(f"\n  Column map saved to {map_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
