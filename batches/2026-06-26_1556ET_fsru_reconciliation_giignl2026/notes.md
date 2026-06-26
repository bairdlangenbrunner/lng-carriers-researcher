# FSRU reconciliation — GIIGNL 2026 fleet table vs backend

**Date:** 2026-06-26 15:56 ET
**Mode:** `fsru` reconciliation (new workflow — see `docs/sops/fsru_reconciliation.md`, FR rev 1)
**SOP:** FR rev 1 (issued in this batch); inherits [ref]-Fill §3.8 (URL gate), §4 (additive/never-edit), and the Apply SOP for promotion.

## Scope (Phase A of the FSRU plan)

This is **Phase A** — the gap analysis: *how complete is the tracker's FSRU coverage vs the
most complete public in-service roster?* It is **not** the comprehensive global FSRU build
(Phase B, later) — that triangulates on-order/proposed/idle units and is out of scope here.

- **FSRUs only.** FSUs (storage-only) are out of scope and logged as a known-exclusions list.
- **GIIGNL 2026 report only** ("FSRU FLEET AT THE END OF 2025"); prior years not blended.
- **Inputs:**
  - `work/backend.csv` — pulled fresh today (mandatory first step); colmap re-derived.
  - `work/giignl_fsru_fleet.json` — extracted by the sibling repo's production parser
    `../lng-terminals-researcher/scripts/giignl_fsru_fleet.py` (not rebuilt). Copied into this
    batch dir alongside `fsru_reconcile.json` for reproducibility.

## Headline result

**The tracker's coverage of GIIGNL's in-service FSRU fleet is essentially complete.** Every
full-size in-service FSRU in GIIGNL is already in the backend (a few mistyped or misnamed). The
only genuine absences are four small / power-barge units, all flagged for FSRU-vs-small-scale
human review rather than asserted as FSRUs to add. Well under the >5-cluster escalation
threshold — no systematic gap.

| Bucket | Count | Meaning |
|---|---|---|
| GIIGNL in-service fleet | 54 | the comparison roster |
| Backend FSRUs (`Vessel type`=FSRU) | 49 | tracker's FSRU subset |
| **Matched** (already FSRU in backend) | **47** | name/ex-name hit on an FSRU-typed row |
| **Reclassify** (present, typed non-FSRU) | **2** | in the tracker but mis-typed — a typing finding, not a gap |
| **Manual pairing** (name defect / no name match) | **1** | capacity+owner pair; human confirms |
| **Candidates to add** (genuine gaps) | **4** | all small-scale → FSRU-vs-small-scale review |
| Backend-only FSRUs (absent from GIIGNL) | 1 | expected (GIIGNL is in-service only) |
| FSU exclusions (out of scope) | 10 | logged so they don't resurface as gaps |
| GIIGNL orderbook (future) | 4 | Phase B reference, not added here |

## Bucket detail

**Matched (47).** Capacity (the join corroborator) agreed on **all 47** pairs — zero capacity
disagreements. Other diffs are minor: **1 delivery-year** (FSRU Toscana, GIIGNL built 2003 vs
backend delivery 2004), **6 owner non-overlaps** (role/stylization differences, not vessel
mismatches), and **34 builder diffs** — all expected/informational (GIIGNL lists the conversion
yard for converted units; the backend keeps the original builder, so builder is NOT used to
confirm/reject a match). Spot-checks confirmed the ex-name join works: GIIGNL "Italis LNG
(ex Golar Tundra)" → backend "Golar Tundra" (live row 648); GIIGNL "Saros (ex Vasant 1)" →
backend "Vasant 1" (live row 1089) — both would be false gaps without `ex_names`.

**Reclassify (2).** Both are in the tracker but typed `conventional`, not `FSRU`:
- **Alexandroupolis** (live row 376) — capacity 153,000 = 153,000, solid; GIIGNL lists it as a
  deployed FSRU. Recommend reclassifying the backend `Vessel type`.
- **KARMOL LNGT Powership Americas** / backend **"LNGT Americas"** (live row 806) — capacity
  agrees, but GIIGNL flags it `unassigned` / candidate conversion. Human should confirm the
  conversion status before changing the type.

**Manual pairing (1).** **GIIGNL "Höegh Esperanza"** ↔ backend **"Hoegh"** (live row 676). No
name match, but capacity (170k) + owner overlap (backend owner cell "Esperanza Hoegh") pair
them. This is a **backend Name defect** — the backend row is named just "Hoegh". Confirm the
pairing and fix the backend Name to "Höegh Esperanza". (This is exactly the case the
mandatory owner-overlap guard is designed to surface.)

**Candidates to add (4) — all small-scale, all YELLOW, `Vessel type` left blank:**
| GIIGNL name | storage m³ | note |
|---|---|---|
| EDN 1 | 14,000 | power-barge / small-scale; CCS "Other" |
| Eemshaven LNG | 25,000 | small-scale regas |
| Karunia Dewata | 26,000 | small-scale |
| Torman | 28,000 | small-scale; relates to backend FSU "Torman II" (row 1076) — pending FSU/FSRU adjudication |

These are below the 60,000 m³ small-scale cutoff (or CCS "Other"). The workbook does **not**
assert them as FSRUs — `Vessel type` is left blank because FSRU-vs-small-scale is the open
question for the human reviewer. No full-size in-service FSRU is missing.

**Backend-only (1).** Samsung HI (MISC FSRU), live row 1201, on-order 2029 — **expected**
absence (GIIGNL is in-service only).

**FSU exclusions (10).** Backend rows typed `FSU`, listed so they don't resurface as false
gaps. Note: the small-scale candidates (esp. Torman vs FSU "Torman II") also pend FSU/FSRU
review.

**GIIGNL orderbook (4).** N/B Hyundai HI (2027), Excelerate Acadia (2026), N/B Hanwha Ocean
(2027), LNGT Oceania (2026) — passed through as a Phase B reference.

## Methodology (the load-bearing choices)

- **Name-based join** — GIIGNL has no IMO column, so the join is by vessel name over
  {current name} ∪ {ex_names}, normalized (`normalize_vessel_name`: diacritics folded,
  "(ex …)" parentheticals stripped). `ex_names` is essential (Italis/Golar Tundra, Saros/Vasant 1).
- **Capacity is the corroborator; builder is NOT.** Storage m³ ↔ backend Capacity (cbm), within
  `max(6000 m³, 3%)`. Builder diffs are expected conversion-yard noise — informational only.
- **Manual pairing requires owner-tag overlap** (not capacity alone). This guard prevents the
  coincidental mis-pair GIIGNL "Torman" (Access LNG, 28k) ↔ backend "Coral Encanto" (Anthony
  Veder, 30k) — they agree on capacity/delivery by chance; owner tags don't overlap, so Torman
  correctly falls through to a small-scale candidate.
- **Whole-backend match (not just FSRU-typed rows).** Matching against the entire backend is
  what surfaced the reclassify findings (Alexandroupolis, LNGT Americas, both typed conventional).

## Source rule — GIIGNL is NOT a citable `[ref]`

GIIGNL's source line is "Clarksons Research, GIIGNL" — same data family as SFOC. It is a
**comparison artifact, not a citable `[ref]`** (added to `data/source_roster.md` Forbidden list,
same status as SFOC). The workbook pre-fills **no `[ref]` cells**; any candidate promoted in
Phase B must carry a primary source verified through the §3.8 URL gate. The backend is never
auto-edited — promotion runs through the Apply SOP (digest → apply → verify), additive to blanks.

## Toolchain changes committed in this batch

- **`scripts/fsru_reconcile.py`** (new) — the name-keyed five-bucket reconciler.
- **`scripts/normalize.py`** — added `normalize_vessel_name`, `_strip_diacritics`,
  `fsru_owner_tags` + `_FSRU_OWNER_ALIASES` (purely additive; existing functions untouched).
- **`scripts/build_workbook.py`** — added `--mode fsru` (`build_fsru` + `_table_sheet` helper)
  and the `--reconcile` arg.
- **`docs/sops/fsru_reconciliation.md`** (new, FR rev 1) — the authoritative SOP.
- **`docs/pointers.md`**, **`CLAUDE.md`** — FSRU workflow indexed + router section added.
- **`data/source_roster.md`** — GIIGNL added to the Forbidden list.
- **`tests/test_fsru_reconcile.py`**, **`tests/test_normalize_fsru.py`** (new) — bucket logic +
  normalizer guards.

(The `refdata/` → `data/` rename and the `.gitignore` `gem_export*.csv` entry were Phase 0
prerequisites, committed earlier in this work.)

## Verification

- `recalc.py` → **zero formula errors** (10 sheets).
- Spot-checks: ex-name match (Italis/Golar Tundra row 648), former-suspected gap now matched
  (Saros/Vasant 1 row 1089), delivery-year diff (FSRU Toscana) — all render correctly.
- `dedupe_check.py` → **no FSRU-related duplicates** (only pre-existing non-FSRU
  placeholder/identified pairs, e.g. Hyundai Samho / Capital Clean ECC conventional LNGCs).
- `pytest tests/` → **78 passed**.
- All live-sheet rows in this note are the live tab rows (data_start + offset + 1), not the
  column-A `row_id`.

## Phase B (later, not in this batch)

Comprehensive global FSRU build: triangulate on-order (SFOC + CSB Ring A + the 4 GIIGNL
orderbook units), proposed (Discovery Rings C/D), idle/converted; IMO backfill per-candidate;
cross-project sync via the terminals repo's `fsru_sync_check.py --carrier-export`; promote vetted
candidates through the Apply round-trip. Deployment attributes (terminal, send-out MTPA) have no
backend column yet — recommend a name/IMO-keyed sidecar before any schema change.
