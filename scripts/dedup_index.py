"""
Build dedup indexes from the backend CSV.

Two indexes per [ref]-Fill SOP §3.2 and Discovery SOP §4.3:
  - hull_index: (builder_norm, hull_norm) -> backend row(s)
      For matching CSB hulls against the backend.
  - cluster_index: (builder_norm, owner_norm, contract_month) -> backend row(s)
      For matching cluster-level signals (trade press, DART) against the
      backend when hull numbers aren't yet assigned.

Usage:
    python dedup_index.py
    # Writes <work_dir>/dedup_index.json with both indexes

Library:
    from dedup_index import build_indexes
    hull_idx, cluster_idx = build_indexes("<path>/backend.csv")
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Import siblings
sys.path.insert(0, str(Path(__file__).parent))
from normalize import normalize_builder, normalize_owner, normalize_hull
from paths import backend_csv_path, dedup_index_path


def _load_colmap(csv_path: str) -> dict:
    """Load the colmap.json sibling, or raise if missing."""
    map_path = Path(csv_path).with_suffix(".colmap.json")
    if not map_path.exists():
        raise RuntimeError(
            f"colmap.json not found at {map_path}. Run pull_backend.py first."
        )
    return json.loads(map_path.read_text())


def _contract_month(contract_date: str) -> str:
    """
    Normalize various contract date formats to YYYY-MM.
    Backend uses formats like "2026-03-15", "16-Dec-2025", "Dec 2025", "2026".
    """
    s = (contract_date or "").strip()
    if not s:
        return ""
    # YYYY-MM-DD or YYYY-MM
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # DD-MMM-YYYY
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    m = re.match(r"\d{1,2}[-\s]([A-Za-z]{3})[-\s](\d{4})", s)
    if m:
        mon = months.get(m.group(1).lower(), 0)
        if mon:
            return f"{m.group(2)}-{mon:02d}"
    # MMM YYYY
    m = re.match(r"([A-Za-z]{3})\s+(\d{4})", s)
    if m:
        mon = months.get(m.group(1).lower(), 0)
        if mon:
            return f"{m.group(2)}-{mon:02d}"
    # Just a year
    m = re.match(r"(\d{4})$", s)
    if m:
        return f"{m.group(1)}-00"
    return ""


def build_indexes(csv_path: str) -> tuple[dict, dict, list]:
    """
    Build hull_index and cluster_index from the backend CSV.
    Also returns the list of raw data rows (each as a list of cells).
    """
    colmap = _load_colmap(csv_path)
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f))

    data_start = colmap["_data_starts_at"]
    data = rows[data_start:]

    hull_idx = defaultdict(list)
    cluster_idx = defaultdict(list)

    ci_builder = colmap["shipbuilder"]
    ci_owner = colmap["shipowner"]
    ci_hull = colmap["hull"]
    ci_contract = colmap["contract_date"]
    ci_row = colmap["row_id"]

    for i, row in enumerate(data):
        try:
            builder_raw = row[ci_builder] if ci_builder is not None and len(row) > ci_builder else ""
            owner_raw = row[ci_owner] if ci_owner is not None and len(row) > ci_owner else ""
            hull_raw = row[ci_hull] if ci_hull is not None and len(row) > ci_hull else ""
            contract_raw = row[ci_contract] if ci_contract is not None and len(row) > ci_contract else ""
            row_id = row[ci_row] if ci_row is not None and len(row) > ci_row else str(i)
        except IndexError:
            continue

        b = normalize_builder(builder_raw)
        o = normalize_owner(owner_raw)
        h = normalize_hull(b, hull_raw)
        cm = _contract_month(contract_raw)

        if b and h:
            hull_idx[f"{b}|{h}"].append({
                "row_id": row_id, "data_row_index": i,
                "builder": builder_raw, "hull": hull_raw,
                "owner": owner_raw, "contract": contract_raw,
            })
        if b and o and cm:
            cluster_idx[f"{b}|{o}|{cm}"].append({
                "row_id": row_id, "data_row_index": i,
                "builder": builder_raw, "owner": owner_raw,
                "hull": hull_raw, "contract": contract_raw,
            })

    return dict(hull_idx), dict(cluster_idx), data


def main():
    csv_path = str(backend_csv_path())
    hull_idx, cluster_idx, data = build_indexes(csv_path)
    print(f"  Backend rows: {len(data)}")
    print(f"  Hull index keys (builder|hull): {len(hull_idx)}")
    print(f"  Cluster index keys (builder|owner|month): {len(cluster_idx)}")

    out = {
        "hull_index": hull_idx,
        "cluster_index": cluster_idx,
        "stats": {
            "total_rows": len(data),
            "hull_keys": len(hull_idx),
            "cluster_keys": len(cluster_idx),
        },
    }
    out_path = str(dedup_index_path())
    Path(out_path).write_text(json.dumps(out, indent=2, default=str))
    print(f"  Saved to {out_path}")

    # Sanity print: collisions (hulls/clusters with >1 row)
    print(f"\n  Hull-key collisions (>1 row, possible dupes):")
    for k, v in hull_idx.items():
        if len(v) > 1:
            print(f"    {k}: {len(v)} rows -> {[r['row_id'] for r in v]}")
    print(f"\n  First 5 cluster keys:")
    for k in list(cluster_idx.keys())[:5]:
        print(f"    {k}: {len(cluster_idx[k])} row(s)")


if __name__ == "__main__":
    main()
