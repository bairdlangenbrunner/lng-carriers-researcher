# SOP pointer index

Quick lookup for "which SOP section governs X" without re-reading both SOPs. The SOPs are authoritative; this file just indexes them.

The SOPs live in `docs/sops/`:
- `ref_fill.md` — abbreviated below as **RF**
- `discovery.md` — abbreviated below as **DC**
- `data_fill.md` — abbreviated below as **DF**
- `sfoc_reconciliation.md` — abbreviated below as **SR** (not yet indexed in detail below)
- `fsru_reconciliation.md` — abbreviated below as **FR** (the name-keyed GIIGNL-FSRU comparison)
- `qc_release.md` — abbreviated below as **QC** (the pre-release whole-backend QC pass)
- `apply.md` — abbreviated below as **AP** (the review→apply→verify round-trip)

Last reconciled against: RF rev 17, DC rev 7, DF rev 1, SR rev 5 (2026-06-04). Note: the rule/section numbers below were last content-reconciled at RF rev 12 / DC rev 2; the rev 13–16 and DC rev 3–6 changes were path/navigation/QA-note refinements that did not renumber the indexed rules. RF rev 17 added §4.14–§4.15 and a §4.8 carve-out; DC rev 7 added §6.7–§6.8; DF rev 1 is the new data-fill workflow (inherits RF §4 wholesale) — all indexed below.

## Hard rules ([ref]-Fill SOP §4)

| Rule | Section | One-line summary |
|---|---|---|
| 4.1 | RF | NEVER cite SFOC as a `[ref]` URL |
| 4.2 | RF | NEVER cite GEM (incl. `gem.wiki`) |
| 4.3 | RF | NEVER cite GTT standalone — always pair with non-GTT |
| **A** §4.4 | RF | `Hull number [ref]` URL must explicitly contain the hull number |
| **B** §4.5 | RF | When `Name` = hull number, `Name [ref]` also needs the hull |
| 4.7 | RF | NEVER overwrite backend values (additive only) |
| 4.8 | RF | Never *research* geolocation `[ref]` — but mirror a known yard's block from the backend (DC §6.7) |
| 4.9 | RF | Don't fill empty data cells without explicit source support |
| 4.10 + §9 | RF | IMOs starting with 1 are REAL — run §6a.8 lookup, don't treat as placeholders |
| **D** §4.11 | RF | Every cited URL must pass the §3.8 verification gate |
| **E** §4.12 | RF | Every cited URL must be cluster-coherent (owner + yard + ship count or contract date) |
| **F** §4.13 | RF | Never fill a `[ref]` without a corresponding data value (no orphan citations) |
| 4.14 | RF | Owner/charterer names use the backend's existing short stylization (e.g. `COSCO`) |
| 4.15 | RF | Multiple URLs in one `[ref]` cell join with `", "`, never a newline |

## Workflow steps

| Step | Section | What |
|---|---|---|
| Backend pull | RF §3.0 | MANDATORY first step every batch — pull fresh CSV |
| Cluster rows | RF §3.2 | Group rows by (yard, owner, contract month) |
| CSB lookup | RF §3.3 | Canonical Hull [ref] source |
| §6a fallback | RF §3.3a | MANDATORY when CSB doesn't list a hull |
| Trade press | RF §3.4 | For each cluster, find order announcement |
| Vessel db check | RF §3.5 | Active/near-active vessels only |
| Build workbook | RF §3.6 | Encode citations into build script |
| QA flag conflicts | RF §3.7 | Flag any conflicts vs backend |
| **URL verification gate** | RF §3.8 | MANDATORY before committing the batch |
| 404 sweep of pre-existing | RF §3.8a | Distinguish dead URLs vs environment blocks |

## Confidence labels (RF §5, current rev 12)

- **Green** — ideally 2 cross-checked URLs agree AND both contain value verbatim; OR 1 URL that's explicit (value verbatim + cluster-coherent) and/or primary/regulatory (DART, Bursa, yard PR, owner PR, class society). Rule F still requires the paired data cell to be populated.
- **Yellow** — entity-level confirmation but value implied or contested
- **Red** — single source, weak corroboration; prefer leaving blank with §6a.9 search log

## Workbook structure

| Sheet | Section | What it contains |
|---|---|---|
| README | RF §2.1 / DC §5.1 | Batch summary, methodology |
| backend_ref_fill | RF §2.2 | Backend rows with color-coded citations |
| candidate_vessels | DC §5.2 | Discovery candidates with prefix columns |
| QA_review | RF §2.3 / DC §5.3 | Per-cell log, conflicts, candidate fills, defects, verification log |
| backend_status_flags | DC §5.4 | Non-candidate findings as standalone sheet |
| backend_data_fill | DF §7.2 | In-scope backend rows with proposed values + preserved/appended refs, color-coded |

## Hull citation fallback (RF §6a)

| Step | Section | Source |
|---|---|---|
| 6a.1 | RF | Targeted Google search recipes |
| 6a.2 | RF | DART (Korean filings) — `dart.fss.or.kr` |
| 6a.3 | RF | KIND (KRX English) — `kind.krx.co.kr` |
| 6a.4 | RF | Class society registries (DNV, LR, ABS, KR, BV, NK) |
| 6a.5 | RF | Yard / parent press releases |
| 6a.6 | RF | Owner / charterer press releases |
| 6a.7 | RF | Vessel database newbuild entries |
| 6a.8 | RF | **IMO → marine-vessel-tracker** (run this LAST before negative result) |
| 6a.9 | RF | Document negative result in QA log |

## Discovery workflow (DC)

| Phase | Section | What |
|---|---|---|
| Parameters | DC §2 | Confirm gap window, yard coverage, threshold, FSRU handling, output name |
| Backend pull + indexes | DC §4.2-4.3 | Same as RF §3.0 + build two indexes |
| Ring A (CSB) | DC §4.4 | Authoritative for on-order |
| Ring B (regulatory) | DC §4.5 | Post-CSB leading edge — DART, KIND, Bursa, HKEX |
| Ring C (trade press) | DC §4.6 | Pre-CSB-indexing on-order signal + proposed bucket |
| Ring D (charterer programs) | DC §4.7 | Only if proposed threshold expanded |
| Dedup, enrich, confidence | DC §4.8 | Cluster duplicates; apply RF §5 |
| URL verification | DC §4.10 | Per RF §3.8 |
| Yard-location autofill | DC §6.7 | 7 yard-location cols copied from an existing backend row for the same shipbuilder; blank if new |
| Output formatting | DC §6.8 | Owner stylization (RF §4.14) + multi-URL `", "` (RF §4.15) |

## Data-fill workflow (DF)

| Phase | Section | What |
|---|---|---|
| Scope | DF §1-§2 | Row filter (e.g. `Last updated >= DATE`) + in-scope columns; blank OR literal `unknown` |
| Blank-vs-`unknown` contract | DF §4 | `unknown` = research the value BUT preserve & append-to the existing `[ref]`, never delete |
| Derivable autofill | DF §5 | owner country/area (unambiguous sibling-copy), capacity units, price currency, yard-location |
| Per-batch workflow | DF §6 | pull → dedup → `derive_fills.py` → per-cluster research fan-out → `merge_fills.py` → build → recalc |
| Output | DF §7 | `backend_data_fill` sheet (gray=existing, color=proposed, peach=appended ref) + QA_review |
| Controlled vocab | DF §8 | Cargo/Vessel/Propulsion exact value sets (`data/controlled_vocab.md`) |
| Rule F / §4.9 consistency | DF §9 | proposals are paired candidate fills for review, never a backend edit; conflicts → RF §8 |
| Documented blanks | DF §11 | §6a.9-style negative-result log for cells researched and not found |

## QC sanity check + authoritative facts tables (2026-06-04)

| Thing | Where | What |
|---|---|---|
| Backend QC scan | `scripts/qc_backend.py` | Run after `pull_backend.py`. Flags column-offset / misplaced-value corruption (a controlled value in the wrong column, a data value in a `[ref]`, lat/lon out of range, a URL in a value column, orphan refs, Rule F, lookup-table disagreement). Advisory (writes `work/qc_report.csv`); `--strict` exits non-zero on HIGH/MED findings; `--rows X-Y` scopes. Silence known-legit cells in `data/qc_allowlist.csv`. |
| Builder facts table | `data/shipbuilder_facts.csv` | Authoritative yard country/area + yard-location block, keyed by `normalize_builder`. Autofill reads it first (DF §5). |
| Owner facts table | `data/shipowner_facts.csv` | Authoritative Shipowner country/area + `[ref]`, keyed by `normalize_owner`; `AMBIGUOUS` = research per-vessel. |
| Facts loaders + vocab | `scripts/lookups.py` | `load_builder_facts` / `load_owner_facts` + `CONTROLLED_VOCAB` (single source of truth, shared by build + QC). |
| Seed / refresh tables | `scripts/seed_lookups.py` | Bootstraps both CSVs from the live backend; re-runnable, never clobbers curated rows without `--overwrite`. |

## Pre-release QC workflow (QC — 2026-06-05)

The whole-backend consistency/corruption sweep before a data release. Full SOP: `docs/sops/qc_release.md`.

| Phase | Section | What |
|---|---|---|
| Name conventions | QC §2 | The two placeholder forms (`Hull NNNN (Yard)`; `Shipbuilder (Owner N)`) + consistency rules B1 (one builder label per yard), B2 (canonical owner form), B3 (contiguous ordinals) |
| Scan + triage | QC §3 | `pull_backend.py` → `qc_backend.py` (whole-sheet) → triage by check; corruption (HIGH/MED) escalates, Name drift (LOW) → fix batch |
| Fix batch | QC §4 | `build_workbook.py --mode fix`; `preserve_ref:true` for cosmetic/derived edits (rewrite value, keep `[ref]`, skip §3.8c gate); sourced corrections pass the gate |
| Apply + release gate | QC §5 | Land via the Apply SOP unchanged; re-pull + re-run `qc_backend.py` — clear when HIGH/MED resolved/allowlisted and Name checks at zero |

Name-column QC checks (in `qc_backend.py`): `name-builder-drift` (same yard, different builder label across placeholders) and `name-ordinal-gap` (placeholder missing its sequence number while cluster siblings are numbered) — both LOW/advisory.

## Apply & verify workflow (AP — 2026-06-05)

The offset-proof round-trip that gets a reviewed batch into the backend. Full SOP: `docs/sops/apply.md`.

| Step | Section | What |
|---|---|---|
| Triage | AP §2 | `batch_digest.py` → `digest.md` (auto-safe vs needs-a-decision) |
| Decisions | AP §3 | `apply_batch.py` → `decisions.csv` (accept/hold/reject; Green/derivable→accept default) — authoritative decision surface |
| Apply artifacts | AP §2 | `apply_rows.csv` (full-row paste), `apply_patch.csv` (by-name applier), `apply.json` (record) |
| Apply | AP §2/§7 | full-row paste OR `tools/apply_patch.gs` (by header — offset impossible); never hand cherry-pick |
| Conflicts | AP §4 | `conflicts.csv` — research vs a non-blank value; decided by hand, never auto-applied (RF §8 / DF §9) |
| Verify | AP §5 | `verify_apply.py --pull` → `verify_report.csv` (landed/mismatch/missing) + qc the touched rows |

## FSRU reconciliation workflow (FR — 2026-06-26)

Name-keyed comparison of the backend's FSRUs against the GIIGNL Annual Report's in-service FSRU fleet table (GIIGNL has no IMO column, so the join is by name, not IMO as in SR). Full SOP: `docs/sops/fsru_reconciliation.md`.

| Phase | Section | What |
|---|---|---|
| Scope / positioning | FR §1 | FSRUs only; FSUs logged as exclusions; GIIGNL is a comparison artifact, NOT a citable `[ref]` (like SFOC) |
| Parameters | FR §2 | GIIGNL edition, small-scale cutoff (<60k m³ / CCS "Other"), capacity tolerance (max 6000 m³ / 3%), output name |
| Name join | FR §3 | key = {current} ∪ {ex_names}, `normalize_vessel_name`; capacity corroborates, builder is informational (conversion-yard ≠ original builder); manual pairing requires owner-tag overlap |
| Five buckets | FR §4 | matched / reclassify (typed non-FSRU) / manual pairing / candidates-to-add / backend-only (expected) + FSU exclusions + orderbook passthrough |
| Workflow | FR §5 | pull → terminals-repo extractor → `fsru_reconcile.py` → `build_workbook.py --mode fsru` → recalc → dedupe sweep → commit |
| Promotion | FR §6 | vetted candidates run through the Apply SOP unchanged; backend never auto-edited; GIIGNL never the `[ref]` |

## Pause-and-ask triggers

- **RF §11** — CSB broken AND §6a fallback exhausted; class of values systematically wrong; new rule invalidates prior batches; corroboration too thin even for yellow
- **DC §7** — >5 candidate clusters in same gap window (systematic gap); single-source broker attribution with no corroboration; whole owner's fleet appears missing; CSB master directory times out; gap window unclear
- **DF §12** — type value not in the controlled vocab; owner-country ambiguity beyond `mol`/`maran-gas`; a proposed value conflicts with a non-blank backend value (→ RF §8 conflict, not a fill); a near-zero-yield column where filling would mean guessing
