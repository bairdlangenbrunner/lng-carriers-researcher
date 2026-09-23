# Batch digest — 2026-09-22_2208ET_fix_shipvault_hulls

**Mode:** fix  ·  **Proposals:** 14 (auto-safe 8, needs-decision 6)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: Name ×4, Hull number ×4

These 8 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **row 315** · Delivery year: `2029` (Y) — unit 490165 gives built 2029-01; the backend carries 2028
- **row 315** · Previous delivery year(s): `2028` (Y) — former Delivery year 2028 (now proposed 2029) — decide with the Delivery year line; https://www.shipvault.com/ships/490165: page does not contain value '2028'; no ref prints the former year — [ref] left blank
- **row 315** · Delivery delayed: `yes` (Y) — derived: Delivery year 2028 -> 2029 — decide with the Delivery year line
- **row 316** · Delivery year: `2029` (Y) — unit 490166 gives built 2029-02; the backend carries 2028
- **row 316** · Previous delivery year(s): `2028` (Y) — former Delivery year 2028 (now proposed 2029) — decide with the Delivery year line; https://www.shipvault.com/ships/490166: page does not contain value '2028'; no ref prints the former year — [ref] left blank
- **row 316** · Delivery delayed: `yes` (Y) — derived: Delivery year 2028 -> 2029 — decide with the Delivery year line

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-22_2208ET_fix_shipvault_hulls`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-22_2208ET_fix_shipvault_hulls` to confirm everything landed.
