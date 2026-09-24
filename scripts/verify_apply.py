"""
Close the loop: after you apply a batch, confirm the backend actually matches it.

Re-pull the backend (or use a fresh pull), then diff it against the batch's
`apply.json` (the canonical record of what was accepted). Every accepted cell must
now hold the accepted value; every accepted discovery row must now exist. Anything
missing or mismatched means the apply slipped — exactly the failure mode that left
rows 1216/1217 corrupted for weeks. Also runs the qc_backend content checks over the
touched rows so a paste-offset introduced during apply is caught immediately.

    python scripts/verify_apply.py --batch batches/<dir> [--pull] [--strict]

--pull re-runs pull_backend.py first; otherwise it uses the existing work/backend.csv
(re-pull yourself after applying). --strict exits non-zero if anything didn't land.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import dedupe_check
import qc_backend
from apply_batch import _load_backend, sheet_row_map
from backend_io import load_backend
from paths import backend_csv_path, repo_root


def _norm(s):
    return " ".join((s or "").split()).strip()


def _same(a, b):
    """Equal after whitespace normalisation, or as numbers — the sheet renders a Price
    of 165000000 as `165000000.00` (same rule as review_data._same)."""
    a, b = _norm(a), _norm(b)
    if a == b:
        return True
    try:
        return float(a.replace(",", "")) == float(b.replace(",", ""))
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--pull", action="store_true", help="run pull_backend.py first")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything didn't land")
    args = ap.parse_args()
    batch_dir = Path(args.batch)

    apply_path = batch_dir / "apply.json"
    if not apply_path.exists():
        sys.exit(f"error: {apply_path} not found — run `python scripts/apply_batch.py "
                 f"--batch {batch_dir}` first")
    apply_doc = json.loads(apply_path.read_text())

    if args.pull:
        subprocess.run([sys.executable, str(repo_root() / "scripts" / "pull_backend.py")],
                       check=True)

    header, row_by_id, colmap = _load_backend(args.backend)
    H = {h: i for i, h in enumerate(header)}
    # Keys are UUIDs (legacy "original order" ids resolve); report the LIVE tab row to humans.
    srmap = sheet_row_map(args.backend, colmap)
    def sr(rid):
        return srmap.get(str(rid), "?")

    landed, mismatch, missing = [], [], []
    for cell in apply_doc.get("accepted_cells", []):
        rid, col, want = str(cell["row_id"]), cell["column"], cell["value"]
        row = row_by_id.get(rid)
        idx = H.get(col)
        got = row[idx] if row is not None and idx is not None and len(row) > idx else None
        if not _norm(want):
            # a clearing (fix-mode empty new_value): landed when the cell is blank
            (landed.append((rid, col)) if row is not None and not _norm(got or "")
             else mismatch.append((rid, col, want, got or "")))
        elif got is None or not _norm(got):
            missing.append((rid, col, want, got or ""))
        elif _same(got, want):
            landed.append((rid, col))
        else:
            mismatch.append((rid, col, want, got))

    # discovery: each accepted new row should now exist (match by IMO, Name or Hull number —
    # IMO survives a placeholder restyle, and every row counts, a stub with no row_id included;
    # the row must hold every column the candidate fills — a pasted stub is still missing)
    new_missing, new_present, new_row_ids = [], [], set()
    rid_i = colmap["row_id"]
    all_rows = load_backend(args.backend).data
    for nr in apply_doc.get("accepted_new_rows", []):
        rd = nr.get("row_data", {})
        keys = {h: rd.get(h, "") for h in ("IMO number", "Name", "Hull number") if rd.get(h)}
        if not keys:
            new_present.append(("(unverifiable — no IMO/Name/Hull)", nr.get("cluster_id", "")))
            continue
        filled = [h for h, v in rd.items() if _norm(v) and h in H]
        match = next(
            (r for r in all_rows
             if any(_norm(r[H[h]]) == _norm(v) for h, v in keys.items()
                    if h in H and len(r) > H[h])
             and all(len(r) > H[h] and _norm(r[H[h]]) for h in filled)),   # a stub is not the row
            None)
        if match is not None:
            new_present.append((nr.get("cluster_id", ""), keys))
            if len(match) > rid_i and match[rid_i]:
                new_row_ids.add(str(match[rid_i]))
        else:
            new_missing.append((nr.get("cluster_id", ""), keys))

    # qc the touched rows so an apply-time offset is caught now
    be = load_backend(args.backend)
    touched_ids = {be.canonical_key(c["row_id"]) for c in apply_doc.get("accepted_cells", [])}
    findings, _, _ = qc_backend.scan(
        header, list(row_by_id.values()), rid_i,
        row_filter=(lambda rid: rid in touched_ids) if touched_ids else None)
    qc_hi_med = [f for f in findings if f["severity"] in ("HIGH", "MED")]

    # dedupe sweep (advisory): did anything this batch touched/added duplicate an
    # existing vessel? Focus on the touched + newly-landed rows (Apply SOP §dedupe-sweep).
    focus = touched_ids | new_row_ids
    dupe_groups = dedupe_check.scan_duplicates(
        header, list(row_by_id.values()), colmap, focus_rows=focus or None,
        sheet_rows=srmap)
    dupe_hi_med = [g for g in dupe_groups if g["severity"] in ("HIGH", "MED")]
    if dupe_groups:
        dedupe_check.write_report(dupe_groups, batch_dir / "dedupe_report.csv")

    # report
    rep = batch_dir / "verify_report.csv"
    import csv
    with open(rep, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "sheet_row", "row_id", "column", "accepted_value", "backend_value"])
        for rid, col in landed:
            w.writerow(["landed", sr(rid), rid, col, "", ""])
        for rid, col, want, got in mismatch:
            w.writerow(["MISMATCH", sr(rid), rid, col, want, got])
        for rid, col, want, got in missing:
            w.writerow(["MISSING", sr(rid), rid, col, want, got])

    print(f"verify_apply {batch_dir.name}", file=sys.stderr)
    print(f"  cells: {len(landed)} landed, {len(mismatch)} mismatch, {len(missing)} missing",
          file=sys.stderr)
    if apply_doc.get("accepted_new_rows"):
        print(f"  new rows: {len(new_present)} present, {len(new_missing)} missing",
              file=sys.stderr)
    if mismatch:
        print("  MISMATCH (backend differs from accepted):", file=sys.stderr)
        for rid, col, want, got in mismatch[:10]:
            print(f"    sheet row {sr(rid)} (id {rid}) · {col}: accepted {want!r} "
                  f"but backend has {got!r}", file=sys.stderr)
    if missing:
        print("  MISSING (accepted value not in backend):", file=sys.stderr)
        for rid, col, want, got in missing[:10]:
            print(f"    sheet row {sr(rid)} (id {rid}) · {col}: expected {want!r}",
                  file=sys.stderr)
    if new_missing:
        print(f"  NEW ROWS not found: {[c for c, _ in new_missing]}", file=sys.stderr)
    if qc_hi_med:
        print(f"  ⚠ qc_backend flags {len(qc_hi_med)} HIGH/MED issue(s) in touched rows "
              "— run scripts/qc_backend.py for detail", file=sys.stderr)
    if dupe_hi_med:
        print(f"  ⚠ dedupe_check flags {len(dupe_hi_med)} possible duplicate group(s) "
              f"involving this batch's rows:", file=sys.stderr)
        for g in dupe_hi_med[:10]:
            print(f"      [{g['severity']}] {dedupe_check._fmt_rows(g)} · {g['key']}",
                  file=sys.stderr)
        print(f"      see {batch_dir / 'dedupe_report.csv'}", file=sys.stderr)
    print(f"  report: {rep}", file=sys.stderr)

    # Duplicates are judgment calls (placeholder vs sister ship), so they're
    # advisory — surfaced loudly but never fail the apply by themselves.
    problems = bool(mismatch or missing or new_missing or qc_hi_med)
    if not problems:
        print("  ✓ everything accepted landed cleanly", file=sys.stderr)
    else:
        print(f"  ✗ PROBLEMS: {len(mismatch)} mismatch, {len(missing)} missing, "
              f"{len(new_missing)} new-row missing, {len(qc_hi_med)} qc HIGH/MED "
              f"— see {rep}" + ("" if args.strict else " (exit 0 without --strict)"),
              file=sys.stderr)
    if args.strict and problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
