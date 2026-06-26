"""
FSRU reconciliation — join the GIIGNL FSRU fleet table to the carrier backend.

The GIIGNL Annual Report's "FSRU FLEET AT THE END OF <year>" table is the most
complete public roster of *in-service* FSRUs, but it has NO IMO column, so the
join to the (IMO-rich) backend is by VESSEL NAME. Names drift — owner rebrands
(Golar→Energos, Transgas→Energos), conversions, diacritics (Höegh/Hoegh) — so we
join on the union {GIIGNL current name} ∪ {GIIGNL ex_names} against the backend
Name, normalized by normalize_vessel_name(). Capacity (storage m³ ↔ backend
Capacity cbm) is the corroborator; builder is NOT (for converted units GIIGNL
lists the conversion yard while the backend keeps the original builder).

Input : work/giignl_fsru_fleet.json (from the terminals-repo extractor) + the
        fresh backend CSV + colmap.
Output: work/fsru_reconcile.json — the bucketed reconciliation the FSRU workbook
        (build_workbook.py --mode fsru) renders. Advisory only; never edits the
        backend.

Buckets:
  matched      GIIGNL FSRU ↔ a backend row already typed FSRU (with field diffs)
  reclassify   GIIGNL FSRU ↔ a backend row typed something else (e.g. conventional
               / FSU) — a typing finding, not a gap
  manual       no name match, but capacity+delivery+owner strongly suggest a single
               backend row (e.g. Höegh Esperanza ↔ backend "Hoegh") — human pairs it
  candidate    in GIIGNL, not in the backend at all — a genuine gap to add. Small /
               power-barge units (storage < 60k m³ or CCS "Other") are flagged for
               FSRU-vs-small-scale human review rather than asserted as FSRUs.
  backend_only backend FSRUs absent from GIIGNL — mostly EXPECTED (GIIGNL is
               in-service only; on-order/idle tracker FSRUs won't appear)

Usage:
    python scripts/fsru_reconcile.py
    python scripts/fsru_reconcile.py --fleet work/giignl_fsru_fleet.json \
        --backend work/backend.csv --output work/fsru_reconcile.json
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from paths import backend_csv_path, work_dir
from normalize import normalize_vessel_name, normalize_builder, fsru_owner_tags

# storage m³ ↔ backend Capacity (cbm): agree if within EITHER band (handles both
# big absolute caps and small-scale units). GIIGNL rounds (135000 vs 136967 etc.).
CAP_TOL_FRAC = 0.03
CAP_TOL_ABS = 6000
# below this storage (or CCS == "other") a GIIGNL gap is flagged for FSRU-vs-
# small-scale / FSU human review rather than asserted as an FSRU to add.
SMALL_SCALE_M3 = 60000


def _int(s):
    try:
        return int(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def load_backend(path):
    """Return (header, data_rows, colmap, data_start_idx)."""
    path = Path(path)
    rows = list(csv.reader(open(path, encoding="utf-8")))
    cm = json.loads(path.with_suffix(".colmap.json").read_text())
    hi = cm["_header_row_idx"]
    ds = cm.get("_data_starts_at", hi + 1)
    return rows[hi], rows[ds:], cm, ds


def _idx(cm, hdr, key, header_name):
    i = cm.get(key)
    if i is None:
        i = {h: j for j, h in enumerate(hdr)}.get(header_name)
    return i


def backend_entries(hdr, data, cm, ds):
    """One dict per backend row, with the fields the reconciliation needs.
    sheet_row is the 1-based LIVE sheet row (data_start + offset + 1) — reports
    quote this, never the column-A 'original order' id."""
    NAME = _idx(cm, hdr, "name", "Name")
    IMO = _idx(cm, hdr, "imo", "IMO number")
    CAP = _idx(cm, hdr, "capacity", "Capacity")
    BLD = _idx(cm, hdr, "shipbuilder", "Shipbuilder")
    OWN = _idx(cm, hdr, "shipowner", "Shipowner")
    DYR = _idx(cm, hdr, "delivery_year", "Delivery year")
    VT = _idx(cm, hdr, "vessel_type", "Vessel type")

    def g(r, i):
        return r[i].strip() if i is not None and len(r) > i else ""

    out = []
    for off, r in enumerate(data):
        name = g(r, NAME)
        if not name:
            continue
        out.append({
            "sheet_row": ds + off + 1,
            "name": name,
            "norm": normalize_vessel_name(name),
            "imo": g(r, IMO),
            "capacity": _int(g(r, CAP)),
            "builder": g(r, BLD),
            "owner": g(r, OWN),
            "delivery_year": _int(g(r, DYR)),
            "vessel_type": g(r, VT),
        })
    return out


def cap_agree(a, b):
    if a is None or b is None:
        return None  # unknown
    return abs(a - b) <= max(CAP_TOL_ABS, CAP_TOL_FRAC * max(a, b))


def cap_distance(a, b):
    if a is None or b is None:
        return float("inf")
    return abs(a - b)


def diff_fields(g, be):
    """Field-level comparison for a matched pair. capacity is authoritative;
    builder is informational (conversion-yard vs original-builder); owner uses
    tag-set overlap; delivery compares GIIGNL built_year to backend Delivery year."""
    diffs = {}
    agree = cap_agree(g.get("storage_m3"), be["capacity"])
    diffs["capacity"] = {
        "giignl_storage_m3": g.get("storage_m3"),
        "backend_capacity": be["capacity"],
        "agree": agree,
    }
    g_bld, b_bld = normalize_builder(g.get("builder", "")), normalize_builder(be["builder"])
    diffs["builder"] = {
        "giignl": g.get("builder", ""), "backend": be["builder"],
        "same_tag": (g_bld == b_bld) if (g_bld and b_bld) else None,
        "note": "giignl lists conversion yard for converted units; informational",
    }
    g_yr, b_yr = g.get("built_year"), be["delivery_year"]
    diffs["delivery_year"] = {
        "giignl_built": g_yr, "backend_delivery": b_yr,
        "same": (g_yr == b_yr) if (g_yr and b_yr) else None,
    }
    g_own, b_own = fsru_owner_tags(g.get("vessel_owner", "")), fsru_owner_tags(be["owner"])
    diffs["owner"] = {
        "giignl": g.get("vessel_owner", ""), "backend": be["owner"],
        "overlap": bool(g_own & b_own) if (g_own and b_own) else None,
    }
    return diffs


def suggest_manual(g, unmatched):
    """A conservative single-row suggestion when there's no name match. Requires
    BOTH capacity agreement AND owner-tag overlap — capacity alone coincides far
    too often at common sizes (170k, 30k), which would mis-pair distinct vessels
    (e.g. GIIGNL 'Torman'/Access LNG vs backend 'Coral Encanto'/Anthony Veder).
    Delivery proximity is only a tiebreaker. Returns the best entry or None —
    never auto-resolved, only proposed for human pairing. This catches the
    backend-name-defect case (Höegh Esperanza ↔ backend 'Hoegh')."""
    g_own = fsru_owner_tags(g.get("vessel_owner", ""))
    if not g_own:
        return None
    cands = []
    for be in unmatched:
        if cap_agree(g.get("storage_m3"), be["capacity"]) is not True:
            continue
        if not (g_own & fsru_owner_tags(be["owner"])):
            continue
        yr_gap = (abs(g["built_year"] - be["delivery_year"])
                  if g.get("built_year") and be["delivery_year"] else 999)
        cands.append((yr_gap, cap_distance(g.get("storage_m3"), be["capacity"]), be))
    if not cands:
        return None
    cands.sort(key=lambda t: (t[0], t[1]))
    return cands[0][2]


def reconcile(fleet, backend):
    index = defaultdict(list)
    for be in backend:
        if be["norm"]:
            index[be["norm"]].append(be)

    matched, reclassify, manual, candidates = [], [], [], []
    used_rows = set()

    for g in fleet["vessels"]:
        keys = {normalize_vessel_name(g["vessel_name"])}
        keys |= {normalize_vessel_name(e) for e in g.get("ex_names", [])}
        keys.discard("")
        hits = {be["sheet_row"]: be for k in keys for be in index.get(k, [])}
        hits = list(hits.values())

        if hits:
            fsru_hits = [h for h in hits if h["vessel_type"] == "FSRU"]
            pool = fsru_hits or hits
            best = min(pool, key=lambda h: cap_distance(g.get("storage_m3"), h["capacity"]))
            used_rows.add(best["sheet_row"])
            rec = {"giignl": g, "backend": best, "matched_on": "name/ex-name",
                   "diffs": diff_fields(g, best)}
            (matched if best["vessel_type"] == "FSRU" else reclassify).append(rec)
            continue

        cand = suggest_manual(g, [be for be in backend if be["sheet_row"] not in used_rows])
        if cand:
            used_rows.add(cand["sheet_row"])
            manual.append({"giignl": g, "suggested_backend": cand,
                           "matched_on": "capacity+delivery/owner (no name match)",
                           "diffs": diff_fields(g, cand)})
            continue

        small = (g.get("storage_m3") or 0) < SMALL_SCALE_M3 or \
                (g.get("ccs", "").strip().lower() == "other")
        candidates.append({
            "giignl": g,
            "small_scale_review": small,
            "review_reason": ("storage < 60k m³ / CCS 'Other' — confirm FSRU vs "
                              "small-scale/FSU before adding" if small
                              else "full-size FSRU absent from backend"),
        })

    # backend FSRUs GIIGNL didn't account for (expected: on-order / idle / spot)
    backend_only = [be for be in backend
                    if be["vessel_type"] == "FSRU" and be["sheet_row"] not in used_rows]
    backend_fsu = [be for be in backend if be["vessel_type"] == "FSU"]

    return {
        "edition_year": fleet.get("edition_year"),
        "fleet_count": len(fleet["vessels"]),
        "backend_fsru_count": sum(1 for be in backend if be["vessel_type"] == "FSRU"),
        "summary": {
            "matched": len(matched),
            "reclassify": len(reclassify),
            "manual": len(manual),
            "candidates": len(candidates),
            "candidates_small_scale": sum(1 for c in candidates if c["small_scale_review"]),
            "backend_only": len(backend_only),
            "backend_fsu": len(backend_fsu),
            "orderbook": len(fleet.get("orderbook", [])),
        },
        "matched": matched,
        "reclassify": reclassify,
        "manual": manual,
        "candidates": candidates,
        "backend_only": backend_only,
        "backend_fsu": backend_fsu,
        "orderbook": fleet.get("orderbook", []),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reconcile GIIGNL FSRU fleet vs backend.")
    ap.add_argument("--fleet", default=None, help="GIIGNL fleet JSON (default work/giignl_fsru_fleet.json)")
    ap.add_argument("--backend", default=None, help="backend CSV (default work/backend.csv)")
    ap.add_argument("--output", default=None, help="output JSON (default work/fsru_reconcile.json)")
    args = ap.parse_args(argv)

    fleet_path = Path(args.fleet) if args.fleet else work_dir() / "giignl_fsru_fleet.json"
    backend_path = Path(args.backend) if args.backend else backend_csv_path()
    out_path = Path(args.output) if args.output else work_dir() / "fsru_reconcile.json"

    fleet = json.loads(fleet_path.read_text())
    hdr, data, cm, ds = load_backend(backend_path)
    backend = backend_entries(hdr, data, cm, ds)

    result = reconcile(fleet, backend)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    s = result["summary"]
    print(f"  GIIGNL edition {result['edition_year']}: {result['fleet_count']} fleet FSRUs "
          f"vs {result['backend_fsru_count']} backend FSRUs")
    print(f"  matched={s['matched']}  reclassify={s['reclassify']}  manual={s['manual']}  "
          f"candidates={s['candidates']} (small-scale {s['candidates_small_scale']})  "
          f"backend_only={s['backend_only']}")
    print(f"  Saved reconciliation to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
