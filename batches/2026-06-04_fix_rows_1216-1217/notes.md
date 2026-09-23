# Fix — rows 1216/1217 structural correction (Hull CMHI-282-07/08)

**Batch:** `2026-06-04_fix_rows_1216-1217`
**Trigger:** user flagged these two Celsius Shipping / China Merchants (CMHI) hulls —
"data cells look wrong."
**Rows:** 1216 (Hull CMHI-282-07), 1217 (Hull CMHI-282-08).

## What was wrong

Column-offset corruption from a copy/paste, not a research error — every value was present
but landed in the wrong column. Two distinct offsets: a stray Capacity/Cargo duplicate pasted
into the Yard-location columns (cols 22–26), and the whole tail block (Vessel type → Contract
date) shifted +5 columns right. See `corrections.md` for the full before/after tables.

Flagged for the reviewer, not resolved here: Capacity `176400` (CSB/Deltamarin 98%-fill figure)
vs `180000` (nominal, matching siblings 251–256) — left as the in-place value, reviewer's call.
Resolved in the follow-up batch, `2026-06-05_1323ET_fix_rows_1216-1217_capacity/` (also folds
in the structural fix, since neither had been applied yet).

## Files

`corrected_rows.csv` — the two rows in exact backend column order, ready to paste over
1216/1217. `corrections.md` — the full defect writeup and flags. `lng_carrier_fix_rows_1216-1217.xlsx`
— the candidate workbook.

## Apply status

**Unrecorded.** This predates the apply-artifact pipeline (`decisions.csv` / `apply.json` /
`verify_report.csv`) — there is no record in this repo of whether `corrected_rows.csv` was ever
pasted into the live sheet. The follow-up batch's own notes describe applying *its* combined
output (structural + capacity) as still pending as of 2026-06-05, so treat both as unconfirmed
until a fresh pull is checked against the corrected values.
