# Batch digest — 2026-09-17_0505ET_ref_fill_rule_f

**Mode:** ref_fill  ·  **Proposals:** 8 (auto-safe 0, needs-decision 8)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

_(none)_

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **row 415** · Capacity [ref]: `https://www.shipvault.com/ships/73086` (Y) — live row 6: Rule F fill - Capacity = '126750' corroborated by the shipvault unit record
- **row 663** · Capacity [ref]: `https://www.shipvault.com/ships/73085` (Y) — live row 7: Rule F fill - Capacity = '126750' corroborated by the shipvault unit record
- **row 969** · Capacity [ref]: `https://www.shipvault.com/ships/113754` (Y) — live row 61: Rule F fill - Capacity = '135000' corroborated by the shipvault unit record
- **row 1044** · Capacity [ref]: `https://www.shipvault.com/ships/373877` (Y) — live row 487: Rule F fill - Capacity = '174000' corroborated by the shipvault unit record
- **row 1045** · Capacity [ref]: `https://www.shipvault.com/ships/373876` (Y) — live row 488: Rule F fill - Capacity = '174000' corroborated by the shipvault unit record
- **row 121** · Hull number [ref]: `https://www.shipvault.com/ships/450944` (Y) — live row 771: Rule F fill - Hull number = 'Hull 2651 (SHI)' corroborated by the shipvault unit record
- **row 226** · Hull number [ref]: `https://www.shipvault.com/ships/448545` (Y) — live row 775: Rule F fill - Hull number = 'Hull 8102 (HDHHI)' corroborated by the shipvault unit record
- **row 230** · Hull number [ref]: `https://www.shipvault.com/ships/461187` (Y) — live row 776: Rule F fill - Hull number = 'Hull 8181 (HDHHI)' corroborated by the shipvault unit record

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_0505ET_ref_fill_rule_f`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_0505ET_ref_fill_rule_f` to confirm everything landed.
