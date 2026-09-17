# Batch digest — 2026-09-17_0458ET_fix_delivery_confirmed

**Mode:** fix  ·  **Proposals:** 3 (auto-safe 0, needs-decision 3)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

_(none)_

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **row 186** · Status: `active` (Y) — LNG Prime (25-Aug-2026): 'Knutsen's unit Knutsen LNG France announced the delivery of Al Nigyan in a social media post last week' -- the 174,000-cbm LNG carrier is the eighth of ten HD Hyundai Heavy Industries-built vessels Knutsen owns and charters to QatarEnergy; matches backend_delivery_year 2026.
- **row 186** · Name: `Al Nigyan` (Y) — named at delivery; replaces hull placeholder
- **row 318** · Status: `active` (Y) — LNG Prime (20-Aug-2026): 'Chinese private shipyard Yangzijiang Shipbuilding has delivered its first 175,000-cbm liquefied natural gas (LNG) carrier, Yangze LNG 01'; a follow-up LNG Prime piece (10-Sep-2026) notes it has since completed its maiden voyage. Matches backend's 2026 delivery-year estimate; url_verifier PASSED for --value active, --value 2026, and --value 'Yangze LNG 01'.

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_0458ET_fix_delivery_confirmed`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_0458ET_fix_delivery_confirmed` to confirm everything landed.
