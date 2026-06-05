"""
One-screen triage digest for a batch — so review time scales with the hard cases.

Reading a batch today means opening the xlsx and scanning every colored cell. This
splits a batch into the two things a reviewer actually cares about:

  - AUTO-SAFE   Green / derivable proposals — accept in bulk.
  - NEEDS A DECISION   Yellow / Red proposals, conflicts, `unknown`s — the short
                       list that actually needs a human.

Writes <batch>/digest.md (and prints a summary). Pure read — never edits the backend.

    python scripts/batch_digest.py --batch batches/<dir> [--backend work/backend.csv]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

from paths import backend_csv_path
from apply_batch import _detect, _load_backend, _items_and_conflicts


def _line(it):
    who = f"row {it['row_id']}" if it["row_id"] else f"cluster {it['cluster_id']}"
    val = it["value"] or it["ref_value"] or (it.get("cluster_label", ""))
    col = f" · {it['column']}" if it["column"] else ""
    note = f" — {it['note']}" if it["note"] else ""
    return f"- **{who}**{col}: `{val}` ({it['confidence']}){note}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--backend", default=str(backend_csv_path()))
    args = ap.parse_args()
    batch_dir = Path(args.batch)

    mode, payload = _detect(batch_dir)
    header, _row_by_id, colmap = _load_backend(args.backend)
    items, conflicts = _items_and_conflicts(mode, payload, header, colmap)

    auto = [it for it in items if it["derivable"] or it["confidence"] == "G"]
    decide = [it for it in items if not (it["derivable"] or it["confidence"] == "G")]
    blanks = payload.get("documented_blanks", [])

    out = []
    out.append(f"# Batch digest — {batch_dir.name}")
    out.append(f"\n**Mode:** {mode}  ·  **Proposals:** {len(items)} "
               f"(auto-safe {len(auto)}, needs-decision {len(decide)})  ·  "
               f"**Conflicts:** {len(conflicts)}  ·  **Documented blanks:** {len(blanks)}\n")

    out.append("## ✅ Auto-safe — accept in bulk (Green / derivable)")
    if auto:
        by_col = Counter(it["column"] or "(new vessel)" for it in auto)
        out.append("\nBy field: " + ", ".join(f"{k} ×{v}" for k, v in by_col.most_common()))
        out.append(f"\nThese {len(auto)} are default-`accept` in `decisions.csv`. "
                   "Skim or trust; nothing here needs a per-item call.\n")
    else:
        out.append("\n_(none)_\n")

    out.append("## ⚠️ Needs a decision (Yellow / Red / unknown)")
    if decide:
        out.append("")
        out.extend(_line(it) for it in decide)
        out.append("\nThese are default-`hold`. Flip to `accept`/`reject` in "
                   "`decisions.csv`, then re-run `apply_batch.py`.\n")
    else:
        out.append("\n_(none)_\n")

    out.append("## ⛔ Conflicts — research disagrees with a filled backend value")
    if conflicts:
        out.append("\nNot auto-applied (data-fill is additive to blanks only). Decide each in "
                   "`conflicts.csv`.\n")
        for c in conflicts:
            who = f"row {c['row_id']}" if c.get("row_id") else "—"
            out.append(f"- **{who}** {c.get('column','')}: backend `{c.get('backend_value','')}` "
                       f"vs research `{c.get('proposed_value','')}` — {c.get('recommendation','')}")
        out.append("")
    else:
        out.append("\n_(none)_\n")

    if blanks:
        out.append(f"## 📭 Documented blanks ({len(blanks)})")
        out.append("\nResearched, no sourceable value — honest negatives, **no action needed**. "
                   "See QA_review for the search recipes.\n")

    out.append("## Next steps")
    out.append("\n1. Edit `decisions.csv` (flip any holds).  "
               "2. `python scripts/apply_batch.py --batch " + str(batch_dir) + "`.  "
               "3. Apply: paste `apply_rows.csv` rows over the matching backend rows, "
               "**or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  "
               "4. `python scripts/verify_apply.py --batch " + str(batch_dir) + "` to confirm "
               "everything landed.\n")

    (batch_dir / "digest.md").write_text("\n".join(out))
    print(f"batch_digest [{mode}] {batch_dir.name}: {len(auto)} auto-safe, "
          f"{len(decide)} need a decision, {len(conflicts)} conflicts "
          f"-> {batch_dir / 'digest.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
