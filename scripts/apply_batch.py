"""
Turn a reviewed batch into offset-proof, trackable apply artifacts.

The last mile — getting accepted proposals from a candidate workbook back into the
Google Sheets backend — was pure manual copy/paste, which is exactly what corrupted
rows 1216/1217. This script closes that gap. It reads a batch's input JSON
(`data_fill.json` / `candidates.json` / `citations.json`), records an accept/reject
decision per proposal, and emits:

  decisions.csv     one row per proposal with a default + editable `decision`
                    (acceptance tracking — edit it and re-run to refine)
  apply.json        canonical record of what was accepted (drives verify_apply.py)
  apply_rows.csv    FULL backend-column-order rows for accepted items — paste a whole
                    row over the matching backend row (data/ref) or into a new row
                    (discovery). Full-width paste can't land in the wrong column.
  apply_patch.csv   flat (op,key,column,value) cell patch for the by-name Apps Script
                    applier (tools/apply_patch.gs) — addresses cells by header, so a
                    column offset is impossible.
  conflicts.csv     research that disagrees with a NON-blank backend value — a separate
                    human decision channel (never an automatic fill).

Two-phase UX: the first run writes decisions.csv pre-filled (Green/derivable -> accept,
Yellow/Red -> hold) and emits the artifacts for the defaults. Edit the holds and re-run
to finalize; an existing decisions.csv is preserved, never clobbered.

    python scripts/apply_batch.py --batch batches/<dir> [--backend work/backend.csv]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from paths import backend_csv_path
from normalize import normalize_builder
from build_workbook import _join_refs, _yard_location_map_table_first, YARD_LOCATION_COLS

ACCEPT, HOLD, REJECT = "accept", "hold", "reject"


def _default_decision(confidence, derivable):
    return ACCEPT if (derivable or confidence == "G") else HOLD


def _load_backend(backend_path):
    rows = list(csv.reader(open(backend_path, encoding="utf-8")))
    colmap = json.loads(Path(backend_path).with_suffix(".colmap.json").read_text())
    header = rows[colmap["_header_row_idx"]]
    data = rows[colmap.get("_data_starts_at", colmap["_header_row_idx"] + 1):]
    rid_i = colmap["row_id"]
    row_by_id = {r[rid_i].strip(): r for r in data if len(r) > rid_i and r[rid_i].strip()}
    return header, row_by_id, colmap


def sheet_row_map(backend_path, colmap=None):
    """Map ``row_id`` -> live Google Sheet tab row (1-based).

    ``row_id`` is column A ("original order in sheet") — a static stamp that drifts
    from the live row as rows are deleted, so it is NOT the tab row. The backend
    pull is 1:1 with the sheet, so the live row = CSV line index + 1. Use this
    whenever a row is reported to a human (they navigate the actual sheet).
    """
    rows = list(csv.reader(open(backend_path, encoding="utf-8")))
    cm = colmap or json.loads(
        Path(backend_path).with_suffix(".colmap.json").read_text())
    ri = cm["row_id"]
    ds = cm.get("_data_starts_at", cm["_header_row_idx"] + 1)
    out = {}
    for idx in range(ds, len(rows)):
        r = rows[idx]
        if len(r) > ri and r[ri].strip():
            out[r[ri].strip()] = idx + 1
    return out


def _detect(batch_dir):
    for fname, mode in (("data_fill.json", "data_fill"),
                        ("candidates.json", "discovery"),
                        ("citations.json", "ref_fill")):
        p = batch_dir / fname
        if p.exists():
            return mode, json.loads(p.read_text())
    raise SystemExit(f"No batch input JSON found in {batch_dir} "
                     "(expected data_fill.json / candidates.json / citations.json)")


def _items_and_conflicts(mode, payload, header, colmap):
    """Normalize a batch payload into a uniform list of proposal `items` + `conflicts`."""
    items, conflicts = [], []

    if mode == "data_fill":
        for f in payload.get("fills", []):
            rid, col = str(f["row_id"]), f.get("field", "")
            items.append({
                "id": f"{rid}|{col}", "kind": "fill", "row_id": rid, "cluster_id": "",
                "column": col, "value": f.get("proposed_value", ""),
                "ref_column": f.get("ref_field", ""),
                "ref_value": ", ".join(f.get("new_urls", []) or []),
                "confidence": f.get("confidence", "R"), "derivable": bool(f.get("derivable")),
                "note": f.get("note", ""), "prev_state": f.get("prev_state", "blank"),
                # corroborate fills append refs only — the data value is unchanged,
                # so the value column must never be (re)written (see value-write guard).
                "ref_only": f.get("prev_state") == "corroborate",
                "row_data": None,
            })
        for c in payload.get("candidate_findings", []):
            conflicts.append(_conflict_row(c))

    elif mode == "discovery":
        for cand in payload.get("candidates", []):
            cid = cand.get("cluster_id", "")
            items.append({
                "id": f"cluster:{cid}", "kind": "new_row", "row_id": "", "cluster_id": cid,
                "column": "", "value": "", "ref_column": "", "ref_value": "",
                "confidence": cand.get("confidence", "Y"), "derivable": False,
                "note": cand.get("discovery_notes", ""), "prev_state": "blank",
                "row_data": dict(cand.get("row_data", {})),
                "cluster_label": cand.get("cluster_label", ""),
            })
        for c in payload.get("backend_status_flags", []):
            conflicts.append(_conflict_row(c))

    elif mode == "ref_fill":
        # field is a canonical colmap key (e.g. "hull_ref"); map it to a header string.
        key_to_header = {k: header[v] for k, v in colmap.items()
                         if not k.startswith("_") and isinstance(v, int) and v < len(header)}
        for c in payload.get("cells", []):
            rid = str(c["row_id"])
            col = key_to_header.get(c.get("field", ""), c.get("field", ""))
            items.append({
                "id": f"{rid}|{col}", "kind": "ref", "row_id": rid, "cluster_id": "",
                "column": col, "value": "", "ref_column": col,
                "ref_value": c.get("url", ""), "confidence": c.get("confidence", "R"),
                "derivable": False, "note": c.get("note", ""), "prev_state": "blank",
                "row_data": None,
            })
        for f in payload.get("candidate_data_fills", []):
            rid, col = str(f.get("row_id", "")), f.get("field", "")
            items.append({
                "id": f"{rid}|{col}", "kind": "fill", "row_id": rid, "cluster_id": "",
                "column": col, "value": f.get("proposed_value", ""),
                "ref_column": f.get("ref_field", ""),
                "ref_value": ", ".join(f.get("new_urls", []) or []),
                "confidence": f.get("confidence", "R"), "derivable": False,
                "note": f.get("note", ""), "prev_state": "blank", "row_data": None,
            })
        for c in payload.get("data_conflicts", []):
            conflicts.append(_conflict_row(c))

    return items, conflicts


def _conflict_row(c):
    """Best-effort map a freeform finding into the conflicts.csv shape."""
    if isinstance(c, str):
        return {"row_id": "", "column": "", "backend_value": "", "proposed_value": "",
                "sources": "", "recommendation": c}
    g = lambda *ks: next((str(c[k]) for k in ks if c.get(k)), "")
    return {
        "row_id": g("row_id", "row_ids"),
        "column": g("field", "column", "issue_type"),
        "backend_value": g("backend_value", "backend", "current"),
        "proposed_value": g("proposed_value", "research_value", "proposed"),
        "sources": g("sources", "source_urls", "urls"),
        "recommendation": g("recommendation", "suggested_action", "details", "note", "detail"),
    }


def _load_or_init_decisions(path, items):
    """Read an existing decisions.csv (preserving edits); else None."""
    if not path.exists():
        return None
    by_id = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_id[(row.get("id") or "").strip()] = (row.get("decision") or "").strip().lower()
    return by_id


def _write_decisions(path, items, decisions):
    cols = ["id", "kind", "row_id", "cluster_id", "column", "confidence",
            "derivable", "default", "decision", "proposed_value", "note"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for it in items:
            default = _default_decision(it["confidence"], it["derivable"])
            w.writerow({
                "id": it["id"], "kind": it["kind"], "row_id": it["row_id"],
                "cluster_id": it["cluster_id"], "column": it["column"],
                "confidence": it["confidence"], "derivable": it["derivable"],
                "default": default, "decision": decisions.get(it["id"], default),
                "proposed_value": (it["value"] or it["ref_value"])[:80], "note": it["note"][:80],
            })


def _discovery_full_row(it, header, yard_map):
    """Build a full backend-width row (header order) for a discovery candidate."""
    row_data = dict(it["row_data"] or {})
    for k in YARD_LOCATION_COLS:
        row_data.pop(k, None)
    tag = normalize_builder(row_data.get("Shipbuilder", ""))
    if tag and tag in yard_map:
        row_data.update(yard_map[tag])
    return [row_data.get(h, "") for h in header], row_data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, help="Batch directory under batches/")
    ap.add_argument("--backend", default=str(backend_csv_path()))
    args = ap.parse_args()
    batch_dir = Path(args.batch)

    mode, payload = _detect(batch_dir)
    header, row_by_id, colmap = _load_backend(args.backend)
    items, conflicts = _items_and_conflicts(mode, payload, header, colmap)
    yard_map = _yard_location_map_table_first(list(row_by_id.values()), header)

    # decisions: preserve an existing file, else pre-fill from defaults
    dec_path = batch_dir / "decisions.csv"
    existing = _load_or_init_decisions(dec_path, items)
    decisions = {it["id"]: _default_decision(it["confidence"], it["derivable"]) for it in items}
    if existing:                       # human edits override defaults; new items keep defaults
        decisions.update({k: v for k, v in existing.items() if v})
    _write_decisions(dec_path, items, decisions)

    accepted = [it for it in items if decisions.get(it["id"], "").lower() == ACCEPT]

    # --- apply_rows.csv: full backend-width rows (offset-proof wholesale paste) ---
    touched = {}     # row_id -> mutable copy of the backend row
    new_rows = []    # discovery: (full_row, row_data, cluster_id, confidence)
    cells = []       # canonical accepted cells for apply.json
    patch = []       # flat (op, key, column, value)
    for it in accepted:
        if it["kind"] == "new_row":
            full, row_data = _discovery_full_row(it, header, yard_map)
            new_rows.append({"cluster_id": it["cluster_id"], "confidence": it["confidence"],
                             "row_data": row_data})
            new_rows[-1]["_full"] = full
            for h, v in row_data.items():
                if v:
                    patch.append(["append", it["cluster_id"], h, v])
            continue
        rid = it["row_id"]
        base = touched.get(rid) or list(row_by_id.get(rid, [""] * len(header)))
        touched[rid] = base + [""] * (len(header) - len(base))
        base = touched[rid]
        H = {h: i for i, h in enumerate(header)}
        if it["kind"] == "fill" and it["column"] in H and not it.get("ref_only"):
            base[H[it["column"]]] = it["value"]
            patch.append(["set", rid, it["column"], it["value"]])
            cells.append({"row_id": rid, "column": it["column"], "value": it["value"],
                          "confidence": it["confidence"]})
        if it["ref_column"] and it["ref_value"] and it["ref_column"] in H:
            existing_ref = row_by_id.get(rid, [""] * len(header))[H[it["ref_column"]]] \
                if rid in row_by_id and len(row_by_id[rid]) > H[it["ref_column"]] else ""
            joined = _join_refs(existing_ref, it["ref_value"].split(", "))
            base[H[it["ref_column"]]] = joined
            patch.append(["set", rid, it["ref_column"], joined])
            cells.append({"row_id": rid, "column": it["ref_column"], "value": joined,
                          "confidence": it["confidence"]})

    with open(batch_dir / "apply_rows.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for rid in sorted(touched, key=lambda s: int(s) if s.isdigit() else 0):
            w.writerow(touched[rid][:len(header)])
        for nr in new_rows:
            w.writerow(nr["_full"][:len(header)])

    with open(batch_dir / "apply_patch.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["op", "key", "column", "value"])
        w.writerows(patch)

    with open(batch_dir / "conflicts.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["row_id", "column", "backend_value", "proposed_value", "sources",
                "recommendation", "decision"]
        w.writerow(cols)
        for c in conflicts:
            w.writerow([c.get(k, "") for k in cols[:-1]] + ["hold"])

    apply_doc = {
        "batch": batch_dir.name, "mode": mode,
        "accepted_cells": cells,
        "accepted_new_rows": [{"cluster_id": nr["cluster_id"], "confidence": nr["confidence"],
                               "row_data": nr["row_data"]} for nr in new_rows],
        "counts": {"items": len(items), "accepted": len(accepted),
                   "hold": sum(1 for it in items if decisions.get(it["id"]) == HOLD),
                   "reject": sum(1 for it in items if decisions.get(it["id"]) == REJECT),
                   "conflicts": len(conflicts)},
    }
    (batch_dir / "apply.json").write_text(json.dumps(apply_doc, indent=2, ensure_ascii=False))

    c = apply_doc["counts"]
    first_run = existing is None
    print(f"apply_batch [{mode}] {batch_dir.name}", file=sys.stderr)
    print(f"  proposals: {c['items']}  ->  accept {c['accepted']}, hold {c['hold']}, "
          f"reject {c['reject']}  |  conflicts: {c['conflicts']}", file=sys.stderr)
    print(f"  wrote decisions.csv, apply.json, apply_rows.csv, apply_patch.csv, "
          f"conflicts.csv in {batch_dir}", file=sys.stderr)
    if first_run:
        print("  (first run — decisions.csv pre-filled by confidence; edit the 'hold' "
              "rows and re-run to finalize)", file=sys.stderr)


if __name__ == "__main__":
    main()
