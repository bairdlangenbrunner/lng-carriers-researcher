# LNG Carrier Tracker — Data-fill Research SOP

**Document purpose:** Operating manual for the **data-fill** workflow — researching **blank** (and literal-`unknown`) backend data cells and proposing a value plus a corroborating `[ref]` URL for each, packaged as a candidate workbook for human review. It complements the [ref]-Fill SOP (which cites *existing* values) and the Discovery SOP (which finds *new vessels*). **Authoritative** for this workflow.

**Last revised:** 2026-06-05 rev 2 (added §3 pointer to [ref]-Fill SOP §3.8c — the value↔ref corroboration gate (hard-block) now enforced centrally in `merge_fills.py`: a `[ref]` is dropped from any cell whose proposed value its live page does not contain, and the conflict is logged to `candidate_findings` rather than kept; includes the dual-figure capacity rule. No workflow-structure changes.). Prior: 2026-06-04 rev 1 (initial SOP, written alongside the first data-fill batch — rows with `Last updated >= 2026-05-18`. Inherits the [ref]-Fill SOP §4 rules wholesale; adds the blank-vs-`unknown` preserve-ref contract (§4), the derivable autofill layer (§5), and the `data_fill` build mode + output structure (§7). Abbreviated **DF**.).

---

## 1. Scope

**What data-fill does.** For a chosen set of backend rows, find data cells that are **blank** or contain the literal token **`unknown`**, research the correct value, and propose `value + corroborating [ref] URL` pairs to a candidate workbook for human review. The backend is never edited ([ref]-Fill SOP §4.7).

**In-scope columns ("everything researchable").** IMO number, Name, Hull number, Shipowner, Shipowner country/area, Shipbuilder, Capacity (+ units), Cargo type, Vessel type, Propulsion type, Delivery year, Operator/charterer, Contract date, Price (+ currency).

**Out of scope.** Researching geolocation (lat/lon/plus code/accuracy — [ref]-Fill SOP §4.8; the yard-location *block* is autofilled, see §5, not researched); the workflow columns Researcher / Last updated / [Original source]; and any cell that already holds a non-blank, non-`unknown` value (contradicting an existing value is a **conflict**, not a fill — see §9).

---

## 2. Parameters to confirm with the user

1. **Row selection.** Usually a filter on `Last updated` (e.g. `Last updated >= 2026-05-18`); could also be a row range or a yard.
2. **Columns.** Default "everything researchable" (§1); can be narrowed to a priority subset.
3. **Confidence floor.** Default: ship Green + Yellow; Red is discouraged (prefer a documented blank).
4. **Derivable autofills.** Default: include the deterministic §5 autofills.

The scope is a **moving target** — the user edits the backend between and during batches. The mandatory fresh pull ([ref]-Fill SOP §3.0) at run start is the single source of truth for which rows/cells are in scope.

---

## 3. Relationship to the [ref]-Fill and Discovery SOPs

Data-fill **inherits all [ref]-Fill SOP §4 rules**. The load-bearing ones:
- **§3.8 URL verification gate** — every URL passes HTTP 200 + content match + soft-error check before it enters the xlsx.
- **§3.8a** — environment-blocked URLs are kept/flagged, not deleted.
- **§3.8c value↔ref corroboration gate (hard-block)** — a `[ref]` may only be cited on a cell whose proposed value its live page actually contains; a live page that states a *different* figure is dropped from that cell and the conflict is logged to `candidate_findings`, never kept. `merge_fills.py` enforces this centrally (`corroborates()` / `value_variants()`). Includes the dual-figure rule (nominal vs 98%-fill capacity → carry the nominal).
- **§4.7** — never edit the backend; output is a candidate workbook.
- **§4.8** — never *research* geolocation (but see §5: the yard-location block is *mirrored* from a sibling row).
- **§4.9** — don't fill empty cells without explicit source support; surface as candidate fills. **Data-fill is this path executed in batch** (see §6 of [ref]-Fill, and §9 below).
- **§4.12 Rule E** — cluster coherence (owner + yard + ship-count/contract-date).
- **§4.13 Rule F** — never an orphan `[ref]`; value and its `[ref]` are populated together.
- **§4.14** — owner/charterer stylization (the backend's short form, e.g. `COSCO`).
- **§4.15** — multiple URLs in one cell join with `", "`.
- **§5** — Green / Yellow / Red confidence labels.
- **§6a / §9** — hull and IMO fallback (CSB → DART/KIND → class society → vessel DB → §6a.8 IMO tracker → §6a.9 documented blank).

The Discovery SOP **§3 four-ring source model** (Ring A CSB, Ring B regulatory, Ring C trade press, Ring D cross-refs) is the search method for the research pass.

---

## 4. The blank-vs-`unknown` contract (the one rule unique to this SOP)

A data cell is a research target when it is **blank** OR contains the literal token **`unknown`** (case-insensitive).

- **Blank cell** → research the value; propose `value + new verified [ref]`.
- **`unknown` cell** → treat it as blank for research (find the real value), **but the existing URL(s) in the paired `[ref]` cell are PRESERVED and only appended to — never deleted.** When a value is proposed for an `unknown` cell, the candidate `[ref]` renders the existing URL(s) **first**, then any new corroborator (`", "`-joined, §4.15), and the cell is shaded **peach** to signal "pre-existing ref present, added-to, not replaced." The data cell carries a comment `prev: "unknown"`.

If research cannot identify the real value of an `unknown` cell, do **not** fabricate one: record a documented blank (§11) and leave the cell as-is. (Worked example: the 2026-06-04 batch's O1213 / id 1218 — a Samsung HI carrier for an undisclosed Bermuda owner — stayed `unknown`; the owner is genuinely not public, and its existing Cyprus Shipping News `[ref]` was preserved.)

The preserve guarantee is enforced in the build: `existing_ref_preserved` is read from the **fresh backend pull at build time** (not from the researcher/subagent), so the live URL is provably the one carried forward.

---

## 5. Derivable autofill (deterministic — runs before web research)

Some cells are determined by data already in the backend; they are filled by copying, not research, and narrow the set the research pass must cover. Implemented in `scripts/derive_fills.py`.

**Authoritative facts tables (rev: 2026-06-04).** Builder- and owner-level facts — facts about the *yard* or *owner*, not the vessel — now live in two editable, canonical CSVs that the autofill reads **first**: `data/shipbuilder_facts.csv` (yard country/area + the yard-location block, keyed by `normalize_builder`) and `data/shipowner_facts.csv` (Shipowner country/area + `[ref]`, keyed by `normalize_owner`). Seed/refresh them from the live backend with `python scripts/seed_lookups.py`; loaders live in `scripts/lookups.py`. The backend-sibling scan below is now the **fallback** for tags absent from a table. `qc_backend.py` flags any backend row whose yard/owner facts disagree with the tables.

- **Shipowner country/area** ← `data/shipowner_facts.csv` if the owner is listed (non-`AMBIGUOUS`); otherwise the **unambiguous** country shared by sibling backend rows of the same `normalize_owner` (`owner_country()` in `scripts/normalize.py`). If the owner's siblings disagree (currently `mol`: Japan/Türkiye; `maran-gas`: multiple — written `AMBIGUOUS` in the table) or none carry a country, **do not autofill — research it.** The country `[ref]` is copied alongside the value (value + ref travel together → no orphan, Rule F). See `data/owner_charterer_map.md`.
- **Capacity units** ← `cbm` whenever a Capacity value exists or is proposed (only value in the backend). Shares the Capacity citation.
- **Price currency** ← set from the same source that gives Price (not derivable from the integer alone); the build asserts every proposed Price carries a currency.
- **Yard-location block** (`Shipbuilder yard country/area` + its `[ref]`, and the five `Yard location …` columns) ← `data/shipbuilder_facts.csv` first, then the Discovery SOP §6.7 sibling-scan fallback (`_yard_location_map_table_first` → `_build_yard_location_map`, keyed on `normalize_builder`).

Derivable fills are labeled Green (backend-internal consistency) and carry `derivable: true`. A derivable fill whose copied sibling ref is dead/blocked keeps the **value** (it stands on backend consistency) and drops only the URL.

---

## 6. Workflow per batch

```bash
cd scripts/

# 1. Fresh backend CSV + colmap (MANDATORY first step — re-derives scope; schema drifts)
python pull_backend.py

# 2. Dedup index — cluster_index for the per-cluster fan-out
python dedup_index.py

# 3. Derivable autofills + scope + per-cluster research task lists
python derive_fills.py --since <YYYY-MM-DD>
#   -> work/data_fill.json (derivable fills + scope.row_ids)
#   -> work/research_tasks.json (per-cluster cells still needing research)

# 4. Research fan-out: one subagent per cluster (Discovery §3 four-ring model,
#    controlled vocab §8, owner stylization §4.14, preserve unknown refs §4).
#    Each writes work/research_<label>.json (fills + documented_blanks + verification_log).
#    Reuse prior batches (e.g. the discovery candidates.json) and backend siblings first.

# 5. Merge + central §3.8 gate
python merge_fills.py
#   -> merges derivable + all research_*.json into work/data_fill.json,
#      dedups (row_id, field), re-verifies distinct fill URLs (drops dead/blocked;
#      demotes a research fill that loses all URLs to a documented blank).

# 6. Build the candidate workbook
python build_workbook.py --mode data_fill --fills ../work/data_fill.json \
  --out ../batches/<date>_data_fill_rows_X-Y/

# 7. Recalc — zero formula errors required
python recalc.py ../batches/<date>_data_fill_rows_X-Y/lng_carrier_data_fill.xlsx

# 8. Copy work/data_fill.json into the batch dir; write notes.md; commit the batch
#    directory. Do NOT push without user approval.
```

**Per-cluster subagent contract.** Input: the cluster's rows + per-cell `blank`/`unknown` flags (from `research_tasks.json`). Output: a `fills` list (schema in §7) + a `documented_blanks` list, with each fill's URL already passed through `url_verifier.py` using cluster-coherent (Rule E) expected substrings. The central `merge_fills.py` pass is the authoritative §3.8 backstop.

---

## 7. Output workbook structure

`batches/<date>_data_fill_rows_X-Y/lng_carrier_data_fill.xlsx` (built by `build_workbook.py --mode data_fill`). Three sheets:

### 7.1 `README`
Scope, color legend, the unknown/preserve-ref rule, counts.

### 7.2 `backend_data_fill`
Row-oriented, **mirrors the backend column order exactly** after five prefix columns (`row_id`, `cluster_id`, `cluster_label`, `n_proposed`, `max_confidence`) — paste-review-friendly like the discovery `candidate_vessels` sheet. One worksheet row per in-scope backend row. Cell shading:

| Situation | Value written | Fill |
|---|---|---|
| existing value, no proposal | existing, verbatim | **gray** |
| was **blank**, proposed | proposed value | confidence color (G/Y/R) |
| was **`unknown`**, proposed | proposed value + comment `prev: "unknown"` | confidence color |
| `[ref]`, existing only | existing url(s) | **gray** |
| `[ref]`, existing **+ appended** corroborator | `existing ", " new` (existing first) | **peach** |
| `[ref]`, was blank, new url(s) | new url(s) `", "`-joined | confidence color |

**Peach means "the original URL is still there, first, before the first `", "`."**

### 7.3 `QA_review`
- **Candidate data-value fills** — `row_id, field, prev_state, proposed_value, new_urls, existing_ref_preserved, confidence, note` (one per proposal).
- **Documented blanks (researched, not found)** — `row_id, field, searched, as_of, note` (§11).
- **URL verification log** — `url, status, soft_error, content_match, result` (§3.8).

**Input `fills` JSON schema** (one entry per cell): `row_id`, `field` + `ref_field` (EXACT backend header strings), `proposed_value`, `new_urls[]`, `prev_state` (`blank`|`unknown`), `existing_ref_preserved`, `confidence` (G/Y/R), `note`, `derivable`(bool). Plus top-level `scope.row_ids`, `documented_blanks[]`, `verification_log[]`, and optional `candidate_findings[]` (conflicts/cross-checks surfaced during research — recorded for the reviewer, never written as fills).

---

## 8. Controlled vocabularies

The type columns are a fixed value set (`build_workbook.py` writes verbatim — no normalizer). A proposal for these **must** use an exact canonical value; the build validator (`_DATA_FILL_VOCAB`) warns on anything off-vocab, and off-vocab values are flagged to `documented_blanks` ("vocab decision needed") rather than written. The lists live in `data/controlled_vocab.md`:
- **Cargo type**: `membrane`, `spherical`, `self-supporting prismatic`, `type C`
- **Vessel type**: `conventional`, `FSRU`, `q-flex`, `q-max`, `icebreaker`, `FSU`, `Supporting`, `small-scale`, `mid-scale`
- **Propulsion type**: `X-DF`, `DFDE`, `steam`, `ME-GA`, `ME-GI`, `SSD`, `steam reheat`, `STaGE`, `prismatic conventional DFDE`, `prismatic small-scale DFDE`
- **Capacity units** `cbm`; **Price currency** `$m` / `USD`.

Note (from the first batch): trade press almost never prints the literal token `conventional` for Vessel type — CSB says "LNG Tanker", press says "LNG carrier". A class call of `conventional` is defensible but unsourced, so it is left blank rather than written without a value-present source.

---

## 9. Rule F / §4.9 consistency

Data-fill is **fully consistent** with [ref]-Fill SOP §4.9 and Rule F, and is **not** a backend edit:
- §4.9 says "if a source explicitly supports a value, add it to `QA_review > Candidate data-value fills` for human review." Data-fill does exactly that, at batch scale — every proposed value is backed by a §3.8-verified, Rule-E-coherent, value-containing URL, output to a candidate workbook (§4.7).
- **Rule F** (no orphan `[ref]`): the value and its verified URL are a paired candidate fill — populated together in the candidate, never written to the backend until the human accepts the pair. This is the §4.13 step-1→4 path.
- The `unknown` case strengthens the additive guarantee: existing `[ref]` URLs are appended to, never replaced.
- A research finding that **contradicts an existing non-blank value** is a **conflict** ([ref]-Fill SOP §8 `Data-value conflicts`), recorded in `candidate_findings`, not a fill. Data-fill stays strictly additive to blanks/`unknown`s.

---

## 10. Confidence labels

Defer to [ref]-Fill SOP §5 (Green / Yellow / Red). In practice for data-fill:
- **Green** — value verbatim in a primary/regulatory source (DART, Bursa, yard PR, owner PR, class society) or 2 cross-checked sources; OR a derivable autofill (backend-internal consistency).
- **Yellow** — entity-level confirmation, single non-primary source, an implied/inferred value (e.g. country inferred from "London"), or a paywalled body where only the public surface attests.
- **Red** — avoid; prefer a documented blank.

---

## 11. Documenting blanks (§6a.9 pattern)

Every cell researched without a sourceable value gets a `documented_blanks` entry (`row_id`, `field`, `searched` recipes, `as_of` date, `note`). The data cell stays blank — an honest blank beats a fabricated value ([ref]-Fill SOP §3.8 / §4.4(iii)). Fresh orders routinely have no public hull / IMO / name / price; document and move on (≤2–3 targeted searches per cell), so the next run doesn't re-walk dead ends.

---

## 12. Pause-and-ask triggers

- A type-column value that isn't in the controlled vocab (§8) — surface for a human vocab decision.
- An owner-country ambiguity beyond the known `mol` / `maran-gas` (the guard catches it; flag it).
- A proposed value that conflicts with a non-blank backend value — that's a §9 conflict, not a fill.
- A whole column with near-zero yield (Price, Operator/charterer) where forcing values would mean low-confidence guessing — prefer documented blanks and tell the user.

---

## 13. Changelog

- **rev 2** (2026-06-05): Added a §3 pointer to the new [ref]-Fill SOP §3.8c value↔ref corroboration gate (hard-block) — `merge_fills.py` now drops any `[ref]` whose live page does not contain the cell's proposed value and logs the conflict to `candidate_findings` instead of keeping it; includes the dual-figure capacity rule (carry the nominal). Surfaced by the 2026-06-05 rows 1216/1217 capacity defect. No data-fill workflow-structure changes.
- **rev 1** (2026-06-04): Initial SOP, written with the first data-fill batch (rows `Last updated >= 2026-05-18`: 42 rows, 88 fills, 140 documented blanks, 1 `unknown` preserved at O1213). Establishes the blank-vs-`unknown` preserve-ref contract (§4), the derivable autofill layer (§5; `scripts/derive_fills.py`, `normalize.owner_country`), the per-cluster research fan-out + central §3.8 merge (`scripts/merge_fills.py`), the `data_fill` build mode + `backend_data_fill` output sheet (§7), and the controlled-vocab guard (§8; `data/controlled_vocab.md`). Inherits [ref]-Fill SOP §4 rules wholesale.
