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

from backend_io import load_backend
from build_workbook import YARD_LOCATION_COLS, _join_refs, _yard_location_map_table_first
from normalize import normalize_builder
from paths import backend_csv_path

ACCEPT, HOLD, REJECT = "accept", "hold", "reject"


def _default_decision(confidence, derivable):
    return ACCEPT if (derivable or confidence == "G") else HOLD


def _load_backend(backend_path):
    """(header, row_by_id, colmap) — thin wrapper kept for the downstream
    importers (batch_digest, dedupe_check, verify_apply)."""
    be = load_backend(backend_path)
    return be.header, be.row_by_id(), be.colmap


def sheet_row_map(backend_path, colmap=None):
    """Map ``row_id`` -> live Google Sheet tab row (1-based).

    ``row_id`` is column A ("original order in sheet") — a static stamp that drifts
    from the live row as rows are deleted, so it is NOT the tab row. Use this
    whenever a row is reported to a human (they navigate the actual sheet).
    Delegates to backend_io.Backend.sheet_row_map.
    """
    return load_backend(backend_path).sheet_row_map()


def _detect(batch_dir):
    for fname, mode in (("data_fill.json", "data_fill"),
                        ("candidates.json", "discovery"),
                        ("citations.json", "ref_fill"),
                        ("fix.json", "fix")):
        p = batch_dir / fname
        if p.exists():
            payload = json.loads(p.read_text())
            if mode == "fix" and not payload.get("gated"):
                # Item 1: since build_workbook.py --mode fix started writing its OWN gated
                # fix.json into the batch dir, a fix.json with no "gated" marker is either
                # hand-copied from an ungated --fix source or predates that change — its
                # `refs` may include URLs the §3.8c gate dropped, or an un-swapped IGU
                # landing page. Old batches (regrade_confidence.py reruns) still work; warn
                # rather than refuse.
                print(f"  [warn] {p} has no 'gated' marker — its refs may be UNGATED "
                      f"(rebuild with `build_workbook.py --mode fix` to gate them); "
                      f"proceeding anyway", file=sys.stderr)
            return mode, payload
    raise SystemExit(f"No batch input JSON found in {batch_dir} "
                     "(expected data_fill.json / candidates.json / citations.json / fix.json)")


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
                "confidence_why": f.get("confidence_why", ""),
                "note": f.get("note", ""), "prev_state": f.get("prev_state", "blank"),
                # §5 regrade inputs (confidence.py): what the gate must be told about the cell
                "gate_value": f.get("proposed_value", ""),
                "derived_from": f.get("derived_from"), "cap_reason": f.get("cap_reason", ""),
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
                "confidence_why": cand.get("confidence_why", ""),
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
                "confidence_why": c.get("confidence_why", ""),
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
                "confidence_why": f.get("confidence_why", ""),
                "note": f.get("note", ""), "prev_state": "blank", "row_data": None,
            })
        for c in payload.get("data_conflicts", []):
            conflicts.append(_conflict_row(c))

    elif mode == "fix":
        # A fix batch CORRECTS a non-blank value, so its gated refs REPLACE the paired
        # [ref] (replace_ref) instead of being appended; preserve_ref cells rewrite the
        # value only and leave the [ref] alone; append_ref cells (a former name added to
        # `Other names`) append to the existing [ref] like a data fill.
        for corr in payload.get("corrections", []):
            rid = str(corr["row_id"])
            for c in corr.get("cells", []):
                col = c.get("field", "")
                urls = [] if c.get("preserve_ref") else \
                    [r["url"] if isinstance(r, dict) else r for r in c.get("refs", [])]
                items.append({
                    "id": f"{rid}|{col}", "kind": "fill", "row_id": rid, "cluster_id": "",
                    "column": col, "value": c.get("new_value", ""),
                    "ref_column": f"{col} [ref]" if urls else "",
                    "ref_value": ", ".join(urls),
                    "confidence": c.get("confidence", "Y"), "derivable": False,
                    "confidence_why": c.get("confidence_why", ""),
                    "note": c.get("note", ""), "prev_state": "fix",
                    "replace_ref": not c.get("append_ref"),
                    # §5 regrade inputs (confidence.py)
                    "gate_value": str(c.get("gate_value") or c.get("new_value", "")),
                    "preserve_ref": bool(c.get("preserve_ref")),
                    "former_year": c.get("former_year", ""), "cap_reason": c.get("cap_reason", ""),
                    "row_data": None,
                })

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


def cell_writes(it, header_index, row):
    """[(column, value)] an accepted non-new-row item writes, given the backend `row` it lands
    on: the value (unless ref-only), then the paired [ref] — replaced by a fix cell's gated
    refs, else joined onto what `row` already holds. Shared with review_app/push.py."""
    H, out = header_index, []
    if it["kind"] == "fill" and it["column"] in H and not it.get("ref_only"):
        out.append((it["column"], it["value"]))
    if it["ref_column"] and it["ref_value"] and it["ref_column"] in H:
        i = H[it["ref_column"]]
        existing_ref = row[i] if row is not None and len(row) > i else ""
        out.append((it["ref_column"], it["ref_value"] if it.get("replace_ref") else
                    _join_refs(existing_ref, it["ref_value"].split(", "))))
    return out


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
        for column, value in cell_writes(it, H, row_by_id.get(rid)):
            base[H[column]] = value
            patch.append(["set", rid, column, value])
            cells.append({"row_id": rid, "column": column, "value": value,
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
