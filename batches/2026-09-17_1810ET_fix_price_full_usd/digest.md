# Batch digest — 2026-09-17_1810ET_fix_price_full_usd

**Mode:** fix  ·  **Proposals:** 58 (auto-safe 58, needs-decision 0)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: Price ×29, Price currency ×29

These 58 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

_(none)_

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_1810ET_fix_price_full_usd`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_1810ET_fix_price_full_usd` to confirm everything landed.
