# Fix — rows 1216/1217 structural + capacity (176,400 → 180,000), gated refs

**Batch:** `2026-06-05_1323ET_fix_rows_1216-1217_capacity`
**Mode:** `build_workbook.py --mode fix` (new) + value↔ref corroboration gate
**Rows:** 1216 (Hull CMHI-282-07), 1217 (Hull CMHI-282-08) — CMHI Haimen, Celsius/Clearlake quartet
**Output:** `lng_carrier_fix.xlsx` (paste both full rows over the matching backend rows)

## What was wrong

Two distinct problems were live in the backend on these two rows:

1. **Structural column-offset corruption** (carried over from the original
   data-fill incorporation): a stray duplicated yard-location pair in cols 25–26
   and a +5 shift in the tail (cols 37–47). A reviewed correct layout already
   existed at `batches/2026-06-04_fix_rows_1216-1217/corrected_rows.csv`, but it
   had **not been applied to the live backend** — so the corruption was still
   present.

2. **Value↔ref conflict on Capacity.** The cell read **176,400** while citing a
   Deltamarin ref whose headline figure is **180,000**. 176,400 is Deltamarin's
   *98%-fill* figure ("180,000 cbm, or 176,400 cbm at 98%"); the tracker carries
   the **nominal** volume. So the cell value and one of its refs disagreed.

## Root cause (how the conflict got in)

The conflict entered through a **hand-built fix batch**, not through the gated
pipeline. When the structural correction was drafted, the Capacity value was
preserved in place (176,400) while a ref gathered for the *nominal* 180,000
figure (Deltamarin) was kept on the cell. It was flagged only as a soft
"not-a-conflict / your call" note in prose — easy to miss, and exactly the kind
of soft flag the user does not want. The data-fill `merge_fills.py` gate would
have caught this, but a hand-edited CSV bypassed it.

Ground truth (re-confirmed this batch):
- LNG Prime 69940 — nominal **180,000 cbm** (public lead).
- offshore-energy.biz — nominal **180,000 cbm** (public body).
- Deltamarin — **180,000 cbm** nominal, 176,400 at 98% (browser-confirmed; the
  page soft-blocks curl at HTTP 000, so it's retained under §3.8a with out-of-band
  content confirmation, `soft: true`).
- Siblings 251–256 (same Celsius quartet/order) also carry 180,000.

CSB lists 176,400 (the 98% figure) and was **dropped** from the Capacity `[ref]`.

## The fix

- Built on the reviewed `corrected_rows.csv` via `--base` (remapped to the live
  `backend_header` *by header name*, so stray/trailing columns clear), so the
  output rows are structurally correct **and** carry the capacity correction.
- **Capacity → 180000** (nominal), confidence **G**.
- **Capacity [ref]** → LNG Prime 69940, offshore-energy.biz, Deltamarin
  (`soft:true`, §3.8a). CSB chinashipbuild URL dropped (`drop_refs`).
- The §3.8c gate ran on every ref: live non-corroborating CSB URLs were dropped
  (2 dropped), the soft-blocked Deltamarin URL retained under §3.8a.

## Verification

- `recalc.py` → **zero formula errors.**
- Both output rows spot-checked: Capacity = 180000; Capacity [ref] =
  LNG Prime / offshore-energy / Deltamarin (CSB gone); structural cells correctly
  placed (Vessel type = conventional, Propulsion type = ME-GA, Delivery year = 2028,
  [Original source] = "Claude - agentic workflow new discovery - May 2026",
  Operator/charterer = Clearlake Shipping, Contract date = 01-May-2024); the
  cols 25–26 stray pair and the +5 tail shift are gone.

## Prevention (process + code changes shipped with this batch)

1. **Value↔ref corroboration gate (hard-block), [ref]-Fill SOP §3.8c (rev 18).**
   A `[ref]` may only be cited on a cell whose value its live page actually
   contains. A live page stating a *different* figure fails the gate — the ref is
   dropped and the conflict logged for human review, never kept with a soft
   footnote. Includes the **dual-figure rule** (nominal vs 98%-fill capacity →
   carry the nominal).
2. **Code:** `corroborates()` + `value_variants()` in `scripts/url_verifier.py`
   (format-aware: 180000 ↔ "180,000", 250000000 ↔ "$250 million"); wired into
   `scripts/merge_fills.py` (data-fill central gate) and the new
   `build_workbook.py --mode fix`. CLI spot-check:
   `python scripts/url_verifier.py --value <value> <url>`.
3. **Correction batches go through `--mode fix` + the gate, never hand-edited CSV.**
   That's the bypass that let this conflict through.
4. **Data-fill SOP rev 2** points at §3.8c so the gate is documented on both
   workflows; CLAUDE.md scripts table now lists the `fix` mode.

## Action for the user

Paste both full rows from `lng_carrier_fix.xlsx` over backend rows 1216/1217
(offset-proof: full-row replacement). This applies the structural correction
**and** the capacity correction in one move. After applying, a `verify_apply` /
`qc_backend` pass on the touched rows will confirm the offset is gone.
