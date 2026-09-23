"""
Build dedup indexes from the backend CSV.

Four indexes per [ref]-Fill SOP §3.2 and Discovery SOP §4.3:
  - hull_index: (builder_norm, hull_norm) -> backend row(s)
      For matching CSB hulls against the backend.
  - cluster_index: (builder_norm, owner_norm, contract_month) -> backend rows
      For matching cluster-level signals (trade press, DART) against the
      backend when hull numbers aren't yet assigned.
  - imo_index: IMO -> backend row(s)
  - name_index: name_key(Name) -> backend row(s)

The last two exist for STUB ROWS. A discovery batch's accepted vessels are
pasted into the sheet by hand, and that paste can land columns A-E only --
Name, IMO and their [ref]s -- leaving Status, Shipbuilder, Shipowner, Contract
date and Capacity blank until the batch's remaining holds are decided. Sheet
rows 1220-1231 (the 2026-09-17 discovery batch) are in exactly that state.
Such a row is invisible to hull_index and cluster_index, because both key on
the shipbuilder, so a completeness sweep re-reports its vessel as missing.
`stubs` lists them, and --pending maps them back to the batch they came from.

Usage:
    python dedup_index.py
    python dedup_index.py --pending batches/2026-09-17_0431ET_discovery_since_jun_2026
    # Writes <work_dir>/dedup_index.json

Library:
    from dedup_index import build_indexes
    idx = build_indexes("<path>/backend.csv")        # dict of indexes + stubs
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Import siblings
sys.path.insert(0, str(Path(__file__).parent))
from backend_io import contract_month as _contract_month
from backend_io import load_backend
from normalize import normalize_builder, normalize_hull, normalize_owner
from paths import backend_csv_path, dedup_index_path

# Yard abbreviations that vary between the candidate workbook and what gets
# pasted into the sheet -- the 2026-09-17 batch wrote "HD Hyundai HI (HHI)
# Ulsan (Tsakos 2)" and the sheet carries "(HDHHI)". Dropped from the name key
# so the two forms match. Deliberately minimal: only variants actually seen.
_YARD_ABBR = {"hhi", "hdhhi"}


def name_key(s: str) -> str:
    """Match key for a backend Name, placeholder forms included.

    NOT normalize_vessel_name() -- that drops parenthetical content, which on a
    placeholder is the only thing that distinguishes one row from the next
    ("Samsung HI (Dynagas 1)" and "(Dynagas 2)" would collide on "samsung hi").
    This keeps the parentheses' contents, folds the yard-abbreviation variants,
    and reduces to lowercase alphanumeric tokens.
    """
    if not s:
        return ""
    toks = [t for t in re.split(r"[^0-9a-z]+", str(s).lower()) if t]
    toks = [t for t in toks if t not in _YARD_ABBR]
    return " ".join(toks)


def build_indexes(csv_path: str) -> dict:
    """Build the four indexes from the backend CSV.

    Returns a dict with hull_index, cluster_index, imo_index, name_index,
    stubs and data (the raw data rows).
    """
    be = load_backend(csv_path)
    colmap = be.colmap
    data = be.data

    hull_idx = defaultdict(list)
    cluster_idx = defaultdict(list)
    imo_idx = defaultdict(list)
    name_idx = defaultdict(list)
    stubs = []

    ci_builder = colmap["shipbuilder"]
    ci_owner = colmap["shipowner"]
    ci_hull = colmap["hull"]
    ci_contract = colmap["contract_date"]
    ci_row = colmap["row_id"]
    ci_name = colmap["name"]
    ci_imo = colmap["imo"]
    ci_status = colmap["status"]

    for i, row in enumerate(data):
        cell = lambda ci: be.cell(row, ci)  # noqa: E731
        builder_raw = cell(ci_builder)
        owner_raw = cell(ci_owner)
        hull_raw = cell(ci_hull)
        contract_raw = cell(ci_contract)
        name_raw = cell(ci_name)
        imo_raw = cell(ci_imo)
        status_raw = cell(ci_status)
        row_id = cell(ci_row) or str(i)

        b = normalize_builder(builder_raw)
        o = normalize_owner(owner_raw)
        h = normalize_hull(b, hull_raw)
        cm = _contract_month(contract_raw)

        # A stub: pasted Name (+ IMO) with none of the columns the structural
        # indexes key on. Blank Status is the signature -- every researched row
        # carries one, so a blank means "not filled in yet", not "unknown".
        stub = not status_raw and not builder_raw and not owner_raw

        entry = {
            "row_id": row_id, "data_row_index": i,
            "sheet_row": be.data_start + i + 1,
            "name": name_raw, "imo": imo_raw, "status": status_raw,
            "builder": builder_raw, "owner": owner_raw,
            "hull": hull_raw, "contract": contract_raw,
        }
        if stub:
            entry["stub"] = True
            stubs.append(entry)

        if b and h:
            hull_idx[f"{b}|{h}"].append(entry)
        if b and o and cm:
            cluster_idx[f"{b}|{o}|{cm}"].append(entry)
        if imo_raw:
            imo_idx[imo_raw].append(entry)
        if name_key(name_raw):
            name_idx[name_key(name_raw)].append(entry)

    return {
        "hull_index": dict(hull_idx),
        "cluster_index": dict(cluster_idx),
        "imo_index": dict(imo_idx),
        "name_index": dict(name_idx),
        "stubs": stubs,
        "data": data,
    }


def _candidates_of(batch_dir: Path) -> list[dict]:
    """The candidate vessels a discovery batch proposed (candidates.json)."""
    f = Path(batch_dir) / "candidates.json"
    if not f.exists():
        return []
    doc = json.loads(f.read_text())
    out = []
    for c in doc.get("candidates", []):
        rd = c.get("row_data", {}) or {}
        out.append({
            "batch": Path(batch_dir).name,
            "cluster_id": c.get("cluster_id") or c.get("id") or "",
            "name": rd.get("Name", ""),
            "imo": str(rd.get("IMO number", "") or ""),
            "hull": rd.get("Hull number", ""),
        })
    return out


def base_key(key: str) -> str:
    """A name key with any trailing ordinal removed.

    `samsung hi dynagas 1` -> `samsung hi dynagas`. Used two ways: to drop the
    ordinal a one-vessel cluster carries in the candidate workbook but usually
    loses when pasted into the sheet (C3 of the 2026-09-17 batch), and -- on
    the whole batch -- to count how many candidates share that base, so a
    numbered `Dynagas 1`..`4` cluster never collapses onto a single row.
    """
    return re.sub(r"\s+\d+$", "", key)


def match_pending(idx: dict, batch_dirs) -> list[dict]:
    """Map each batch's candidate vessels onto the backend row holding it.

    IMO first, then the placeholder-tolerant name key, then that key without a
    trailing ordinal -- the last only where no other candidate in the batch
    shares the same ordinal-free base, so a `Dynagas 1`..`4` cluster can never
    collapse onto a single `Dynagas` row. A candidate that lands on a stub row is already in
    the sheet awaiting its remaining columns; one that lands nowhere is
    genuinely absent and a sweep SHOULD re-report it.
    """
    out = []
    for d in batch_dirs:
        cands = _candidates_of(Path(d))
        bases = Counter(base_key(name_key(c["name"])) for c in cands)
        for cand in cands:
            hits = idx["imo_index"].get(cand["imo"], []) if cand["imo"] else []
            how = "imo" if hits else ""
            nk = name_key(cand["name"])
            if not hits and nk:
                hits = idx["name_index"].get(nk, [])
                how = "name" if hits else ""
            sk = base_key(nk)
            if not hits and sk != nk and bases[sk] == 1:
                hits = idx["name_index"].get(sk, [])
                how = "name-ordinal" if hits else ""
            rec = dict(cand, matched_by=how,
                       sheet_rows=[h["sheet_row"] for h in hits],
                       stub=bool(hits) and all(h.get("stub") for h in hits))
            rec["state"] = ("absent" if not hits
                            else "stub" if rec["stub"] else "filled")
            out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", nargs="*", default=[], metavar="BATCH_DIR",
                    help="discovery batch dirs whose candidates to locate in the sheet")
    args = ap.parse_args()

    csv_path = str(backend_csv_path())
    idx = build_indexes(csv_path)
    data = idx.pop("data")
    print(f"  Backend rows: {len(data)}", file=sys.stderr)
    print(f"  Hull index keys (builder|hull): {len(idx['hull_index'])}", file=sys.stderr)
    print(f"  Cluster index keys (builder|owner|month): {len(idx['cluster_index'])}",
          file=sys.stderr)
    print(f"  IMO index keys: {len(idx['imo_index'])}", file=sys.stderr)
    print(f"  Name index keys: {len(idx['name_index'])}", file=sys.stderr)
    print(f"  Stub rows (Name pasted, nothing else): {len(idx['stubs'])}", file=sys.stderr)
    for s in idx["stubs"]:
        print(f"    sheet row {s['sheet_row']:>5}  {s['name'][:50]}", file=sys.stderr)

    pending = match_pending(idx, args.pending) if args.pending else []
    if pending:
        print(f"\n  Pending batch candidates: {len(pending)}", file=sys.stderr)
        for r in pending:
            where = ",".join(str(x) for x in r["sheet_rows"]) or "-"
            print(f"    {r['state']:<7} {r['cluster_id']:<6} {r['name'][:42]:<42} "
                  f"rows {where}", file=sys.stderr)

    out = {
        **idx,
        "pending_candidates": pending,
        "stats": {
            "total_rows": len(data),
            "hull_keys": len(idx["hull_index"]),
            "cluster_keys": len(idx["cluster_index"]),
            "imo_keys": len(idx["imo_index"]),
            "name_keys": len(idx["name_index"]),
            "stub_rows": len(idx["stubs"]),
            "pending_absent": sum(1 for r in pending if r["state"] == "absent"),
        },
    }
    out_path = str(dedup_index_path())
    Path(out_path).write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  Saved to {out_path}", file=sys.stderr)

    print("\n  Hull-key collisions (>1 row, possible dupes):", file=sys.stderr)
    for k, v in idx["hull_index"].items():
        if len(v) > 1:
            print(f"    {k}: {len(v)} rows -> {[r['row_id'] for r in v]}", file=sys.stderr)


if __name__ == "__main__":
    main()
