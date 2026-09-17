# LNG Carrier Tracker — IGU Reconciliation SOP

**Document purpose:** This SOP describes the workflow for intercomparing the backend Google Sheet against the fleet tables of the IGU World LNG Report — Appendix 3 (active fleet) and Appendix 4 (orderbook). The backend was seeded from the IGU 2025 edition (~1,070 of its rows still carry `Original source = IGU`), so each new edition is the natural annual check on the bulk-loaded fleet: what IGU delivered, renamed, re-typed, dropped or added since the load. It is distinct from the companion reconciliations: SFOC is an IMO-keyed join against the Clarkson orderbook, the FSRU SOP is a name-keyed join against GIIGNL, and *this* SOP is an IMO-keyed join of the **whole fleet** against IGU, with an edition-to-edition comparison layered on top.

**Last revised:** 2026-09-17 rev 1 (initial issue — codifies the word-coordinate extractor, the IMO join, the `kind` model for field diffs, the dropped / status buckets, and the `--mode igu` workbook, from the IGU-2026 intercomparison folded into the sep-17-pass).

---

## 1. Scope and prerequisites

**What this SOP covers.** Extracting both fleet tables from an IGU report PDF; joining them to the backend by IMO; reporting field-level disagreements, Status disagreements, vessels IGU dropped between editions, IGU vessels missing from the backend, backend vessels IGU does not list, IGU orderbook rows printed without an IMO, and IMOs IGU prints twice.

**What it does NOT cover.** Per-row `[ref]` work ([ref]-Fill SOP), leading-edge discovery (Discovery SOP — IGU's cut-off is nine months stale by publication), or writing anything to the backend. Findings promote through a `fix` or discovery batch and the Apply SOP.

**Positioning of IGU as a source.** IGU is the tracker's foundation and, unlike GIIGNL and SFOC, **is citable** — the backend cites the report landing page (`https://www.igu.org/igu-reports/<year>-world-lng-report`) on the bulk-loaded rows. Two limits:
- The landing page does not surface per-vessel values, so an IGU URL cannot pass the §3.8c value↔ref gate for a *new* proposal. A Status change, rename, scrapping or type change found here needs its own verified ref (press / class society / tracker).
- IGU is a secondary compilation with its own defects (duplicate IMOs, mis-spelt names, stale owners). It tells you *where to look*, not what to write. In particular IGU Appendix 3 "Type" is the one published source for the tracker's `conventional` classification.

**Inclusion criteria apply throughout** (`docs/inclusion_criteria.md`): FSUs, small-/mid-scale carriers, bunkering vessels and domestic-only ships are out of scope, as are vessels cancelled or **decommissioned before December 2025**. The last rule decides what happens to a dropped vessel (§5.2).

**Inputs.**
- **Backend CSV** — pulled fresh (mandatory first step, [ref]-Fill SOP §3.0). Keep the same `work/backend.csv` for the reconcile and the build so live sheet rows stay consistent.
- **Current IGU report PDF** — `../lng-terminals-researcher/data/IGU-World-LNG-Report-<year>.pdf` (the terminals repo keeps the committed copy).
- **Previous IGU report PDF** — needed for the edition comparison. Without it every diff is `no_prev_edition` and the dropped bucket is empty.

---

## 2. Parameters to confirm before starting

1. **Editions.** Current and previous. An edition's cut-off is the end of the year before its title year (2026 edition = fleet at end-2025).
2. **Pending batches.** Which un-applied batch dirs to cross-reference (`--pending`). A finding a pending batch already proposes is reported green, not as new work.
3. **Capacity tolerance.** Default agree within `max(6000 cbm, 3%)` (`CAP_TOL_ABS` / `CAP_TOL_REL`) — the FSRU SOP's band.
4. **Tracker leads.** Whether to run the paced shipvault lookup (`--fetch-leads`, ~6 s per IMO, ~50 IMOs) for the review buckets. Default yes.
5. **Output naming.** `batches/<date>_<HHMMET>_igu_reconciliation_igu<year>/lng_carrier_igu_reconciliation.xlsx`.

---

## 3. Extraction (`scripts/igu_fleet.py`)

**Extract every edition fresh — never reuse a prior edition's column positions.** The tables are typeset, not tagged, and the layout changes:

| | 2025 edition | 2026 edition |
|---|---|---|
| Page model | one report page per PDF page | landscape spreads: **two tables per PDF page**, each with its own header (and sometimes an unrelated table in the other half) |
| Fleet columns | 9 (no Age) | 10 (Age added) |
| Orderbook columns | 7 (no Vessel Type) | 8 (Vessel Type added, placed **last**) |
| Orderbook IMOs | 8 rows without one | 46 rows printed `Unknown` |

`pdftotext -layout` interleaves the halves of a spread and gives no column boundaries, so the extractor works from pdfplumber word coordinates and assumes nothing about the column set: each `IMO Number` header starts a table, column left edges come from the header labels, a row starts at each word in the IMO column, and wrapped owner / builder / name lines attach to the row above. The table kind comes from the `Appendix N:` title, falling back to the column set.

**Validation is built in** — IMO check digit, numeric capacity, plausible year, no empty required cell, and a per-page cross-check against an independent count of IMO-shaped tokens. Anything off lands in `warnings`; `--strict` exits 1. **Read the warnings before reconciling.** The expected residue is IGU's own duplicate IMOs. A new header label goes in `FIELD_BY_LABEL`.

**Acceptance check for a new edition:** the fleet/orderbook counts should reconcile with the previous edition — `prev fleet − dropped + delivered + added direct = current fleet` (2026: 742 − 18 + 79 + 1 = 804) — and the previous edition's extraction should reproduce the backend's IGU-sourced rows (2025: 1,068 of 1,070 found by IMO, zero capacity or cargo-type diffs; the other two have no IMO).

---

## 4. The join and the comparison (`scripts/igu_reconcile.py`)

### 4.1 Join key: IMO, as a string

No fuzzy matching. An IGU row whose IMO is not in the backend gets one fallback — a normalized-name lookup — only to flag a *possible backend IMO defect*; it is never auto-paired.

### 4.2 Field comparison

Compared: name, shipowner, shipbuilder, capacity, cargo type, vessel type, propulsion, delivery year.
- **Name** — compared without the `(ex-…)` tail and punctuation; a backend placeholder (`Hull 2541 (Hanwha)`) against an IGU real name is a diff (the vessel has been named).
- **Owner** — shared-token overlap after stop-words; IGU prints short / group names.
- **Builder** — IGU prints short labels (`Mitsui`, `HD Hyundai`) where the backend carries full yard names, so labels are compared through a **learned co-occurrence map**: an IGU label ↔ backend yard pairing seen on ≥ 3 matched vessels (`BUILDER_PAIR_MIN`) counts as agreement.
- **Capacity** — §2 tolerance.

### 4.3 What a diff means — `kind`

Because the backend was loaded from the previous edition, the previous edition's value says which side moved:

| kind | meaning | priority |
|---|---|---|
| `igu_changed` | IGU printed a different value last edition — new information | review |
| `new_to_igu` | vessel was not in the previous edition | review |
| `backend_differs` | IGU unchanged between editions; the backend was edited since the load, usually from a better source | low — **never revert blindly** |
| `no_prev_edition` | no previous edition supplied | — |

### 4.4 Buckets

- **matched** — per-field `diffs`, plus a `status_finding` where backend Status disagrees with the IGU table: `delivered_per_igu` (backend on order / proposed, IGU fleet) or `on_order_at_igu_cutoff` (backend active, IGU orderbook). The latter sets `delivery_year_conflict` when the backend Delivery year is at or before the cut-off year — both cannot be true.
- **dropped** — backend `active` rows in the previous IGU fleet and absent from the current fleet *and* orderbook. See §5.2.
- **backend_not_in_igu** — by reason: no IMO in the backend; contract signed after the cut-off; on order / proposed and never listed; **active and never listed** (the only reason worth a second look).
- **igu_only** — candidates to add, possible IMO defects, or out of scope.
- **igu_no_imo** — IGU orderbook rows printed `Unknown`, clustered by owner / yard / contract month / delivery year, with a **cluster-level** backend hint: `strong` (contract month ±1 or hull number agrees), `weak` (owner + yard only), `none`. Never a row pairing. A strong cluster with fewer backend rows than IGU rows is a possible gap.
- **igu_duplicates** — IMOs IGU prints more than once, as printed; the first print is the one joined.
- **edition_diff** — what IGU itself changed.

### 4.5 Leads

`--fetch-leads` looks the review-bucket IMOs up on the open shipvault API (dropped rows, status findings not already pending, IGU-only candidates, active-never-listed rows, vessels that left the orderbook undelivered) — one host, so it is paced like `sweep.py` (6 s ± 2 s), stops after three consecutive failures, and resumes from `work/igu_review_shipvault.json`. The name / status / fate date / delivery date are **leads, never refs**: shipvault is single-source (Y at best), and any value proposed from one goes through §3.8 like everything else.

---

## 5. Reading the findings

### 5.1 Status findings
`delivered_per_igu` rows are usually already covered by a delivery roll-forward batch (green). For `on_order_at_igu_cutoff` with a delivery-year conflict, the usual answer is that the vessel delivered *after* the cut-off and the backend Delivery year is a year early — the shipvault delivery date says which. Rows shipvault still shows on order (e.g. the sanctioned Arctic LNG 2 hulls) are a Status question, not a year question.

### 5.2 Dropped vessels
IGU silently removes scrapped tonnage. For each dropped row get the fate and its date, then apply the inclusion rule: **decommissioned before December 2025 → out of scope, remove the row; December 2025 or later → the row stays**, and the fate is recorded. The Status vocabulary currently has no `scrapped` value — adding one is a user decision (escalate; do not invent a value). Converted vessels (FSU / FSRU) are a Vessel-type change, not a removal, unless the new type is itself out of scope.

### 5.3 Field diffs
Work `igu_changed` by field: delivery-year slips on on-order rows (check against a tracker before accepting — IGU's schedule is nine months old), renames and owner changes (sale / rebrand — need a ref), propulsion flips (ME-GA ↔ X-DF — IGU is often the one correcting itself), vessel-type changes (conversion). `backend_differs` is a reading list for backend *name defects* and load corruption, not a to-do list.

---

## 6. Output workbook (`build_workbook.py --mode igu`)

`lng_carrier_igu_reconciliation.xlsx`, 11 sheets: README, Summary, Dropped_from_IGU, Status_findings, Field_diffs, IGU_only, Backend_not_in_IGU, IGU_no_IMO, IGU_duplicates, Edition_diff, QA_review. Every table leads with the **live sheet row**. Colour: green = a pending batch already proposes it (or a strong hint); yellow = review; red = a contradiction or an out-of-scope row; gray = expected / low priority. **No `[ref]` cells are proposed.** Recalc to zero formula errors.

---

## 7. Batch contents and close-out

Commit one directory: the workbook, `igu_fleet_<year>.json` for both editions, `igu_reconcile.json`, `shipvault_leads.json`, `notes.md` (headline counts, the decisions list, extraction warnings, anything escalated). Run `python scripts/dedupe_check.py` (apply.md §5a). Anything actionable becomes a follow-up `fix` / discovery batch — this batch itself is never applied.

**Escalate** when a whole class of rows is affected (e.g. the first dropped-vessel pass needs a Status-vocabulary decision), when the extractor's acceptance check (§3) does not balance, or when IGU-only candidates exceed a handful (suggests an IMO-column problem, not real gaps).
