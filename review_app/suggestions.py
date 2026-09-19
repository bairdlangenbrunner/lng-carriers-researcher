"""
Review-app suggestions -> a standard fix.json, so a suggested value reaches the backend only
through the normal QC-SOP path (other_names.py -> build_workbook.py --mode fix, whose §3.8c
gate is the re-gate -> recalc -> batch_digest / apply_batch).

    python review_app/suggestions.py --batches batches/<dir> [<dir> ...] \
        [--out work/review_suggestions_fix.json]

A suggestion is a proposal whose latest review_log.jsonl record is `suggest` and whose
decisions.csv line still says `reject` (suggest is stored as reject). Each becomes one cell:
`new_value` = the suggested value, `refs` = the original proposal's refs, `confidence` = the
original's, `note` = reviewer + note. `cosmetic` -> `preserve_ref: true`, no refs.

Not emitted, reported instead: discovery (new-row) and ref-only lines. Read-only over the
batch dirs and the backend; writes only --out.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import review_data  # noqa: E402  (puts scripts/ on sys.path)
import store  # noqa: E402
from paths import work_dir  # noqa: E402

LIST_SEP = "; "   # multi-valued cells (Other names)


def _refs(p):
    return list(dict.fromkeys(r["url"] for r in p["refs"] if r.get("url")))


def cell_for(p, mode, rec):
    """(cell, report) for one suggestion: report is None, or (bucket, text) when the cell is
    emitted with a caveat or not emitted at all (cell None)."""
    col, value, kind = p["column"], rec["suggested_value"], rec.get("suggest_kind") or "value"
    if p["kind"] == "new_row":
        return None, ("not_emitted", "discovery new row: out of scope for a fix batch — decide it in the batch")
    if p["kind"] == "ref" or "ref_only" in p["flags"]:
        return None, ("not_emitted", "ref-only line: there is no value to replace")
    cell = {"field": col, "new_value": value, "confidence": p["confidence"] or "Y",
            "note": f"review suggestion ({rec.get('reviewer', '')}, {rec.get('ts', '')[:16]}): "
                    f"{rec.get('note', '')} — instead of {p['proposed']!r} ({p['batch']}::{p['id']})",
            "review_key": f"{p['batch']}::{p['id']}"}
    report = None
    refs = _refs(p)
    if kind == "cosmetic" and p["current_refs"]:
        cell["preserve_ref"] = True     # same fact: the paired [ref] stays, the gate is skipped
        return cell, None
    if kind == "cosmetic":
        # a blank [ref] in the backend has nothing to preserve (Rule F): gate it as a value
        report = ("cosmetic_gated", "cosmetic, but the backend cell has no [ref] to keep — gated as a value")
    if "append_ref" in p["flags"]:
        cur = [x for x in p["current"].split(LIST_SEP) if x]
        added = [x for x in value.split(LIST_SEP) if x and x not in cur]
        if len(added) != 1:
            return None, ("not_emitted", f"multi-valued cell: the suggestion adds {len(added)} elements to "
                                         "the current cell (one expected) — hand-build this cell")
        cell.update(append_ref=True, gate_value=added[0])
    elif mode == "data_fill" and p["current_refs"]:
        # Data-fill SOP §4: refs already on an `unknown` cell are appended to, never replaced
        cell.update(append_ref=True, gate_value=value)
    cell["refs"] = [{"url": u} for u in refs]
    if not refs:
        report = ("needs_source", "no ref to gate — the built cell will carry no [ref] until one is found")
    return cell, report


def collect(batch_dirs, backend_path=None, info_path=None):
    data = review_data.build(batch_dirs, backend_path, info_path)
    dirs = {d.name: d for d in batch_dirs}
    cur = store.overlay(data, dirs)
    modes = {b["dir"]: b["mode"] for b in data["batches"]}
    order = {b["dir"]: b["apply_order"] for b in data["batches"]}
    live = {v["row_id"]: v for v in data["vessels"] if v.get("row_id")}
    reports = []
    # a suggest record whose decisions.csv line no longer says reject was overridden by hand
    for b, d in dirs.items():
        for key, rec in store.latest(store.read_jsonl(d / "review_log.jsonl")).items():
            p = cur["proposals"].get(key)
            if rec.get("decision") == "suggest" and p and p["decision"] != "suggest":
                reports.append(("superseded", p, f"decisions.csv now says {p['decision']}"))
    cells = {}   # (row_id, field) -> (apply_order, proposal, cell)
    for key in sorted(cur["proposals"]):
        p = cur["proposals"][key]
        if p["decision"] != "suggest":
            continue
        rec = p["last"]
        cell, rep = cell_for(p, modes[p["batch"]], rec)
        if rep:
            reports.append((rep[0], p, rep[1]))
        if not cell:
            continue
        slot = (p["row_id"], p["column"])
        if slot in cells:
            prev = cells[slot]
            loser, winner = (prev, (order[p["batch"]], p, cell)) if order[p["batch"]] >= prev[0] \
                else ((order[p["batch"]], p, cell), prev)
            reports.append(("duplicate", loser[1], f"same cell also suggested in {winner[1]['batch']} "
                                                   "(later batch kept)"))
            cells[slot] = winner
        else:
            cells[slot] = (order[p["batch"]], p, cell)
    by_row = {}
    for (rid, _f), (_o, p, cell) in cells.items():
        by_row.setdefault(rid, []).append(cell)
    corrections = []
    for rid, cs in by_row.items():
        v = live.get(rid, {})
        corrections.append({"row_id": rid, "_live_row": v.get("live_row"), "_name": v.get("name", ""),
                            "cells": sorted(cs, key=lambda c: data["header"].index(c["field"])
                                            if c["field"] in data["header"] else 999)})
    corrections.sort(key=lambda c: (c["_live_row"] is None, c["_live_row"] or 0, c["row_id"]))
    today = datetime.now(store.ET).date().isoformat()
    fix = {"batch_label": f"Fix — review app suggestions ({today})",
           "reason": "Values suggested in the review app instead of a batch's proposal (the proposal itself "
                     "is rejected in its decisions.csv). Each value is re-gated here (§3.8c) against the "
                     "original proposal's refs; cosmetic suggestions keep the paired [ref] (QC §4).",
           "corrections": corrections}
    return fix, reports


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batches", nargs="+", required=True)
    ap.add_argument("--out", default=None, help="default work/review_suggestions_fix.json")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--info", default=None, help="review_batches.json (dir -> label / apply_order / applied)")
    args = ap.parse_args(argv)
    batch_dirs = review_data.resolve_dirs(args.batches)
    review_data.check_backend(args.backend)
    fix, reports = collect(batch_dirs, args.backend, args.info)
    out = Path(args.out) if args.out else work_dir() / "review_suggestions_fix.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fix, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(c["cells"]) for c in fix["corrections"])
    print(f"{n} suggested cell(s) on {len(fix['corrections'])} row(s) -> {out}")
    heads = {"not_emitted": "not emitted", "needs_source": "needs a source",
             "cosmetic_gated": "cosmetic gated as a value", "duplicate": "dropped duplicate",
             "superseded": "superseded (not emitted)"}
    for bucket, head in heads.items():
        rows = [(p, t) for b, p, t in reports if b == bucket]
        if rows:
            print(f"\n{head} ({len(rows)}):")
            for p, t in rows:
                print(f"  {p['batch']} · {p['column'] or 'new row'} · row_id {p['row_id']}: {t}")
    if n:
        print("\nnext (QC SOP, nothing new):")
        if any(c["field"] == "Name" and not c.get("preserve_ref") for corr in fix["corrections"] for c in corr["cells"]):
            print(f"  python scripts/other_names.py --batch {out}")
        print(f"  python scripts/build_workbook.py --mode fix --fix {out} --out batches/<date>_<HHMMET>_fix_review_suggestions/")
        print("  python scripts/recalc.py batches/<dir>/lng_carrier_fix.xlsx")
        print("  python scripts/batch_digest.py --batch batches/<dir>   # a ref the gate drops = the value needs a source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
