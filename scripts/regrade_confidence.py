"""
Re-grade a batch's held lines under the §5 rule of RF rev 28 (Baird directive 2026-09-22).

Every held line was labelled by the OLD §5 ladder, where a single trade-press page
carrying the value was only Yellow. The rule now is: a ref that survives the §3.8c gate
on a **live** page, stating the value for this vessel, is Green. This walks the holds,
re-runs the gate live, and promotes the ones that clear it.

What it will and will not touch:

  - Only lines whose decision is still `hold`. A line a person decided is theirs — any
    `review_log.jsonl` record that is not a machine's (the backend sync, an earlier
    regrade) takes the line out of scope, whatever it says.
  - Only ever `hold -> accept`, and only on a G. A line that now grades Y or R stays
    held and is reported; nothing is ever demoted or rejected here.
  - The record it appends to `review_log.jsonl` says what it is (`reviewer: "§5 regrade"`).
    It is NOT a reviewer's click: `store.reviewed()` still reads the line as undecided,
    so the app shows it as an un-clicked accept exactly like a batch's own Green pre-fill.

    python scripts/regrade_confidence.py --batch batches/<dir> [<dir> ...] [--apply]
    python scripts/regrade_confidence.py --all [--apply]

Dry run by default: it writes `work/regrade_report.csv` and changes nothing. `--apply`
writes the new grade into the batch's source JSON + `decisions.csv` and appends the log.
Gate results are cached in `work/regrade_gate.jsonl`, so an interrupted run resumes cheap.
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import confidence
from apply_batch import _detect, _items_and_conflicts, sheet_row_map
from backend_io import BackendNotPulled, load_backend
from igu_refs import corroborates_cell
from paths import backend_csv_path, work_dir
from url_verifier import citable_forms

ET = ZoneInfo("America/New_York")
REVIEWER = "§5 regrade"
# Reviewers that are machines, not people: a record from one of these leaves the line
# in scope here, and leaves it undecided in the review app. Mirrors
# review_app/store.py MACHINE_REVIEWERS (scripts/ never imports review_app; a test pins
# the two together).
MACHINE_REVIEWERS = {"backend sync", REVIEWER}


def _log_path():
    return work_dir() / "regrade_gate.jsonl"


def _load_cache():
    cache, p = {}, _log_path()
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            cache[(r["url"], r["value"], r["field"], r["imo"])] = (r["ok"], r["reason"])
    return cache


def gate(url, value, field, imo, cache):
    """(ok, reason) from the §3.8c gate, cached across runs."""
    key = (url, str(value), field, imo)
    if key in cache:
        return cache[key]
    ok, reason = corroborates_cell(url, value, field, imo)
    cache[key] = (ok, reason)
    with open(_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "value": str(value), "field": field, "imo": imo,
                            "ok": ok, "reason": reason}, ensure_ascii=False) + "\n")
    return ok, reason


def person_decided(batch_dir):
    """Proposal ids whose latest review_log record is a person's — out of scope."""
    p, out = batch_dir / "review_log.jsonl", {}
    if not p.exists():
        return set()
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = r.get("key", "")
        if "::" in key:
            out[key.split("::", 1)[1]] = r.get("reviewer", "")
    return {i for i, rev in out.items() if rev not in MACHINE_REVIEWERS}


def payload_cells(mode, payload):
    """proposal id -> the payload dict that carries its `confidence` (so a regrade
    survives the next `apply_batch.py` run, which rebuilds decisions.csv from here)."""
    out = {}
    if mode == "data_fill":
        for f in payload.get("fills", []):
            out[f"{f['row_id']}|{f.get('field', '')}"] = f
    elif mode == "fix":
        for corr in payload.get("corrections", []):
            for c in corr.get("cells", []):
                out[f"{corr['row_id']}|{c.get('field', '')}"] = c
    elif mode == "ref_fill":
        for f in payload.get("candidate_data_fills", []):
            out[f"{f.get('row_id', '')}|{f.get('field', '')}"] = f
    return out


def regrade_batch(batch_dir, backend, imo_by_id, srm, cache, rows):
    """Grade every held line of one batch. Returns {id: (grade, why)} for the promotions."""
    mode, payload = _detect(batch_dir)
    items, _ = _items_and_conflicts(mode, payload, backend.header, backend.colmap)
    dec_path = batch_dir / "decisions.csv"
    if not dec_path.exists():
        print(f"  {batch_dir.name}: no decisions.csv — skipped", file=sys.stderr)
        return {}
    with open(dec_path, encoding="utf-8", newline="") as f:
        decisions = {r["id"]: (r.get("decision") or "").strip().lower()
                     for r in csv.DictReader(f)}
    theirs = person_decided(batch_dir)

    promoted = {}
    for it in items:
        if decisions.get(it["id"]) != "hold" or it["id"] in theirs:
            continue
        if it["kind"] == "new_row":
            continue                      # a discovery cluster is a whole row, decided by hand
        rid, field = it["row_id"], it["column"]
        value = it.get("gate_value") or it.get("value") or ""
        imo = imo_by_id.get(rid, "")
        urls = [u for u in citable_forms(
            [x.strip() for x in str(it.get("ref_value", "")).split(",") if x.strip()])]
        # ref-fill [ref] lines carry no value of their own; the gate has nothing to hold
        # them to, so they stay where the batch put them.
        if it["kind"] == "ref" or it.get("preserve_ref") or not value:
            continue

        passes, verdicts = [], []
        for u in urls:
            ok, reason = gate(u, value, field, imo, cache)
            verdicts.append(f"{'PASS' if ok else 'FAIL'} {u} ({reason})")
            if ok:
                passes.append((u, reason))

        caps = []
        if it.get("derived_from"):
            caps.append(confidence.CAP_DERIVED)
        if field == "Delivery year" and confidence.rolls_forward(value, it.get("former_year")) \
                and len(confidence.live_hosts(passes)) < 2:
            caps.append(confidence.CAP_ROLL_FORWARD)
        if it.get("cap_reason"):
            caps.append(it["cap_reason"])
        caps.append(confidence.note_cap(it.get("note")))
        conf, why = confidence.grade(passes, field=field, value=value, caps=caps)

        rows.append({"batch": batch_dir.name, "id": it["id"], "row_id": rid,
                     "live_row": srm.get(rid, ""), "column": field, "value": value,
                     "was": it.get("confidence", ""), "now": conf,
                     "promoted": "yes" if conf == confidence.GREEN else "",
                     "why": why, "refs": " | ".join(verdicts)})
        if conf == confidence.GREEN:
            promoted[it["id"]] = (conf, why)

    return promoted


def write_back(batch_dir, promoted):
    """Stamp the new grade into the source JSON + decisions.csv and log the regrade."""
    mode, payload = _detect(batch_dir)
    cells = payload_cells(mode, payload)
    for pid, (conf, why) in promoted.items():
        cell = cells.get(pid)
        if cell is not None:
            cell["confidence"], cell["confidence_why"] = conf, why
    src = next(p for p in (batch_dir / f"{n}.json" for n in
                           ("data_fill", "candidates", "citations", "fix")) if p.exists())
    src.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    dec_path = batch_dir / "decisions.csv"
    with open(dec_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields, out = reader.fieldnames, list(reader)
    for r in out:
        if r["id"] in promoted:
            r["decision"] = "accept"
            r["confidence"] = promoted[r["id"]][0]
    with open(dec_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    ts = datetime.now(ET).isoformat(timespec="seconds")
    with open(batch_dir / "review_log.jsonl", "a", encoding="utf-8") as f:
        for pid, (conf, why) in promoted.items():
            f.write(json.dumps({"key": f"{batch_dir.name}::{pid}", "decision": "accept",
                                "suggested_value": "", "suggest_kind": "", "note": why,
                                "via": "regrade:§5 rev 28", "reviewer": REVIEWER,
                                "ts": ts}, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", action="append", default=[], help="batch directory (repeatable)")
    ap.add_argument("--all", action="store_true", help="every batches/* dir with a decisions.csv")
    ap.add_argument("--apply", action="store_true",
                    help="write the promotions (default: dry run + report only)")
    ap.add_argument("--backend", default=str(backend_csv_path()))
    args = ap.parse_args()

    dirs = [Path(b) for b in args.batch]
    if args.all:
        dirs += sorted(p.parent for p in Path("batches").glob("*/decisions.csv"))
    dirs = sorted({d.resolve() for d in dirs})
    if not dirs:
        sys.exit("error: pass --batch <dir> (repeatable) or --all")

    try:
        backend = load_backend(args.backend)
    except (BackendNotPulled, FileNotFoundError):
        sys.exit("error: no fresh backend pull — run `python scripts/pull_backend.py` first")
    i = backend.header_index.get("IMO number")
    imo_by_id = {rid: backend.cell(r, i).strip() for rid, r in backend.row_by_id().items()} \
        if i is not None else {}
    srm = sheet_row_map(args.backend)

    cache, rows, total = _load_cache(), [], 0
    for d in dirs:
        promoted = regrade_batch(d, backend, imo_by_id, srm, cache, rows)
        held = sum(1 for r in rows if r["batch"] == d.name)
        print(f"  {d.name}: {held} held line(s) graded, {len(promoted)} -> G", file=sys.stderr)
        if promoted and args.apply:
            write_back(d, promoted)
        total += len(promoted)

    out = work_dir() / "regrade_report.csv"
    cols = ["batch", "id", "row_id", "live_row", "column", "value", "was", "now",
            "promoted", "why", "refs"]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    still = len(rows) - total
    print(f"\n{len(rows)} held line(s) re-graded: {total} -> G (accept), {still} stay held.\n"
          f"report: {out}" + ("" if args.apply else "\n(dry run — nothing written; re-run with --apply)"),
          file=sys.stderr)


if __name__ == "__main__":
    main()
