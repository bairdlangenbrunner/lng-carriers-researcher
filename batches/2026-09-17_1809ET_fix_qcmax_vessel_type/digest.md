# Batch digest — 2026-09-17_1809ET_fix_qcmax_vessel_type

**Mode:** fix  ·  **Proposals:** 24 (auto-safe 24, needs-decision 0)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: Vessel type ×24

These 24 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

_(none)_

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_1809ET_fix_qcmax_vessel_type`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_1809ET_fix_qcmax_vessel_type` to confirm everything landed.
