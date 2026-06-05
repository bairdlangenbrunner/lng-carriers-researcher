# LNG Carrier Tracker — SFOC Reconciliation SOP

**Document purpose:** This SOP describes the workflow for periodically reconciling the backend Google Sheet against a fresh SFOC (Clarkson) export. It is distinct from both companion SOPs: the [ref]-Fill SOP covers citation work on existing backend rows, the Discovery SOP covers finding vessels missing from the backend in the post-SFOC-cutoff leading edge, and *this* SOP covers the quarterly bulk reconciliation against the SFOC snapshot itself — which is the project's authoritative third-party orderbook reference and the upstream source of most candidate adds.

**Last revised:** 2026-06-04 rev 5 (completed the input-side migration left half-done at rev 4 — §4.2 and §2 now stage the three input files in the repo `work/` directory and the residual claude.ai-sandbox path `/mnt/user-data/uploads/` (and its `ls` check) is removed, since it doesn't exist on a cloned local repo. Path-only edit; no reconciliation-rule changes — the four-bucket model, capacity cut, normalization mapping, and nine-sheet structure are unchanged.). Prior: 2026-05-28 rev 4 (repository migration — output model changed to one committed directory per reconciliation run under `batches/`; input files may now be staged in the repo `work/` directory as well as `/mnt/user-data/uploads/`; `present_files` reference updated for the Git/Claude Code workflow. No reconciliation-rule changes from rev 3.). Prior: 2026-05-27 rev 3 (added §3.8b cross-reference to §6.1 — QA notes for reconciliation findings quote only publicly-visible content; LNG Prime editorial entity tags support yellow per §5, not green. Surfaced by the same 2026-05-27 F8 finding that drove [ref]-Fill SOP rev 15 and Discovery SOP rev 5.).

---

## 1. Scope and prerequisites

**What this SOP covers.** Bulk IMO-keyed reconciliation of the backend against a fresh SFOC export: identifying matched vessels with field-level disagreements, vessels present in SFOC but missing from the backend (candidates to add, after filtering against the exclusions list), and vessels present in the backend but missing from SFOC (candidates to verify). It is the operating manual for a recurring (typically quarterly) reconciliation pass that lands at the same point in the project cycle as a new IGU release or a fresh SFOC distribution.

**What it does NOT cover.**
- Per-row `[ref]` URL citation work on existing backend rows — see the [ref]-Fill SOP.
- Discovery of vessels that landed after SFOC's cutoff (the leading edge) — see the Discovery SOP. **The two workflows compose:** SFOC reconciliation covers everything *up to* SFOC's snapshot date; Discovery covers the gap between SFOC's snapshot and today.

**Tracker inclusion criteria** apply as a filter throughout (per the project description; also restated in Discovery SOP §1 and [ref]-Fill SOP §1):
- INCLUDED: conventional LNG carriers and FSRUs in global LNG trade
- EXCLUDED: FSUs (storage-only), small-scale and mid-scale LNG carriers, LNG bunkering vessels, domestic-only ships, anything cancelled or decommissioned before December 2025

**Critical positioning of SFOC.** SFOC is the project's third-party data origin (alongside GEM and the annual IGU World LNG Report) and remains in the backend's `[Original source]` column for rows it seeded. It is **NOT** a citable URL for any `[ref]` cell — see [ref]-Fill SOP §4.1. SFOC reconciliation operates on the SFOC CSV as a comparison artifact only; nothing this workflow produces ends up cited as an SFOC URL in the backend or in any companion workbook.

**Three input files.**
- **Backend CSV** — the live `backend` tab, pulled fresh from the public export URL (see [ref]-Fill SOP §3.0). The user is actively editing it; always re-pull at the start of every reconciliation.
- **SFOC CSV** — the most recent SFOC distribution, supplied by the user and staged in `work/` (Clarkson distributions arrive roughly quarterly; the file name typically encodes the dist version and date, e.g. `..._dist_Q3__updated_may_26_...`).
- **Exclusions CSV** — the deliberately-curated list of small/mid-scale/bunkering vessels that the tracker excludes by criteria. Supplied by the user; shares the backend schema. Without this file, the reconciliation cannot distinguish "SFOC vessel missing from backend" (a real candidate) from "SFOC vessel correctly excluded from backend" (a non-finding).

If the user supplies fewer than three files, ask for the missing one(s) before proceeding rather than assuming defaults. The exclusions file especially: running reconciliation without it produces a "Candidates to add" bucket full of vessels the user has already deliberately excluded, which is worse than not running at all.

---

## 2. Parameters to confirm with the user before starting

Always confirm these before kicking off:

1. **SFOC snapshot date.** Confirm the distribution version (e.g. "dist Q3, updated 26-May-2026") and treat it as the reconciliation's cutoff. Any vessel contracted after the SFOC snapshot is out of scope here and belongs to Discovery.
2. **Backend snapshot timing.** Pull fresh — but confirm whether the user has paused backend edits during the reconciliation or whether they'll keep editing. If they keep editing, note that the workbook captures a point-in-time backend state.
3. **Capacity threshold for the "review as candidates to add" cut.** Default: 50,000 cu m. Vessels below this in SFOC but missing from the backend are presumptively small/mid-scale and should land in the "Already excluded" or "Likely excluded" bucket rather than as add candidates. The 50,000 threshold isn't from the project description (the criteria say "small-scale and mid-scale" without naming a cubic-meter cutoff); it's a working heuristic from the 2026-05-22 pilot. Confirm with the user if you want to change it.
4. **Field-level diff scope.** Default: report every per-field disagreement on matched rows, sorted by `# Diffs` descending. The user may want only substantive diffs (status, capacity, delivery year, builder identity) — in which case apply the §4.6 normalization mapping to suppress cosmetic naming differences before the diff log is built.
5. **Output naming.** Default: `batches/<batch-dir>/LNG_carrier_reconciliation.xlsx` for the workbook; `batches/<batch-dir>/LNG_carrier_backend_with_hull_numbers.csv` for the optional Hull-number backfill CSV (see §4.5). Each reconciliation run gets its own committed directory under `batches/`.

---

## 3. The four-bucket model

SFOC reconciliation produces four primary buckets by IMO join, plus two IMO-less buckets for vessels that can't participate in the join. The whole workflow exists to populate, triage, and present these.

### 3.1 Bucket 1 — Matched (in both backend AND SFOC, joined on IMO)

The largest bucket. In the 2026-05-22 pilot: **1,046 vessels**. The reconciliation work here is per-field disagreement triage — most matched rows have at least one diff (the pilot found 1,036 of 1,046 had ≥1 diff, but most were cosmetic naming differences).

### 3.2 Bucket 2 — Only in SFOC (in SFOC, not in backend, joined on IMO)

The candidate-add bucket. Sub-split by capacity:

- **≥ 50,000 cu m**: presumptively conventional LNG carriers; candidates to add to the backend after cross-checking against the exclusions list. In the 2026-05-22 pilot: **47 vessels** (45 on-order, 2 in-service).
- **< 50,000 cu m**: presumptively small/mid-scale; out of scope per criteria. Cross-check against the exclusions list — most should already be there. In the pilot: **25 vessels**, all already on the exclusions list or matching its pattern.

Sub-split by IMO format:
- **Real 7-digit IMOs** (starts with 9, or 8 for older vessels): typically in-service or near-delivery vessels.
- **Synthetic 11xxxxx IMOs**: on-order vessels without real IMO assignments yet. Both backend and SFOC use this placeholder convention, so the IMO join works on pre-build ships too. Synthetic-IMO-only candidates in SFOC are the post-cutoff (relative to backend) on-order leading edge that SFOC has captured.

### 3.3 Bucket 3 — Only in backend (in backend, not in SFOC, joined on IMO)

The verify-or-explain bucket. Possibilities:
- **(a)** SFOC's snapshot is older than the backend's research and didn't catch some additions. (Most common; no action needed.)
- **(b)** SFOC has explicitly dropped them — possibly because they've been reclassified out of scope (e.g. converted to FSU). Worth spot-checking against the inclusion criteria.
- **(c)** Genuine backend finds that don't appear in any SFOC distribution — fine, no action needed.
- **(d)** The IMO format in the backend doesn't match SFOC's (e.g. backend has the real IMO, SFOC still has the synthetic 11xxxxx — or vice versa). Spot-check; if you can identify the SFOC row by name+yard+owner, the vessel actually IS in both files and should move to Bucket 1. This typically resolves itself on the next quarterly run after IMO assignment.

In the 2026-05-22 pilot: **54 vessels** (51 real-IMO, mostly active vessels from the 1990s–2000s and 14 on-order for 2026; 3 with synthetic IMOs).

### 3.4 Bucket 4 — Contradictions (in BOTH backend AND exclusions list)

Should be empty. A vessel can't simultaneously be in the backend (where it's an active tracker entry) and on the exclusions list (where it's been deliberately removed). If this bucket has any rows, one of the two lists is wrong and needs human review before the reconciliation can be trusted.

In the 2026-05-22 pilot: **0 vessels**. Clean.

### 3.5 Bucket 5 — Already excluded (in SFOC, not in backend, but on exclusions list)

The "we already considered this and decided no" confirmations. Validates that the exclusions list is being applied correctly. The 25 small/mid-scale `<50,000 cu m` only-in-SFOC vessels from Bucket 2 typically land here.

In the pilot: most of the 25 small-cap only-in-SFOC vessels matched exclusions list entries. Two cases worth flagging in this bucket:
- **Definition-disagreement cases**: a vessel that the exclusions list classifies one way (e.g. "bunkering") that SFOC classifies differently (e.g. "regular LNG Carrier"). Example from the pilot: IMO 9627497 *Maran Gas Efessos* — on exclusions list as a bunkering vessel; in SFOC as a 159,800 cu m regular LNG Carrier. Flag for human verification; exclusions list is treated as authoritative until the user resolves the disagreement.
- **Naming-mismatch cases**: same vessel, different name across the two files (e.g. IMO 8608884 `LNGT Oceania` on exclusions list, `Karadeniz LNGT Powership Oceania` in SFOC). These are not real disagreements — same IMO means same vessel. No action needed beyond noting it in the workbook.

### 3.6 IMO-less rows (no IMO in either file, joined on... nothing automated)

Two parallel sub-buckets, presented side-by-side for manual matching:
- **No_IMO_Backend**: backend rows with blank IMO. In the pilot: **43 rows**, mostly proposed vessels with no contract/hull assigned yet (`Equinor 1-4`, `Hanwha Ocean 1-2`, `Mozambique LNG 01-02`).
- **No_IMO_SFOC**: SFOC rows with blank IMO. In the pilot: **18 rows**, mostly on-order vessels with placeholder names (`N/B Hudong Zhonghua`, `N/B HD Hyundai Samho`).

**Do not auto-fuzzy-match these.** Per §4.7 below, automated fuzzy joins on `(builder, owner, delivery year)` produce silent errors that are worse than leaving the match manual. Present both lists side-by-side in the workbook so the user can pair them by hand; most will resolve themselves over time as IMO assignments come through and the vessels move into the IMO-keyed buckets on subsequent quarterly runs.

---

## 4. Workflow per reconciliation run

### 4.1 Confirm parameters with the user (§2)

### 4.2 Verify all three input files are present

Confirm the backend export, the SFOC distribution, and the exclusions CSV are all available. Stage the three input files in the repo's `work/` directory (gitignored — the right place for inputs you don't commit); `ls -la ../work/` to check. If any is missing, ask for it — don't proceed with a default. (If you're driving this from a claude.ai chat rather than a local checkout, an uploaded file lands in the session's upload area; copy it into `work/` before running the scripts.)

If the backend CSV is not in `work/` (e.g. user wants you to pull the live version), use `curl -A "Mozilla/5.0"` against the public export URL per [ref]-Fill SOP §3.0. Note in the workbook README which backend snapshot you used (staged-file timestamp vs. fresh pull date).

### 4.3 Load and inspect the schemas

The backend CSV has a non-trivial parsing gotcha: the **first row is a junk integer header (1, 2, 3, ...)** before the real header. Use `pd.read_csv(..., skiprows=1)`. The exclusions CSV has the same structure. The SFOC CSV does not — it has a real header on row 0.

Confirm before joining:
- Backend IMO column: `IMO number`
- SFOC IMO column: `IMO Number` (capital N — different from backend)
- Exclusions IMO column: `IMO number` (matches backend)
- SFOC capacity column: `Capacity (cu m)`
- SFOC hull column: `Hull No`
- SFOC builder column: `Yard` (or similar — check the actual header)

These column names can drift between SFOC distributions; re-derive from the live file header rather than hardcoding.

**Treat IMO as string everywhere.** Float coercion turns synthetic IMOs like `1157109` into `1.157109e6` and silently breaks the join. `dtype=str` on every pd.read_csv call.

### 4.4 Build the four buckets (§3)

Set-based IMO comparisons, then split Bucket 2 by capacity and Bucket 5 by exclusions-list membership:

```python
b_imo = set(backend["IMO number"].dropna())
s_imo = set(sfoc["IMO Number"].dropna())
excl_imo = set(excl["IMO number"].dropna())

matched = backend[backend["IMO number"].isin(s_imo)]                  # Bucket 1
only_sfoc = sfoc[sfoc["IMO Number"].notna() & ~sfoc["IMO Number"].isin(b_imo)]
candidates = only_sfoc[~only_sfoc["IMO Number"].isin(excl_imo)]       # Bucket 2 (filtered)
already_excluded = only_sfoc[only_sfoc["IMO Number"].isin(excl_imo)]  # Bucket 5
only_backend = backend[backend["IMO number"].notna() & ~backend["IMO number"].isin(s_imo)]  # Bucket 3
contradictions = backend[backend["IMO number"].isin(excl_imo)]        # Bucket 4 (should be empty)
no_imo_backend = backend[backend["IMO number"].isna()]
no_imo_sfoc = sfoc[sfoc["IMO Number"].isna()]
```

### 4.5 Optional: backfill Hull number into the backend

If the user opts in (or if it's the standing quarterly workflow), populate Hull number on the backend rows in Bucket 1 by copying SFOC's `Hull No` value when present. For Bucket 3 rows (no SFOC match), parse from the backend `Name` field where the pattern clearly encodes a hull number — patterns seen in the pilot:

- `Hull 2709 (SHI)` → `2709`
- `Hull 8276 (Hanwha)` → `8276`
- `Hull Unknown 01 (HSHI)` → None (explicitly unknown, don't parse)
- `Dalian No 1 G175K-16` → `G175K-16`

Insert the new columns right after `Name [ref]`. Leave `Hull number [ref]` **blank** in this workflow — the [ref] needs a publicly-citable URL per Rule A (4.4), and SFOC isn't one per Rule 4.1. The user's standard [ref]-Fill workflow will populate it from CSB or a §6a fallback source on a subsequent batch.

Output: a separate `LNG_carrier_backend_with_hull_numbers.csv` file alongside the reconciliation workbook. In the pilot this populated 1,055 of 1,143 backend rows (1,041 from SFOC, 14 parsed from names).

### 4.6 Apply name normalization before per-field diff (recommended)

The matched-rows diff in Bucket 1 is dominated by cosmetic naming differences:
- `Samsung HI` vs `Samsung Heavy Industries`
- `Hudong-Zhonghua Shipbuilding` vs `Hudong Zhonghua`
- comma-list shipowner formatting differences

Without normalization, 1,036 of 1,046 matched rows show a diff (per the pilot) — most uninteresting. Apply the canonical yard/owner mappings from `normalize.py` and `owner_charterer_map.md` to both sides before comparing. After normalization, the diff list collapses to genuinely substantive disagreements: status mismatches (backend "on order" vs SFOC "in service"), capacity mismatches, delivery year mismatches, builder identity changes (e.g. yard reorganizations).

For the first reconciliation run on a fresh SFOC distribution, it's worth running both: an un-normalized diff to see the noise floor, and a normalized diff for actionable triage.

### 4.7 Do NOT auto-fuzzy-match IMO-less rows

Resist the temptation to fuzzy-join `No_IMO_Backend` against `No_IMO_SFOC` on `(builder, owner, delivery year)`. The shipowner field especially has too many synonyms ("MOL" / "Mitsui OSK Lines", "Mozambique LNG" / "TotalEnergies Mozambique") for fuzzy matching to be safe without a curated synonym table — and the consequences of a silent wrong match (a vessel attributed to the wrong owner in the backend) are worse than the consequences of leaving the rows unpaired.

Present the two no-IMO sheets side-by-side with the columns the user needs to pair them manually: `Name`, `Hull number`, `Status`, `Shipowner`, `Shipbuilder`, `Delivery year`. Most will resolve themselves on subsequent quarterly runs as IMO assignments come through.

If the user explicitly asks for an automated fuzzy match with confidence scores per pairing, that's fine — but it's an opt-in, not a default. Confidence scores below ~0.85 should be presented as "candidate pairings for human review" rather than as automated matches.

### 4.8 Inclusion-criteria spot-checks on Bucket 3

For the "Only in backend" bucket, spot-check at least 5 rows against the inclusion criteria. Failure modes worth catching:
- A vessel that's been converted to FSU (storage-only) but still tagged as active LNG carrier in the backend. SFOC's removal of it from the orderbook is the signal.
- A vessel that was cancelled or decommissioned but not yet status-updated in the backend.
- A small/mid-scale vessel that snuck into the backend but should be on the exclusions list. (Reverse of the normal exclusion direction; rare but worth checking.)

These spot-check findings go into the workbook's `QA_review` section as **backend_status_flags** entries (same convention as Discovery SOP §5.4) — they're not candidate adds, but they're actionable backend updates.

**Before flagging any specific hull as a CSB discrepancy, sweep every page of the yard.** Per [ref]-Fill SOP §6.3, CSB pagination can split a single owner's cluster across pages (not just split by date). And per [ref]-Fill SOP §6.4, CSB renders hyphens inconsistently between fullwidth `－` and ASCII `-` — sometimes mixing both within the same hull series across pages of the same yard. A page-1-only sweep with a hyphen-strict regex can produce false-positive "missing from CSB" findings. Concrete example (2026-05-27): a reconciliation flagged Hull CMHI-282-04 as missing from CSB's CMHI Haimen orderbook, but the hull was actually on page 2, rendered as `CMHI－282-04` with a fullwidth hyphen. Before any §4.8 finding lands in the workbook, paginate fully AND normalize hyphens.

### 4.9 Build the workbook (see §5)

### 4.10 Run recalc.py, then write notes.md and commit the batch directory

Per [ref]-Fill SOP §3.6 and Discovery SOP §4.11, every output workbook gets recalc.py before the batch directory is committed.

---

## 5. Output workbook structure

Written to `batches/<batch-dir>/LNG_carrier_reconciliation.xlsx`. Nine sheets in this fixed order:

### 5.1 `Read_me`
Generated date, SFOC snapshot version, backend snapshot date, exclusions list snapshot date, methodology summary, per-bucket row counts, capacity-cut threshold used (default 50,000 cu m), normalization status (applied / not applied), pause-and-ask trigger findings if any.

### 5.2 `Summary`
A small table: bucket name | row count | what it is | what the user should do. The same content as §3 above, condensed to a quick-orient page.

### 5.3 `Candidates_to_add`
Bucket 2 filtered to ≥ capacity threshold AND not on exclusions list. The actionable candidates. Sort by status (On Order first, then In Service), then by delivery year. Include SFOC's columns the backend would consume on copy-paste (Name, Hull No, Builder/Yard, Shipowner, Capacity, Delivery year, Status, Contract date if present).

Color coding (mirror the candidate-vessels convention in Discovery SOP §5.2):
- **Green fill**: high confidence — SFOC has full identifying data (Hull, Builder, Shipowner all populated)
- **Yellow fill**: incomplete SFOC entry; verify before adding to backend
- **No fill**: synthetic-IMO rows where SFOC has only placeholder data

### 5.4 `Matched_with_diffs`
Bucket 1. Each row: IMO, backend Name, # Diffs, Diffs (semicolon-separated list of `field: backend_value | SFOC_value`). Sort by `# Diffs` descending so the most-disagreement rows surface first. The pilot's headline finding came from the top of this list: backend showed several vessels as `Hull 2640 (SHI)` / `on order` / 2026 that SFOC had as delivered, named, and in service in 2025 — actionable status updates.

If normalization (§4.6) is applied, note that in the column header so the user knows the diffs are post-normalization (i.e. likely substantive rather than cosmetic).

### 5.5 `Backend_only`
Bucket 3. Same column shape as `Matched_with_diffs` but no diff column — the backend row in full plus a `triage_reason` column with the §4.8 spot-check finding when relevant ("possible FSU conversion", "possible cancellation", or blank for "no concern, SFOC snapshot is older").

### 5.6 `Already_excluded`
Bucket 5. Skim-only; mostly validation that the exclusions list is being applied. Flag any definition-disagreement cases (§3.5) in a `review_flag` column.

### 5.7 `Contradictions`
Bucket 4. Should be empty. If non-empty: each row gets the backend record AND the exclusions-list record side-by-side, plus a `recommendation` column ("remove from exclusions" or "remove from backend"). User must resolve before the next reconciliation can be trusted.

### 5.8 `No_IMO_Backend`
The 43-ish backend rows with blank IMO. Columns for manual pairing: `Name`, `Hull number`, `Status`, `Shipowner`, `Shipbuilder`, `Delivery year`. Group visually by Shipowner so charterer-led proposals cluster together.

### 5.9 `No_IMO_SFOC`
The 18-ish SFOC rows with blank IMO. Same columns. Same Shipowner grouping. Paired with §5.8 — the user opens both side-by-side and pairs by hand.

---

## 6. Hard rules

### 6.1 Inherit [ref]-Fill SOP rules where they apply
All rules in [ref]-Fill SOP §4 apply to the reconciliation workbook, especially:
- **§4.1** NEVER cite SFOC as a `[ref]` URL — this includes citations the reconciliation workbook might be tempted to generate (e.g. "source: SFOC dist Q3" for a Hull number backfill). Use SFOC values for the data, leave `[ref]` blank, let the next [ref]-Fill batch supply the URL.
- **§4.7** NEVER overwrite backend values — the reconciliation workbook is informational and additive (candidate adds, status flags, suggested updates); the user decides what to promote into the backend.
- **§4.13 Rule F** Never fill a `[ref]` without a corresponding data value — applies to the optional Hull-number backfill: if Hull number gets populated from SFOC, `Hull number [ref]` stays blank.

§3-series workflow rules also apply to reconciliation QA narrative:
- **§3.8b** QA notes quote only publicly-visible content; paywalled body text is never quoted in a QA_review entry. LNG Prime's editorial entity tag list is a real corroboration signal supporting yellow confidence per §5, not green. This rule applies to every reconciliation finding that references a trade-press URL (status updates, charterer corroborations, FSU-conversion flags, etc.) — see [ref]-Fill SOP §3.8b for the full text and rationale.

### 6.2 The exclusions list is authoritative
When SFOC and the exclusions list disagree on a vessel's type or status (e.g. SFOC says "LNG carrier", exclusions list says "bunkering"), the exclusions list wins for the purpose of this reconciliation. Flag the disagreement in the `Already_excluded` sheet's `review_flag` column so the user can resolve it, but don't promote the vessel into `Candidates_to_add` while the disagreement is unresolved.

### 6.3 Capacity threshold is a heuristic, not a rule
The 50,000 cu m cut for splitting Bucket 2 is a working heuristic to separate conventional carriers from small/mid-scale. It is not from the project description and not from any authoritative source. Spot-check the rows that land just above the threshold (50,000–80,000 cu m) — the conventional/mid-scale boundary lives in this range and miscategorization is plausible. Mention the threshold in the README so the user knows it's adjustable.

### 6.4 Backend wins on status by default
For per-field reconciliation precedence (Bucket 1 `Matched_with_diffs`), the default convention is:
- **Backend wins on status** (the project does active research; backend status reflects current information)
- **SFOC wins on hull numbers** (backend doesn't carry them; SFOC is closer to shipyard records)
- **SFOC wins on contract dates** (backend doesn't carry them; SFOC is closer to shipyard records)
- **Most-recent `Last updated` wins for capacity and price** (either side may have updated specs)

These are recommendations for the user reviewing the diffs, not auto-applied overrides. The workbook never modifies the backend.

### 6.5 Synthetic IMOs are part of the join, not noise
Both backend and SFOC use the `11xxxxx` IMO convention for on-order vessels without real IMO assignments. The IMO-set comparison includes them. A synthetic-IMO match between backend and SFOC is a real match (same on-order vessel, same placeholder ID); a synthetic-IMO row only in SFOC is a real candidate add. Don't filter them out as "not real IMOs."

Note in the workbook README that the `11xxxxx` pattern is a synthetic-IMO convention, since a casual reader of the backend might mistake them for real IMOs.

### 6.6 Do not silently fuzzy-match
Per §4.7. If the user later opts in to fuzzy matching for IMO-less rows, treat anything below ~0.85 confidence as a "candidate pairing for human review", never as an automated match.

---

## 7. Pause-and-ask triggers

Stop and ask the user before proceeding when:

- The exclusions list is not provided. Don't run the reconciliation with a default-empty exclusions set — the resulting `Candidates_to_add` bucket will be full of small/mid-scale vessels the user has already deliberately excluded, and the user may treat the workbook as low-quality and lose trust in the workflow.
- The SFOC IMO column header isn't `IMO Number` (or the backend's isn't `IMO number`). Header drift between SFOC distributions is plausible; fail loudly rather than silently producing an empty match.
- Bucket 4 (`Contradictions`) is non-empty. A vessel in both the backend and the exclusions list is a sign that one of the two lists is wrong; flag to the user before producing the workbook so they can resolve it first.
- Bucket 2 (`Candidates_to_add`) has more than ~80 rows above the capacity threshold. The 2026-05-22 pilot found 47; substantially higher than that may indicate the backend has fallen meaningfully behind SFOC and discovery work has lapsed. The reconciliation is still valid, but the user should know it's a bigger-than-expected catch-up batch.
- More than ~10% of matched rows (Bucket 1) have ≥3 post-normalization diffs. Indicates a systematic schema drift between SFOC and backend conventions — e.g. SFOC reclassified a yard, or status taxonomy changed.
- The SFOC snapshot is older than the previous SFOC distribution the user has on hand. (Yes — confirm distribution dates; reconciling against a stale SFOC pull is worse than not reconciling.)

---

## 8. Operational tips

**Start with the IMO sets to size the work.** Before any field-level diffing or workbook scaffolding, print the counts: `len(matched)`, `len(only_sfoc)` split by capacity, `len(only_backend)`, `len(no_imo_backend)`, `len(no_imo_sfoc)`. This gives you and the user a one-line picture of whether this reconciliation is small (mostly maintenance) or large (substantial catch-up).

**Synthetic-IMO matches confirm SFOC and backend share an upstream convention.** When the IMO join produces many `11xxxxx` matches, that's actually evidence the two files are in sync on on-order tracking, not noise. The 2026-05-22 pilot found this convention working well enough that the IMO join covered most pre-build ships without falling back to fuzzy matching.

**The matched-rows diff is where the headline findings hide.** The "candidates to add" bucket is the easy story to tell ("SFOC has N vessels we don't"), but the matched-rows diff often surfaces more actionable work: status updates (on-order → in-service), delivery-year revisions, capacity corrections. Sort by `# Diffs` descending and look at the top 10–20.

**Definition disagreements between SFOC and the exclusions list are real signal.** The 2026-05-22 pilot found two: *Maran Gas Efessos* (bunkering vs. regular LNG Carrier) and *Karadeniz LNGT Powership Oceania* (FSRU vs. FSU). These usually don't change the candidate list (the exclusions list wins by §6.2), but they're worth flagging because they often reflect real boundary cases the user should resolve once rather than re-litigating every quarter.

**Compose this SOP with Discovery.** A standard quarterly cycle is: (1) reconcile against fresh SFOC distribution, producing this workbook; (2) run Discovery against the post-SFOC-cutoff window to catch what landed after SFOC's snapshot. The two workbooks together represent the full update for the quarter. If only one is run, note in the README which gap is uncovered.

**The backend has structural gaps SFOC fills.** Two columns the backend doesn't carry that SFOC does — and that are materially relevant to the tracker:
- **Hull number** (covered by the optional §4.5 backfill)
- **Contract date** (relevant to the on-order/proposed distinction in the inclusion criteria)

Each quarterly reconciliation is an opportunity to surface these gaps. The §4.5 backfill addresses Hull; a similar Contract-date backfill could be added if the user wants it.

---

## 9. Changelog

- **rev 1** (2026-05-26): Initial SOP, formalized from the 2026-05-22 pilot reconciliation that produced `LNG_carrier_reconciliation.xlsx` against the SFOC dist Q3 (updated 26-May) snapshot. Four-bucket model (Matched / Only-in-SFOC / Only-in-backend / Contradictions) plus Already-excluded plus the two IMO-less sheets, with the 50,000 cu m capacity cut as a working heuristic and the optional Hull-number backfill from §4.5. Pilot bucket counts captured throughout as anchor values for future runs to compare against.
- **rev 2** (2026-05-27): Added CSB-sweep guardrail to §4.8 — before any specific hull lands in the workbook as a CSB discrepancy, sweep every page of the yard AND normalize fullwidth `－` (U+FF0D) and ASCII `-` (U+002D) hyphens. Surfaced by the 2026-05-27 false-positive on Hull CMHI-282-04 (Celsius Shipping at CMHI Haimen), which appeared missing from page 1 but was on page 2 rendered with a fullwidth hyphen. The authoritative CSB navigation rules now live in [ref]-Fill SOP §6.3 (pagination) and §6.4 (hyphen normalization) as of [ref]-Fill rev 14; this SOP cross-references them rather than restating. No structural changes to buckets or workbook.
- **rev 3** (2026-05-27): Added §3.8b cross-reference to §6.1 — reconciliation QA findings (F-series entries) quote only publicly-visible content; paywalled body text is never quoted; LNG Prime editorial entity tags support yellow confidence per §5, not green. Surfaced by a 2026-05-27 F8 reconciliation finding that quoted paywalled LNG Prime body text where the verifier could only see the public lead and the tag list — the underlying Woodside attribution was correct, but the quoted body sentence was unverifiable and on its face indistinguishable from fabrication. Same finding drove [ref]-Fill SOP rev 15 (where §3.8b was added as the authoritative rule) and Discovery SOP rev 5.
- **rev 4** (2026-05-28): Repository migration. Output model changed from `/mnt/user-data/outputs/` to one committed directory per reconciliation run under `batches/` (§2 param 5, §5). §4.2 updated to note input files may be staged in the repo `work/` directory as well as uploaded. §4.10 `present_files` reference replaced with "write notes.md and commit the batch directory." No reconciliation-rule changes — the four-bucket model, capacity cut, normalization mapping, and nine-sheet structure are unchanged from rev 3.
- **rev 5** (2026-06-04): Completed the input-side migration. §4.2 and §2 now stage the three input files in the repo `work/` directory; removed the residual claude.ai-sandbox path `/mnt/user-data/uploads/` and its `ls -la /mnt/user-data/uploads/` check (meaningless on a cloned local repo), replacing them with `work/` and an `ls -la ../work/` check plus a parenthetical for the claude.ai-chat case. Surfaced by a clone-and-replicate readiness audit. Path-only edit — no reconciliation-rule changes.
