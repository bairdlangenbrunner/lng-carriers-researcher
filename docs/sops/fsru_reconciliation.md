# LNG Carrier Tracker — FSRU Reconciliation SOP

**Document purpose:** This SOP describes the workflow for reconciling the backend Google Sheet's FSRU coverage against the GIIGNL Annual Report's "FSRU FLEET AT THE END OF \<year\>" table — the most complete public roster of *in-service* FSRUs. It is distinct from the companion SOPs: the [ref]-Fill SOP covers citation work on existing rows, Discovery covers finding vessels missing from the backend's leading edge, the SFOC SOP covers the IMO-keyed bulk reconciliation against the Clarkson orderbook, and *this* SOP covers the name-keyed comparison of the backend's FSRUs against the GIIGNL fleet table. It is the operating manual for both the immediate gap-analysis ("how complete is our FSRU coverage?") and the recurring annual refresh when a new GIIGNL report lands.

**Last revised:** 2026-06-26 rev 1 (initial issue — codifies the name-based join, the capacity corroborator, the five-bucket model, and the `--mode fsru` workbook, from the 2026-06 GIIGNL-2026 comparison batch).

---

## 1. Scope and prerequisites

**What this SOP covers.** Name-keyed reconciliation of the backend's FSRUs (`Vessel type` == `"FSRU"`) against the GIIGNL in-service FSRU fleet table: matched vessels with field-level disagreements, GIIGNL FSRUs missing from the backend (candidates to add), GIIGNL FSRUs present in the backend but typed as something other than FSRU (reclassification findings), GIIGNL FSRUs that pair to a backend row only by capacity+owner with no name match (manual pairing), and backend FSRUs absent from GIIGNL (mostly expected non-findings — GIIGNL is in-service only). It is the operating manual for the comparison itself; *adding* the vetted candidates to the backend runs through the Apply SOP unchanged.

**What it does NOT cover.**
- Per-row `[ref]` citation work — see the [ref]-Fill SOP.
- Discovery of newly-ordered FSRUs past the backend's leading edge — see the Discovery SOP (`is_lng_relevant` already includes FSRU; the GIIGNL orderbook block feeds Discovery, not this comparison).
- The IMO-keyed SFOC bulk reconciliation — see the SFOC SOP. **The two compose:** SFOC joins on IMO across the whole fleet; this joins on name across the FSRU subset, because GIIGNL has no IMO column.
- A *comprehensive global* FSRU database (on-order/proposed/idle/converted). GIIGNL is the in-service deployed block only; the comprehensive build (Phase B) triangulates SFOC + CSB Ring A + the GIIGNL orderbook + trade press, and is out of scope here.

**Tracker inclusion criteria** apply as a filter throughout (`docs/inclusion_criteria.md`):
- INCLUDED: FSRUs in global LNG trade.
- EXCLUDED: FSUs (storage-only), small-scale / power-barge regas units, anything cancelled or decommissioned before the report's cutoff. Excluded units are logged as a **known-exclusions list** so they don't resurface as false gaps.

**Critical positioning of GIIGNL.** GIIGNL's source line reads "Clarksons Research, GIIGNL" — the same data family as SFOC. It is a **comparison artifact, NOT a citable `[ref]`** (`data/source_roster.md` Forbidden list; same status as SFOC). Nothing this workflow produces ends up cited as a GIIGNL URL. GIIGNL-derived values are *starting points to verify*: a candidate is only promoted after a primary source is attached via `url_verifier.py` (§3.8). The workbook deliberately pre-fills **no `[ref]` cells**.

**Two input files.**
- **Backend CSV** — the live `backend` tab, pulled fresh (mandatory first step, [ref]-Fill SOP §3.0). The user edits it between batches; always re-pull, and re-derive the colmap from the fresh header.
- **GIIGNL fleet JSON** — extracted from the committed GIIGNL PDF by the sibling repo's parser (`../lng-terminals-researcher/scripts/giignl_fsru_fleet.py`). **Do not rebuild the extractor** — it is production-tuned for the report layout. Stage its output into the gitignored `work/`.

---

## 2. Parameters to confirm with the user before starting

1. **GIIGNL edition.** Which report year. Use the single most recent PDF (the 2026 report = "fleet at the end of 2025"); do not blend prior years.
2. **Backend snapshot timing.** Pull fresh. The reconciliation references specific **live sheet rows**; if the user keeps editing during the pass, the workbook is a point-in-time snapshot — keep the same `work/backend.csv` for both the reconcile and the build so the sheet-row numbers stay consistent.
3. **Small-scale cutoff.** Default: storage < 60,000 m³, or CCS == "Other", flags a GIIGNL gap for **FSRU-vs-small-scale human review** rather than asserting it as an FSRU to add (`SMALL_SCALE_M3` in `fsru_reconcile.py`). These are the power-barge / mid-scale units (EDN 1, Karunia Dewata, Torman, Eemshaven LNG in the 2026 edition). Confirm before changing.
4. **Capacity tolerance.** Default: agree if within `max(6000 m³, 3%)` (`CAP_TOL_ABS` / `CAP_TOL_FRAC`). GIIGNL rounds storage figures; the band absorbs the rounding without admitting genuinely different sizes.
5. **Output naming.** Default `batches/<date>_<HHMMET>_fsru_reconciliation_giignl<year>/lng_carrier_fsru_reconciliation.xlsx` (ET time per the batch-naming convention). One committed directory per run.

---

## 3. The name-based join

GIIGNL has **no IMO column**, so the FSRU subset can't use the SFOC IMO join. The reconciliation joins on **vessel name** instead, with capacity as the corroborator.

### 3.1 The join key

For each GIIGNL vessel, build the key set = {current name} ∪ {ex_names}, each passed through `normalize_vessel_name()` (folds diacritics — GIIGNL "Höegh" vs backend "Hoegh"; strips "(ex …)" parentheticals; lowercases; collapses whitespace). Match against the backend `Name`, also normalized. A GIIGNL vessel hits a backend row if **any** key in its set equals the backend name's normalized form.

**`ex_names` is load-bearing.** The backend frequently still lists a vessel under its former name. The canonical cases: GIIGNL "Italis LNG (ex Golar Tundra)" has zero hits under "Italis" but matches backend "Golar Tundra"; GIIGNL "Saros (ex Vasant 1)" matches backend "Vasant 1". Dropping `ex_names` turns both into false gaps.

### 3.2 The corroborator: capacity, NOT builder

- **Capacity is authoritative.** Compare GIIGNL `storage_m3` ↔ backend `Capacity` (cbm), both in cubic metres. Never mix in send-out MTPA (that's regas throughput, a different quantity). In the 2026 edition, capacity agreed on **every** matched pair — it is the reliable confirmation that a name match is the same vessel.
- **Builder is informational only — do NOT use it to confirm or reject a match.** For converted units GIIGNL lists the **conversion yard** while the backend keeps the **original builder**. Builder diffs on matched rows are expected and surfaced for information, not flagged as defects.
- **Owner uses tag-set overlap** (`fsru_owner_tags()`), which collapses lessor/operator stylings (Energos Infrastructure → energos, Karpowership → karmol, Höegh LNG / "Esperanza Hoegh" → hoegh). Owner overlap is a secondary signal and, critically, the **mandatory** guard on manual pairing (§3.3).

### 3.3 Manual pairing requires owner overlap

When a GIIGNL vessel has **no name match**, `suggest_manual()` may still propose a single backend row — but only when **both** capacity agrees **and** owner-tag overlap is non-empty. Capacity alone coincides far too often at common sizes (170k, 30k) and would mis-pair distinct vessels: GIIGNL "Torman" (Access LNG, 28k) and backend "Coral Encanto" (Anthony Veder, 30k) agree on capacity and delivery year by pure coincidence — the owner-overlap guard correctly keeps them apart (Torman falls through to a small-scale candidate). The guard's positive case is the backend **name defect**: GIIGNL "Höegh Esperanza" ↔ backend "Hoegh" (owner cell "Esperanza Hoegh") — no name match, but capacity + owner overlap pair them, and the human confirms and fixes the backend Name. Manual suggestions are **never auto-resolved** — always proposed for human pairing.

---

## 4. The five-bucket model

`scripts/fsru_reconcile.py` produces five buckets (plus the FSU exclusions list and the GIIGNL orderbook passthrough). The workbook renders one sheet per bucket.

### 4.1 Bucket 1 — Matched (GIIGNL ↔ backend, both typed FSRU)

A name/ex-name hit on a backend row already typed `FSRU`. Per-field diff triage: capacity (the corroborator), delivery year (GIIGNL `built_year` ↔ backend `Delivery year`), owner (tag overlap), builder (informational). **Color only genuine diffs** — capacity disagreement is RED, a delivery-year or owner mismatch is YELLOW; builder differences are left uncolored (expected conversion-yard/abbreviation noise).

### 4.2 Bucket 2 — Reclassify (GIIGNL FSRU, backend row typed non-FSRU)

A name/ex-name hit on a backend row typed something **other** than FSRU (conventional, etc.). This is a **typing finding, not a gap** — the vessel is in the tracker but mis-typed. Surface GIIGNL's `location_status`/`location_raw` so a "candidate conversion" caveat is visible before anyone changes the backend `Vessel type`. (2026 edition: Alexandroupolis, typed conventional; KARMOL LNGT Powership Americas / backend "LNGT Americas", flagged candidate conversion.)

### 4.3 Bucket 3 — Manual pairing (no name match; capacity+owner suggest a row)

The §3.3 output. A single suggested backend row for human pairing, typically a backend name defect. YELLOW; never auto-applied.

### 4.4 Bucket 4 — Candidates to add (in GIIGNL, absent from backend)

The genuine-gap bucket — the headline answer to "what's missing." Rendered in **backend column order** with GIIGNL-only attributes (owner, builder, send-out MTPA, terminal, status) carried in prefix columns. Structural backend fields are pre-filled (`Name`, `Capacity`, `Capacity units` = cbm); **`[ref]` cells stay blank** (GIIGNL not citable). Small-scale candidates (§2.3) are **YELLOW with `Vessel type` left blank** — FSRU-vs-small-scale is the open question, so the workbook does not assert FSRU. Full-size gaps would be GREEN with `Vessel type` = FSRU pre-filled (none in the 2026 edition — every full-size in-service FSRU was already present).

### 4.5 Bucket 5 — Backend-only (backend FSRU absent from GIIGNL)

Mostly **expected non-findings** — GIIGNL is in-service only, so the tracker's on-order / idle / spot FSRUs are *supposed* to be absent. GRAY (pre-classified expected). Real signal would be an FSU that should be reclassified; verify before dismissing. (2026 edition: one — Samsung HI (MISC FSRU), on-order 2029.)

### 4.6 Known-exclusions and orderbook passthrough

- **FSU_exclusions** — backend rows typed `FSU` (storage-only, out of scope), listed so they don't resurface as false gaps. NOTE: small-scale candidates (e.g. Torman vs backend FSU "Torman II") also pend FSRU-vs-small-scale/FSU adjudication.
- **GIIGNL_orderbook** — GIIGNL's future-delivery block, passed through untouched as a Phase B (comprehensive on-order coverage) reference. Not added here.

---

## 5. Workflow

```bash
# Run from the repo root.

# 1. Fresh backend CSV + colmap (MANDATORY first step; re-derive the colmap).
python scripts/pull_backend.py

# 2. Extract the GIIGNL fleet table (reuse the terminals repo; do not rebuild).
python ../lng-terminals-researcher/scripts/giignl_fsru_fleet.py \
    data/GIIGNL-<year>-Annual-Report-<ver>.pdf --output work/giignl_fsru_fleet.json
#   Sanity: ~50+ fleet + a handful of orderbook records, with vessel_name,
#   ex_names, storage_m3, ccs, sendout_mtpa, vessel_owner, builder, location_*.

# 3. Reconcile (name join + capacity corroborator + five buckets).
python scripts/fsru_reconcile.py
#   -> work/fsru_reconcile.json  (defaults: --fleet work/giignl_fsru_fleet.json
#      --backend work/backend.csv --output work/fsru_reconcile.json)

# 4. Build the reconciliation workbook (10 sheets).
python scripts/build_workbook.py --mode fsru \
    --reconcile work/fsru_reconcile.json \
    --out batches/<date>_<HHMMET>_fsru_reconciliation_giignl<year>/

# 5. Recalc — zero formula errors required.
python scripts/recalc.py batches/<dir>/lng_carrier_fsru_reconciliation.xlsx

# 6. Advisory dedupe sweep (apply.md §5a); confirm no FSRU-related duplicates.
python scripts/dedupe_check.py     # -> work/dedupe_report.csv

# 7. Copy work/fsru_reconcile.json into the batch dir; write notes.md; commit
#    the batch directory. Do NOT push without user approval.
```

**Verification (per batch).** Spot-check an ex-name match (Italis/Golar Tundra), a former-suspected gap that resolves to a match (Saros/Vasant 1), and the candidate count (expect a handful, all small-scale in a current edition). Confirm `recalc.py` reports zero formula errors.

---

## 6. Promotion and escalation

**Promotion (additive, human-gated).** Vetted candidates flow through the Apply SOP unchanged: `batch_digest.py` → `apply_batch.py` → human accept → `verify_apply.py --pull` (with its dedupe sweep). **The backend is never auto-edited** — outputs are candidate xlsx for human review, additive to blanks only, and every promoted value carries a primary `[ref]` verified through §3.8. GIIGNL is never the `[ref]`.

**Escalate** (per Discovery §7 / [ref]-Fill §11) when:
- The candidate gap exceeds ~5 clusters (suggests systematic under-coverage, not normal leading-edge lag).
- A whole class of backend FSRU values looks systematically wrong (e.g. many in-service FSRUs mis-typed).
- A new rule here would invalidate prior batches.
- Name-join corroboration is too thin to support even a YELLOW manual pairing after the owner-overlap guard.
