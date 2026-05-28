# SOP pointer index

Quick lookup for "which SOP section governs X" without re-reading both SOPs. The SOPs are authoritative; this file just indexes them.

The SOPs live in `docs/sops/`:
- `ref_fill.md` — abbreviated below as **RF**
- `discovery.md` — abbreviated below as **DC**
- `sfoc_reconciliation.md` — abbreviated below as **SR** (not yet indexed in detail below)

Last reconciled against: RF rev 16, DC rev 6, SR rev 4 (2026-05-28). Note: the rule/section numbers below were last content-reconciled at RF rev 12 / DC rev 2; the rev 13–16 and DC rev 3–6 changes were path/navigation/QA-note refinements that did not renumber the rules or workflow steps indexed here.

## Hard rules ([ref]-Fill SOP §4)

| Rule | Section | One-line summary |
|---|---|---|
| 4.1 | RF | NEVER cite SFOC as a `[ref]` URL |
| 4.2 | RF | NEVER cite GEM |
| 4.3 | RF | NEVER cite GTT standalone — always pair with non-GTT |
| **A** §4.4 | RF | `Hull number [ref]` URL must explicitly contain the hull number |
| **B** §4.5 | RF | When `Name` = hull number, `Name [ref]` also needs the hull |
| 4.7 | RF | NEVER overwrite backend values (additive only) |
| 4.8 | RF | Skip geolocation `[ref]` fields entirely |
| 4.9 | RF | Don't fill empty data cells without explicit source support |
| 4.10 + §9 | RF | IMOs starting with 1 are REAL — run §6a.8 lookup, don't treat as placeholders |
| **D** §4.11 | RF | Every cited URL must pass the §3.8 verification gate |
| **E** §4.12 | RF | Every cited URL must be cluster-coherent (owner + yard + ship count or contract date) |
| **F** §4.13 | RF | Never fill a `[ref]` without a corresponding data value (no orphan citations) |

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

## Pause-and-ask triggers

- **RF §11** — CSB broken AND §6a fallback exhausted; class of values systematically wrong; new rule invalidates prior batches; corroboration too thin even for yellow
- **DC §7** — >5 candidate clusters in same gap window (systematic gap); single-source broker attribution with no corroboration; whole owner's fleet appears missing; CSB master directory times out; gap window unclear
