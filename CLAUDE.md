# LNG Carrier Tracker — Claude Code instructions

This file is read automatically at the start of every Claude Code session in this repo. It's the workflow router. The actual rules live in `docs/sops/`.

## Repository orientation

- `docs/sops/ref_fill.md` — the [ref]-fill workflow, hard rules (A through F), confidence labels, conflict handling, the §3.8 verification gate. **Authoritative.**
- `docs/sops/discovery.md` — the discovery workflow, the four-ring source model, candidate workbook structure. **Authoritative.**
- `docs/sops/data_fill.md` — the data-fill workflow (research blank/`unknown` data cells → candidate value+[ref] pairs; the blank-vs-`unknown` preserve-ref contract, derivable autofills, controlled vocab). **Authoritative.**
- `docs/sops/sfoc_reconciliation.md` — the SFOC reconciliation workflow (less frequent).
- `docs/sops/fsru_reconciliation.md` — the **FSRU reconciliation** workflow: name-keyed comparison of the backend's FSRUs against the GIIGNL Annual Report fleet table (GIIGNL has no IMO → join by name; comparison artifact, not a citable `[ref]`). **Authoritative.**
- `docs/sops/qc_release.md` — the **pre-release QC** workflow: whole-backend consistency/corruption sweep before a data release, the authoritative Name-column placeholder conventions, and the `fix`-mode correction batch (incl. the `preserve_ref` escape hatch). **Authoritative.**
- `docs/sops/apply.md` — the **apply & verify** workflow: getting a reviewed batch's accepted proposals back into the backend, offset-proof and verified (digest → decisions → apply_rows/apply_patch → verify). **Authoritative.**
- `docs/pointers.md` — "which SOP section governs X" index.
- `docs/inclusion_criteria.md` — what's in scope vs out.
- `data/csb_yard_urls.md` — stable ChinaShipBuild yard URLs.
- `data/owner_charterer_map.md` — canonical owner names and variants (human-readable companion to `scripts/normalize.py`).
- `data/source_roster.md` — source tier list for picking corroboration URLs.
- `scripts/` — the Python tooling.
- `batches/` — per-batch outputs, one directory per batch.

## Before any batch

1. View both relevant SOPs end-to-end. Note the current rev numbers in the `Last revised:` line at the top of each.
2. Check `docs/pointers.md` for the rule-to-section lookup map.
3. If SOP cross-references look inconsistent (Discovery SOP citing a [ref]-Fill SOP rev older than the current one), flag to the user before proceeding.
4. Pull a fresh backend CSV — **mandatory first step** ([ref]-Fill SOP §3.0). The user edits the backend between batches.
5. Run the backend QC sanity check on the fresh pull — `python scripts/qc_backend.py`. It flags column-offset / misplaced-value corruption (a controlled value in the wrong column, a data value in a `[ref]`, lat/lon out of range, a URL in a value column, orphan refs). Advisory by default; review `work/qc_report.csv` and surface anything in the batch's scope to the user before building.

## Workflow router

### [ref]-fill batch

Trigger phrases: "fill refs for rows X to Y", "[ref]-fill batch", "next batch", "redo batch N", "rebuild rows X-Y".

```bash
# Run from the repo root (paths.py anchors work/ to the repo root regardless of
# cwd; the build/recalc paths below are root-relative). This also matches the
# `Bash(python scripts/*)` allow rule in .claude/settings.json.

# 1. Fresh backend CSV + column-index map
python scripts/pull_backend.py
# -> work/backend.csv + work/backend.colmap.json
# Re-derive the column map EVERY run. Schema drifts.

# 2. Identify fillable [ref] cells (Rule F: blank [ref] paired with FILLED data value).
# 3. Cluster rows by (yard, owner, contract month) — [ref]-Fill SOP §3.2.
#    Watch for cluster splits within the same owner/yard when contract dates
#    or delivery years diverge ([ref]-Fill SOP §4.12 Rule E rev 6 extension).

# 4. For each yard in batch:
python scripts/csb_fetch.py <yard-slug>
# -> work/csb/<yard>.json. Slugs are in data/csb_yard_urls.md.

# 5. For hulls not on CSB: §6a fallback (targeted Google search ->
#    DART/KIND -> class society -> vessel database -> §6a.8 IMO-tracker ->
#    §6a.9 negative-result log).
python scripts/imo_tracker.py <imo>  # only at §6a.8, the LAST step before negative result

# 6. Trade press / regulatory searches per [ref]-Fill SOP §3.4.
#    Pick sources via data/source_roster.md.

# 7. URL verification gate — Rule D §4.11. EVERY url before it goes in the xlsx.
python scripts/url_verifier.py <url> <expected1> <expected2> ...

# 8. Build the workbook.
python scripts/build_workbook.py --mode ref_fill --rows X-Y \
  --citations citations.json \
  --out batches/<date>_rows_X-Y/

# 9. Recalc - zero formula errors required.
python scripts/recalc.py batches/<date>_rows_X-Y/lng_carrier_backend_ref_fill.xlsx

# 10. Write batches/<date>_rows_X-Y/notes.md
#     (conflicts flagged, defects corrected, escalations, Drive link)

# 11. Commit the batch directory. Do NOT push without user approval.
```

### Discovery batch

Trigger phrases: "find new vessels", "discovery run", "gap analysis", "what's missing from the backend", "catch-up sweep".

```bash
# Run from the repo root (paths.py anchors work/ to the repo root regardless of
# cwd; the build/recalc paths below are root-relative). This also matches the
# `Bash(python scripts/*)` allow rule in .claude/settings.json.

# 1. Confirm parameters per Discovery SOP §2:
#    - Gap window (latest contract date in backend -> today)
#    - Yard coverage (seven main / all-yards)
#    - Proposed-bucket threshold
#    - FSRU handling
#    - Output naming
#    DO NOT skip this. Discovery is sensitive to scope choices.

# 2. Fresh backend CSV, extract rows in gap window as baseline coverage.
python scripts/pull_backend.py

# 3. Build the two dedup indexes.
python scripts/dedup_index.py

# 4. Ring A - CSB on each yard in scope.
python scripts/csb_fetch.py <yard-slug>

# 5. Ring B - regulatory sweep (DART / KIND / Bursa / HKEX).
#    Use English proxies (en.sedaily.com etc.) by default.

# 6. Ring C - trade press, source_roster.md for tier picks.

# 7. Ring D - charterer programs (only if proposed threshold expanded).

# 8. Cluster, dedup, confidence-label per [ref]-Fill SOP §5 (rev 12 standard).

# 9. URL verification gate.
python scripts/url_verifier.py <url> <expected>...

# 10. Build the candidate workbook.
python scripts/build_workbook.py --mode discovery \
  --candidates candidates.json \
  --out batches/<date>_discovery/

python scripts/recalc.py batches/<date>_discovery/lng_carrier_candidate_vessels.xlsx

# 11. Commit the batch directory.
```

### Data-fill batch

Trigger phrases: "data fill", "fill blank data cells", "fill the blanks for rows X-Y", "propose values for missing cells", "fill missing <column>", "data-fill batch".

```bash
# Run from the repo root (paths.py anchors work/ to the repo root regardless of
# cwd; the build/recalc paths below are root-relative). This also matches the
# `Bash(python scripts/*)` allow rule in .claude/settings.json.

# 1. Fresh backend CSV + colmap (MANDATORY — re-derives scope; schema drifts)
python scripts/pull_backend.py

# 2. Dedup index (cluster_index for the per-cluster fan-out)
python scripts/dedup_index.py

# 3. Derivable autofills + scope + per-cluster research task lists (Data-fill SOP §5-§6)
python scripts/derive_fills.py --since <YYYY-MM-DD>
# -> work/data_fill.json (derivable fills + scope) + work/research_tasks.json

# 4. Research fan-out: one subagent per cluster (Discovery §3 four-ring model,
#    controlled vocab in data/controlled_vocab.md, owner stylization §4.14,
#    PRESERVE existing refs on `unknown` cells per Data-fill SOP §4). Reuse prior
#    batches + backend siblings first. Each writes work/research_<label>.json.

# 5. Merge + central §3.8 verification gate.
python scripts/merge_fills.py   # -> work/data_fill.json (merged, deduped, re-verified)

# 6. Build the candidate workbook.
python scripts/build_workbook.py --mode data_fill \
  --fills work/data_fill.json \
  --out batches/<date>_data_fill_rows_X-Y/

# 7. Recalc - zero formula errors required.
python scripts/recalc.py batches/<date>_data_fill_rows_X-Y/lng_carrier_data_fill.xlsx

# 8. Copy work/data_fill.json into the batch dir; write notes.md; commit the
#    batch directory. Do NOT push without user approval.
```

### SFOC reconciliation batch

Trigger phrases: "SFOC reconciliation", "reconcile against SFOC", "reconcile the backend against the new SFOC dataset", "SFOC pass".

Less frequent and script-light — there's no fixed scriptchain here. Follow
`docs/sops/sfoc_reconciliation.md` end-to-end (rev 5): stage the three input
files in `work/`, run the four-bucket reconciliation (with the capacity cut and
the normalization mapping), build the nine-sheet workbook, recalc to zero
formula errors, and commit the batch directory under `batches/`. The SOP is
authoritative. Close the pass with a full-backend dedupe scan
(`python scripts/dedupe_check.py` -> `work/dedupe_report.csv`; apply.md §5a).

### FSRU reconciliation batch

Trigger phrases: "FSRU reconciliation", "compare FSRUs to GIIGNL", "reconcile FSRUs against the GIIGNL report", "how complete is our FSRU coverage", "FSRU gap analysis".

Governed by `docs/sops/fsru_reconciliation.md` (FR rev 1). Name-keyed comparison of the
backend's FSRUs against the GIIGNL Annual Report fleet table — GIIGNL has no IMO column, so
the join is by vessel name ({current} ∪ {ex_names}, `normalize_vessel_name`) corroborated by
storage capacity (builder is informational — conversion yard ≠ original builder). GIIGNL is a
**comparison artifact, not a citable `[ref]`** (like SFOC). The backend is never auto-edited;
vetted candidates promote through the Apply SOP.

```bash
# Run from the repo root.

# 1. Fresh backend CSV + colmap (MANDATORY first step).
python scripts/pull_backend.py

# 2. Extract the GIIGNL fleet table — REUSE the terminals repo parser (don't rebuild).
python ../lng-terminals-researcher/scripts/giignl_fsru_fleet.py \
    data/GIIGNL-<year>-Annual-Report-<ver>.pdf --output work/giignl_fsru_fleet.json

# 3. Reconcile (name join + capacity corroborator + five buckets).
python scripts/fsru_reconcile.py        # -> work/fsru_reconcile.json

# 4. Build the 10-sheet reconciliation workbook + recalc to zero errors.
python scripts/build_workbook.py --mode fsru --reconcile work/fsru_reconcile.json \
    --out batches/<date>_<HHMMET>_fsru_reconciliation_giignl<year>/
python scripts/recalc.py batches/<dir>/lng_carrier_fsru_reconciliation.xlsx

# 5. Advisory dedupe sweep; copy fsru_reconcile.json into the batch dir; write
#    notes.md; commit the batch directory. Do NOT push without user approval.
python scripts/dedupe_check.py          # -> work/dedupe_report.csv (apply.md §5a)
```

### Pre-release QC batch

Trigger phrases: "qc pass", "pre-release qc", "qc the backend", "prep for data release", "check the names before release", "name consistency check".

Governed by `docs/sops/qc_release.md` (QC rev 1). A whole-backend consistency/corruption
sweep before a data release; mechanical defects get packaged as a `fix`-mode batch and
routed through the Apply SOP.

```bash
# Run from the repo root.

# 1. Fresh backend CSV + colmap (MANDATORY first step).
python scripts/pull_backend.py

# 2. Full-backend QC scan (no --rows — release pass is whole-sheet).
python scripts/qc_backend.py          # -> work/qc_report.csv ; --strict to gate
#   Triage by check (QC §3): column-offset / misplaced-vocab / url-in-value / bad-shape
#   (corruption — escalate); orphan-ref / lookup-mismatch (MED); name-builder-drift /
#   name-ordinal-gap (LOW — the Name-column consistency checks, QC §2). Confirm the
#   canonical target form with the user before any mass rename.

# 3. Mechanical corrections -> fix.json (keyed by row_id). For cosmetic / derived-value
#    edits (e.g. placeholder Name normalization) set preserve_ref:true on the cell so the
#    value is rewritten but the paired [ref] is preserved and the §3.8c gate is skipped
#    (QC §4). Sourced value corrections supply refs and pass the gate as usual.
python scripts/build_workbook.py --mode fix --fix work/<name>_fix.json \
  --out batches/<date>_<HHMMET>_<label>/
python scripts/recalc.py batches/<date>_<HHMMET>_<label>/lng_carrier_fix.xlsx

# 4. Copy fix.json into the batch dir, write notes.md, commit the batch directory.
#    Apply via the Apply SOP unchanged. Release gate: re-pull + re-run qc_backend.py;
#    clear when HIGH/MED are resolved/allowlisted and the Name checks are at zero.
```

### Apply a reviewed batch

Trigger phrases: "apply batch", "incorporate batch X", "get this batch into the backend", "review and apply", "verify the apply".

Governed by `docs/sops/apply.md` (AP rev 1). This is the offset-proof round-trip that
replaces manual copy/paste (which corrupted rows 1216/1217).

```bash
# 1. Triage — split auto-safe vs needs-a-decision.
python scripts/batch_digest.py --batch batches/<dir>          # -> digest.md

# 2. Decisions + apply artifacts. First run pre-fills decisions.csv by confidence;
#    edit the holds, then re-run to finalize.
python scripts/apply_batch.py --batch batches/<dir>
#   -> decisions.csv, apply.json, apply_rows.csv, apply_patch.csv, conflicts.csv

# 3. Apply (offset-proof, pick one): paste apply_rows.csv full rows over matching
#    backend rows, OR run tools/apply_patch.gs on apply_patch.csv (by-name, DRY_RUN first).

# 4. Verify — re-pull and confirm everything landed. Also runs the dedupe sweep
#    (apply.md §5a) over touched/added rows -> <dir>/dedupe_report.csv (advisory).
python scripts/verify_apply.py --batch batches/<dir> --pull   # -> verify_report.csv
```

Conflicts (research vs a non-blank backend value) go to `conflicts.csv` and are decided
by hand — never auto-applied (additive-to-blanks holds). Review any HIGH/MED group in
`dedupe_report.csv` before calling the batch done — a newly-added row may duplicate an
existing vessel (apply.md §5a). Run standalone any time: `python scripts/dedupe_check.py`.

## Hard requirements (these override anything below)

- **Never modify the backend CSV directly.** Outputs are always candidate xlsx files for human review ([ref]-Fill SOP §4.7). The backend lives in Google Sheets and is human-edited.
- **Every URL passes §3.8 before going in the xlsx.** No exceptions, even for URLs that worked in prior batches — URLs decay.
- **Never cite GEM as a data source** — this includes `gem.wiki` and any other GEM-published page or dataset, as a `[ref]` URL or as corroboration ([ref]-Fill SOP §4.2; Forbidden lists in `docs/sops/ref_fill.md` and `data/source_roster.md`). GEM is downstream of this tracker, so citing it would be circular.
- **Rule F applies always** — no orphan `[ref]` cells with no paired data value ([ref]-Fill SOP §4.13).
- **Data-fill is additive to blanks/`unknown`s only.** It proposes value + verified-`[ref]` pairs for human review, never a backend edit; existing `[ref]` URLs on `unknown` cells are appended to, never replaced (Data-fill SOP §4, §9).
- **Always pull fresh backend CSV at the start of a batch.**
- **Re-derive the column-index map** from the fresh header row — don't assume schema is stable.
- **Never `git push` without explicit user approval.** Local commits are fine; pushing to a public repo is irreversible.
- **Never commit** files containing credentials, API keys, or anything in `work/` (gitignored).

## When to escalate

Per [ref]-Fill SOP §11 and Discovery SOP §7, pause and ask the user when:

- CSB is broken AND §6a fallback exhausted without success on at least one cluster
- A whole class of backend values looks systematically wrong
- A new rule would invalidate prior batches
- Source corroboration is too thin to support even yellow even after §6a fallback
- Discovery surfaces more than ~5 candidate clusters in the same gap window (suggests systematic gap, not normal leading-edge lag)
- The gap window is unclear (no clear "latest contract date" in backend, multiple recent rows with blank contract dates)

## Scripts — what each does and when to read its source

| Script | Purpose | Read source when |
|---|---|---|
| `pull_backend.py` | curl + parse CSV, derive column-index map from header row | Schema changed; column indices look wrong |
| `qc_backend.py` | backend QC sanity check — column-offset / misplaced-value detection + Name-column consistency (`name-builder-drift`, `name-ordinal-gap`; QC §2) (`work/qc_report.csv`; `--strict`, `--rows`) | New column-shape rule; a false positive/negative; new check |
| `lookups.py` | data loaders: `CONTROLLED_VOCAB` (shared by build + QC) + builder/owner facts tables | Adding a vocab value; changing the facts-table schema |
| `seed_lookups.py` | seed/refresh `data/shipbuilder_facts.csv` + `shipowner_facts.csv` from the live backend | New yard/owner to capture; re-deriving facts after backend edits |
| `normalize.py` | canonical builder/owner names (module, imported by others) | Adding a new yard or owner; clusters over- or under-merging |
| `dedup_index.py` | builds the two indexes used for matching candidates against backend | New batch type that needs a different index shape |
| `fsru_reconcile.py` | FSRU reconciliation: name-keyed join of the GIIGNL fleet JSON ({current}∪{ex_names}, `normalize_vessel_name`) against backend FSRUs, capacity-corroborated; emits the five-bucket `work/fsru_reconcile.json` (matched / reclassify / manual / candidates / backend_only + FSU exclusions + orderbook). Advisory; never edits the backend | New bucket; changing the capacity tolerance or small-scale cutoff; manual-pairing guard tuning |
| `csb_fetch.py` | curl chinashipbuild.com with the right UA, parse orderbook table | CSB layout changed; new yard added; parser returning fewer rows than expected |
| `url_verifier.py` | the §3.8 verification gate — HTTP 200 + content check + soft-error detection | Verifier flagging false positives or negatives; new soft-error pattern |
| `imo_tracker.py` | the §6a.8 IMO->marine-vessel-tracker fallback | marinetraffic.org URL pattern changed; Cloudflare gating |
| `build_workbook.py` | xlsx scaffolding — sheets, color fills, frozen panes, headers (modes: ref_fill / discovery / data_fill / fix / fsru). `fix` mode rebuilds corrected full rows from a `fix.json` (optionally `--base <corrected_rows.csv>`) and runs every ref through the §3.8c value↔ref corroboration gate (drops refs that don't contain the cell value); a cell may set `preserve_ref:true` for cosmetic/derived edits (rewrite value, keep the paired `[ref]`, skip the gate). `fsru` mode renders the `work/fsru_reconcile.json` buckets into a 10-sheet GIIGNL↔backend comparison workbook (no `[ref]` cells — GIIGNL not citable) | Adding a new sheet section; changing color convention; changing fix-mode gating; changing the fsru sheet set |
| `derive_fills.py` | data-fill: select in-scope rows, compute derivable autofills, list per-cluster research targets | New derivable column; changing the row-selection filter |
| `merge_fills.py` | data-fill: merge per-cluster research outputs + run the central §3.8 re-verify gate | Verifier behavior changes; new research-output key |
| `recalc.py` | open the xlsx, force recalc, return any formula errors | Always run before committing the batch |
| `batch_digest.py` | triage a batch into auto-safe vs needs-a-decision (`digest.md`) | Changing the triage split or digest format |
| `apply_batch.py` | reviewed batch → `decisions.csv` + offset-proof apply artifacts (`apply_rows.csv`, `apply_patch.csv`, `apply.json`, `conflicts.csv`) | New batch mode; changing the patch/decision schema |
| `verify_apply.py` | re-pull + diff backend vs `apply.json` (landed/mismatch/missing) + qc the touched rows + dedupe sweep over touched/added rows | Changing match logic; new verify check |
| `dedupe_check.py` | internal duplicate scan — tiered (IMO/builder+hull → HIGH; placeholder↔identified on builder+owner+capacity+delivery → MED; distinct ordinals → LOW sister ships). Advisory; `work/dedupe_report.csv` (reports lead with **live sheet row**, not the column-A `row_id`); `--rows`, `--sheet-rows`, `--strict` (apply.md §5a) | New dup signal/tier; a false positive/negative; new disqualifier |

Trust the scripts by default. They're versioned scaffolding, not throwaway code. If you fix one, commit the fix in the same batch with a note in `notes.md`.

## Working directory convention

Scratch artifacts (intermediate CSVs, cached CSB JSON, draft citation JSON) go in `work/`, which is gitignored. The only things that get committed from a batch are the contents of `batches/<date>_rows_X-Y/`.
