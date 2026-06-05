# LNG Carrier Tracker — Claude Code instructions

This file is read automatically at the start of every Claude Code session in this repo. It's the workflow router. The actual rules live in `docs/sops/`.

## Repository orientation

- `docs/sops/ref_fill.md` — the [ref]-fill workflow, hard rules (A through F), confidence labels, conflict handling, the §3.8 verification gate. **Authoritative.**
- `docs/sops/discovery.md` — the discovery workflow, the four-ring source model, candidate workbook structure. **Authoritative.**
- `docs/sops/data_fill.md` — the data-fill workflow (research blank/`unknown` data cells → candidate value+[ref] pairs; the blank-vs-`unknown` preserve-ref contract, derivable autofills, controlled vocab). **Authoritative.**
- `docs/sops/sfoc_reconciliation.md` — the SFOC reconciliation workflow (less frequent).
- `docs/pointers.md` — "which SOP section governs X" index.
- `docs/inclusion_criteria.md` — what's in scope vs out.
- `refdata/csb_yard_urls.md` — stable ChinaShipBuild yard URLs.
- `refdata/owner_charterer_map.md` — canonical owner names and variants (human-readable companion to `scripts/normalize.py`).
- `refdata/source_roster.md` — source tier list for picking corroboration URLs.
- `scripts/` — the Python tooling.
- `batches/` — per-batch outputs, one directory per batch.

## Before any batch

1. View both relevant SOPs end-to-end. Note the current rev numbers in the `Last revised:` line at the top of each.
2. Check `docs/pointers.md` for the rule-to-section lookup map.
3. If SOP cross-references look inconsistent (Discovery SOP citing a [ref]-Fill SOP rev older than the current one), flag to the user before proceeding.
4. Pull a fresh backend CSV — **mandatory first step** ([ref]-Fill SOP §3.0). The user edits the backend between batches.

## Workflow router

### [ref]-fill batch

Trigger phrases: "fill refs for rows X to Y", "[ref]-fill batch", "next batch", "redo batch N", "rebuild rows X-Y".

```bash
cd scripts/

# 1. Fresh backend CSV + column-index map
python pull_backend.py
# -> ../work/backend.csv + ../work/backend.colmap.json
# Re-derive the column map EVERY run. Schema drifts.

# 2. Identify fillable [ref] cells (Rule F: blank [ref] paired with FILLED data value).
# 3. Cluster rows by (yard, owner, contract month) — [ref]-Fill SOP §3.2.
#    Watch for cluster splits within the same owner/yard when contract dates
#    or delivery years diverge ([ref]-Fill SOP §4.12 Rule E rev 6 extension).

# 4. For each yard in batch:
python csb_fetch.py <yard-slug>
# -> ../work/csb/<yard>.json. Slugs are in refdata/csb_yard_urls.md.

# 5. For hulls not on CSB: §6a fallback (targeted Google search ->
#    DART/KIND -> class society -> vessel database -> §6a.8 IMO-tracker ->
#    §6a.9 negative-result log).
python imo_tracker.py <imo>  # only at §6a.8, the LAST step before negative result

# 6. Trade press / regulatory searches per [ref]-Fill SOP §3.4.
#    Pick sources via refdata/source_roster.md.

# 7. URL verification gate — Rule D §4.11. EVERY url before it goes in the xlsx.
python url_verifier.py <url> <expected1> <expected2> ...

# 8. Build the workbook.
python build_workbook.py --mode ref_fill --rows X-Y \
  --citations citations.json \
  --out ../batches/<date>_rows_X-Y/

# 9. Recalc - zero formula errors required.
python recalc.py ../batches/<date>_rows_X-Y/lng_carrier_backend_ref_fill.xlsx

# 10. Write batches/<date>_rows_X-Y/notes.md
#     (conflicts flagged, defects corrected, escalations, Drive link)

# 11. Commit the batch directory. Do NOT push without user approval.
```

### Discovery batch

Trigger phrases: "find new vessels", "discovery run", "gap analysis", "what's missing from the backend", "catch-up sweep".

```bash
cd scripts/

# 1. Confirm parameters per Discovery SOP §2:
#    - Gap window (latest contract date in backend -> today)
#    - Yard coverage (seven main / all-yards)
#    - Proposed-bucket threshold
#    - FSRU handling
#    - Output naming
#    DO NOT skip this. Discovery is sensitive to scope choices.

# 2. Fresh backend CSV, extract rows in gap window as baseline coverage.
python pull_backend.py

# 3. Build the two dedup indexes.
python dedup_index.py

# 4. Ring A - CSB on each yard in scope.
python csb_fetch.py <yard-slug>

# 5. Ring B - regulatory sweep (DART / KIND / Bursa / HKEX).
#    Use English proxies (en.sedaily.com etc.) by default.

# 6. Ring C - trade press, source_roster.md for tier picks.

# 7. Ring D - charterer programs (only if proposed threshold expanded).

# 8. Cluster, dedup, confidence-label per [ref]-Fill SOP §5 (rev 12 standard).

# 9. URL verification gate.
python url_verifier.py <url> <expected>...

# 10. Build the candidate workbook.
python build_workbook.py --mode discovery \
  --candidates candidates.json \
  --out ../batches/<date>_discovery/

python recalc.py ../batches/<date>_discovery/lng_carrier_candidate_vessels.xlsx

# 11. Commit the batch directory.
```

### Data-fill batch

Trigger phrases: "data fill", "fill blank data cells", "fill the blanks for rows X-Y", "propose values for missing cells", "fill missing <column>", "data-fill batch".

```bash
cd scripts/

# 1. Fresh backend CSV + colmap (MANDATORY — re-derives scope; schema drifts)
python pull_backend.py

# 2. Dedup index (cluster_index for the per-cluster fan-out)
python dedup_index.py

# 3. Derivable autofills + scope + per-cluster research task lists (Data-fill SOP §5-§6)
python derive_fills.py --since <YYYY-MM-DD>
# -> ../work/data_fill.json (derivable fills + scope) + ../work/research_tasks.json

# 4. Research fan-out: one subagent per cluster (Discovery §3 four-ring model,
#    controlled vocab in refdata/controlled_vocab.md, owner stylization §4.14,
#    PRESERVE existing refs on `unknown` cells per Data-fill SOP §4). Reuse prior
#    batches + backend siblings first. Each writes ../work/research_<label>.json.

# 5. Merge + central §3.8 verification gate.
python merge_fills.py   # -> ../work/data_fill.json (merged, deduped, re-verified)

# 6. Build the candidate workbook.
python build_workbook.py --mode data_fill \
  --fills ../work/data_fill.json \
  --out ../batches/<date>_data_fill_rows_X-Y/

# 7. Recalc - zero formula errors required.
python recalc.py ../batches/<date>_data_fill_rows_X-Y/lng_carrier_data_fill.xlsx

# 8. Copy ../work/data_fill.json into the batch dir; write notes.md; commit the
#    batch directory. Do NOT push without user approval.
```

## Hard requirements (these override anything below)

- **Never modify the backend CSV directly.** Outputs are always candidate xlsx files for human review ([ref]-Fill SOP §4.7). The backend lives in Google Sheets and is human-edited.
- **Every URL passes §3.8 before going in the xlsx.** No exceptions, even for URLs that worked in prior batches — URLs decay.
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
| `normalize.py` | canonical builder/owner names (module, imported by others) | Adding a new yard or owner; clusters over- or under-merging |
| `dedup_index.py` | builds the two indexes used for matching candidates against backend | New batch type that needs a different index shape |
| `csb_fetch.py` | curl chinashipbuild.com with the right UA, parse orderbook table | CSB layout changed; new yard added; parser returning fewer rows than expected |
| `url_verifier.py` | the §3.8 verification gate — HTTP 200 + content check + soft-error detection | Verifier flagging false positives or negatives; new soft-error pattern |
| `imo_tracker.py` | the §6a.8 IMO->marine-vessel-tracker fallback | marinetraffic.org URL pattern changed; Cloudflare gating |
| `build_workbook.py` | xlsx scaffolding — sheets, color fills, frozen panes, headers (modes: ref_fill / discovery / data_fill) | Adding a new sheet section; changing color convention |
| `derive_fills.py` | data-fill: select in-scope rows, compute derivable autofills, list per-cluster research targets | New derivable column; changing the row-selection filter |
| `merge_fills.py` | data-fill: merge per-cluster research outputs + run the central §3.8 re-verify gate | Verifier behavior changes; new research-output key |
| `recalc.py` | open the xlsx, force recalc, return any formula errors | Always run before committing the batch |

Trust the scripts by default. They're versioned scaffolding, not throwaway code. If you fix one, commit the fix in the same batch with a note in `notes.md`.

## Working directory convention

Scratch artifacts (intermediate CSVs, cached CSB JSON, draft citation JSON) go in `work/`, which is gitignored. The only things that get committed from a batch are the contents of `batches/<date>_rows_X-Y/`.
