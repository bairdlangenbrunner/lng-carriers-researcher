# LNG Carrier Tracker — Claude Code instructions

This file is read automatically at the start of every Claude Code session in this repo. It's the workflow router. The actual rules live in `docs/sops/`.

## Repository orientation

- `docs/sops/ref_fill.md` — the [ref]-fill workflow, hard rules (A through F), confidence labels, conflict handling, the §3.8 verification gate. **Authoritative.**
- `docs/sops/discovery.md` — the discovery workflow, the four-ring source model, candidate workbook structure. **Authoritative.**
- `docs/sops/data_fill.md` — the data-fill workflow (research blank/`unknown` data cells → candidate value+[ref] pairs; the blank-vs-`unknown` preserve-ref contract, derivable autofills, controlled vocab). **Authoritative.**
- `docs/sops/sfoc_reconciliation.md` — the SFOC reconciliation workflow (less frequent).
- `docs/sops/fsru_reconciliation.md` — the **FSRU reconciliation** workflow: name-keyed comparison of the backend's FSRUs against the GIIGNL Annual Report fleet table (GIIGNL has no IMO → join by name; comparison artifact, not a citable `[ref]`). **Authoritative.**
- `docs/sops/igu_reconciliation.md` — the **IGU reconciliation** workflow: IMO-keyed intercomparison of the whole backend against the IGU World LNG Report fleet + orderbook tables (Appendix 3 / 4), with an edition-to-edition diff; extract every edition fresh (layout changes). IGU is citable, but its landing page cannot pass the §3.8c gate for a new proposal. **Authoritative.**
- `docs/sops/qc_release.md` — the **pre-release QC** workflow: whole-backend consistency/corruption sweep before a data release, the authoritative Name-column placeholder conventions, and the `fix`-mode correction batch (incl. the `preserve_ref` escape hatch). **Authoritative.**
- `docs/sops/apply.md` — the **apply & verify** workflow: getting a reviewed batch's accepted proposals back into the backend, offset-proof and verified (digest → decisions → apply_rows/apply_patch → verify). **Authoritative.**
- `docs/pointers.md` — "which SOP section governs X" index.
- `docs/plans/` — dated plans and state files for multi-batch passes (working notes, not rules). Current: `2026-09-17_sep-17-pass_worklist.md` (what is left to decide / apply / research) and `2026-09-17_sep-17-pass_summary.md`; `2026-09-18_review-app.md` (build spec for the review app that replaces the combined xlsx as the decision surface — lives in `review_app/`; not built yet).
- `docs/inclusion_criteria.md` — what's in scope vs out.
- `data/csb_yard_urls.md` — stable ChinaShipBuild yard URLs.
- `data/owner_charterer_map.md` — canonical owner names and variants (human-readable companion to `scripts/normalize.py`).
- `data/source_roster.md` — source tier list for picking corroboration URLs.
- `scripts/` — the Python tooling.
- `batches/` — per-batch outputs, one directory per batch.
- `../lng-carriers-map` — sibling repo: live FSRU/FSU fleet map (aisstream.io AIS → GitHub Actions cron → GitHub Pages). Its `data/fleet.json` is exported from this repo's `work/backend.csv` via its `tools/export_fleet.py` — re-export after fleet changes.

## Before any batch

1. View both relevant SOPs end-to-end. Note the current rev numbers in the `Last revised:` line at the top of each.
2. Check `docs/pointers.md` for the rule-to-section lookup map.
3. If SOP cross-references look inconsistent (Discovery SOP citing a [ref]-Fill SOP rev older than the current one), flag to the user before proceeding.
4. Pull a fresh backend CSV — **mandatory first step** ([ref]-Fill SOP §3.0). The user edits the backend between batches.
5. Run the backend QC sanity check on the fresh pull — `python scripts/qc_backend.py`. It flags column-offset / misplaced-value corruption (a controlled value in the wrong column, a data value in a `[ref]`, lat/lon out of range, a URL in a value column, orphan refs). Advisory by default; review `work/qc_report.csv` and surface anything in the batch's scope to the user before building.

## Workflow router

### A URL is blocked / 403 / "Just a moment..."

Never conclude anything about a page from WebFetch or a hand-rolled curl. Run it
through the repo's fetch ladder first — `python scripts/fetch.py <url> --head 2000`
(curl → `curl_cffi` TLS impersonation → real-Chrome `cf_clearance` cookie; the notes
line says which route worked). Only a wall the ladder cannot clear grades `blocked`.

Status `000` with connection timeouts on every origin IP is an **IP ban, not a bot
wall** — the host drops us before TLS, so the ladder cannot clear it (no UA,
fingerprint, or cookie matters; this is how a 1 req/s vesselfinder loop ended on
2026-09-17). Do not retry in a loop — that tends to extend the ban. Switch source or
egress, and re-test later with a single request. Bulk sweeps of one host must go
through `python scripts/sweep.py` (per-host pacing + a circuit breaker), never a bare
loop over `fetch_page()`.

### Archiving URLs to the Wayback Machine

Trigger phrases: "archive the refs", "archive all the URLs", "save to Wayback".

Run `python scripts/wayback_save.py` (`--dry-run` first for the count and auth check), in the background. It is already authenticated with Baird's archive.org S3 key (env or keychain), so don't hand-roll `/save/` calls, don't fall back to anonymous Save Page Now, and don't ask for credentials. Budget ~N/6 minutes (≈75 min for the whole backend). Results land in `work/wayback_save.jsonl`; re-running resumes. Whether a snapshot goes into a `[ref]` cell is still ref_fill.md §7 (last resort, live URL dead).

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
#    PRESERVE existing refs on `unknown` cells per Data-fill SOP §4). A price reported
#    only as an order total -> per-vessel Price with `derived_from` (DF §5a: Y max,
#    never `derivable`). Reuse prior
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

### IGU reconciliation batch

Trigger phrases: "IGU reconciliation", "compare the backend to the IGU report", "intercompare with the World LNG Report", "new IGU edition", "what did IGU drop / change".

Governed by `docs/sops/igu_reconciliation.md` (IG rev 2). IMO-keyed join of the **whole
backend** against the IGU World LNG Report's Appendix 3 (fleet) and Appendix 4 (orderbook),
with the previous edition layered on top so each diff says which side moved (`igu_changed` /
`new_to_igu` / `backend_differs` — never revert the last blindly). The backend was seeded from
IGU 2025, so IGU **is** citable on bulk-loaded rows. Its landing page surfaces no per-vessel
value, so cite the **report PDF**, which passes §3.8c. Interim rule (Baird 2026-09-17, IG §5.4):
what IGU 2026 prints is a sufficient sole source, Vessel type included — no second ref for now
(open decision: back these cells up at the ref-validation step?). IGU's *silence* (a dropped
vessel) is not a statement and still needs its own verified ref.
The batch itself is never applied; findings promote through a `fix` / discovery batch.

```bash
# Run from the repo root.

# 1. Fresh backend CSV + colmap (MANDATORY first step).
python scripts/pull_backend.py

# 2. Extract BOTH editions fresh — the table layout changes between editions
#    (2026: two tables per landscape spread, Age + Vessel Type columns added).
#    Read the warnings; the expected residue is IGU's own duplicate IMOs.
python scripts/igu_fleet.py ../lng-terminals-researcher/data/IGU-World-LNG-Report-<year>.pdf
python scripts/igu_fleet.py <path>/IGU-World-LNG-Report-<year-1>.pdf
# -> work/igu_fleet_<year>.json, work/igu_fleet_<year-1>.json

# 3. Reconcile. --pending cross-references un-applied batches (a finding one already
#    proposes is green); --fetch-leads runs the paced shipvault lookup on the review
#    buckets (leads, never refs; resumable work/igu_review_shipvault.json).
python scripts/igu_reconcile.py --pending batches/<dir> [batches/<dir> ...] --fetch-leads
# -> work/igu_reconcile.json

# 4. Build the 11-sheet workbook + recalc to zero errors.
python scripts/build_workbook.py --mode igu --reconcile work/igu_reconcile.json \
    --out batches/<date>_<HHMMET>_igu_reconciliation_igu<year>/
python scripts/recalc.py batches/<dir>/lng_carrier_igu_reconciliation.xlsx

# 5. Advisory dedupe sweep; copy both igu_fleet JSONs, igu_reconcile.json and the leads
#    file into the batch dir; write notes.md (decisions list); commit the batch directory.
python scripts/dedupe_check.py          # -> work/dedupe_report.csv (apply.md §5a)
```

Dropped vessels (IG §5.2): **rows are never deleted from the backend.** A scrapped vessel keeps
its row and moves to Status `scrapped` (vocabulary value added 2026-09-17) via a `fix` batch, with
a verified ref for the demolition sale — whichever side of December 2025 the scrapping falls.

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
python scripts/other_names.py --batch work/<name>_fix.json   # RF §4.16: former Names -> Other names
python scripts/build_workbook.py --mode fix --fix work/<name>_fix.json \
  --out batches/<date>_<HHMMET>_<label>/
python scripts/recalc.py batches/<date>_<HHMMET>_<label>/lng_carrier_fix.xlsx

# 4. Copy fix.json into the batch dir, write notes.md, commit the batch directory.
#    Apply via the Apply SOP unchanged. Release gate: re-pull + re-run qc_backend.py;
#    clear when HIGH/MED are resolved/allowlisted and the Name checks are at zero.
```

### Apply a reviewed batch

Trigger phrases: "apply batch", "incorporate batch X", "get this batch into the backend", "review and apply", "verify the apply".

Governed by `docs/sops/apply.md` (AP rev 4). This is the offset-proof round-trip that
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
#    Several un-applied batches sharing rows -> patch path only: full rows are a snapshot and
#    revert each other; OVERWRITE_NONBLANK=true for fix / ref-append batches (AP §2a).

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
- **Never propose deleting the row of a vessel that leaves service.** It keeps its row and changes Status — a scrapped vessel moves to `scrapped` (Baird directive 2026-09-17; `docs/inclusion_criteria.md`, IG §5.2). The inclusion criteria govern what gets *added*. **The rule does not extend to duplicates** (Baird 2026-09-17): the same vessel entered twice is not a vessel leaving the fleet, and the duplicate row *is* removed — flag it (dedupe sweep, apply.md §5a), and Baird deletes it by hand in the sheet, carrying a placeholder name worth keeping into the surviving row's `Other names` (as with `Woodside Energy 01`–`03` → the Seapeak rows).
- **Every URL passes §3.8 before going in the xlsx.** No exceptions, even for URLs that worked in prior batches — URLs decay.
- **Never cite GEM as a data source** — this includes `gem.wiki` and any other GEM-published page or dataset, as a `[ref]` URL or as corroboration ([ref]-Fill SOP §4.2; Forbidden lists in `docs/sops/ref_fill.md` and `data/source_roster.md`). GEM is downstream of this tracker, so citing it would be circular.
- **Banned source: abarrelfull** (`abarrelfull.wikidot.com`, `abarrelfull.co.uk`) — never use it as a reference, ever, even corroborated; it must not appear in any output or lane (Baird directive 2026-07-17, all GEM researcher projects). Chase the primary source it footnotes and cite that.
- **A proposed Name change carries the former Name into `Other names`** ([ref]-Fill SOP §4.16, Baird directive 2026-09-17): appended with `"; "`, never replacing what is there; a hull placeholder counts as a former name; spelling / truncation corrections, a name that belongs to another row, and placeholder → placeholder restylings do not. Run `python scripts/other_names.py --batch <dir>` on any fix batch with Name cells before building it; the `Other names` line is decided together with its Name line.
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
| `igu_fleet.py` | IGU World LNG Report extractor — Appendix 3 (fleet) + Appendix 4 (orderbook) from pdfplumber **word coordinates**, assuming nothing about the column set (each `IMO Number` header starts a table; column edges come from the header labels; wrapped lines attach to the row above), so it survives the edition-to-edition layout changes (two tables per spread, added columns). Built-in validation (IMO check digit, numeric capacity, plausible year, per-page IMO-token cross-count) → `warnings`; `--strict` exits 1. Writes `work/igu_fleet_<edition>.json` | A new edition's header label is unmapped (`FIELD_BY_LABEL`); the acceptance check (IG §3) does not balance; a page's count cross-check warns |
| `igu_reconcile.py` | IGU reconciliation: IMO-keyed join of the IGU fleet + orderbook JSON against the whole backend, previous edition layered on (`kind`: igu_changed / new_to_igu / backend_differs), builder labels compared through a learned co-occurrence map, capacity within max(6000, 3%). Buckets: matched (field diffs + status findings) / dropped / backend_not_in_igu / igu_only / igu_no_imo (cluster-level hints only) / igu_duplicates / edition_diff. `--pending <batch dirs>` marks findings an un-applied batch already proposes; `--fetch-leads` = paced, resumable shipvault lookup of the review buckets (`work/igu_review_shipvault.json`; leads, never refs). Advisory; never edits the backend | New bucket or diff kind; tuning the builder-pair threshold or capacity tolerance; a new review bucket for leads |
| `csb_fetch.py` | curl chinashipbuild.com with the right UA, parse orderbook table | CSB layout changed; new yard added; parser returning fewer rows than expected |
| `url_verifier.py` | the §3.8 verification gate — citable-shape check (GEM / abarrelfull / shorteners / navigation URLs banned in code), HTTP status, soft-error + bot-wall detection with Wayback fallback (bot-block ≠ dead), redirect re-check, PDF text, normalised content match, host adapters that verify SPA pages (shipvault.com — and its citable unit-record URL `shipvaultapi-…/api/units/{id}`, the companion ref for a blank-rendering page — and marinetraffic.com) against the JSON they load; `value_variants` renders what a page actually says for a cell value (number/price/date forms, Status `active` ↔ delivery wording, `on order` ↔ order wording, hull numbers with or without the yard tag); graded reasons via `classify()` (ok / banned / dead / blocked / uncorroborated); `--check`, `--value`, `--log` | Verifier flagging false positives or negatives; new soft-error / bot-wall pattern; new banned host |
| `citation_qc.py` | §3.8a rot sweep — grades every existing backend `[ref]` URL once (`work/citation_qc.csv`, live sheet rows); `--corroborate` runs the per-cell §3.8c gate; re-fetches every fresh `dead` verdict once; `--sheet-rows`, `--hosts`, `--delay`, `--resume`, `--regrade` | Changing the triage grades or output columns |
| `wayback_save.py` | archive URLs to the Wayback Machine — **the only way this repo archives**. Save Page Now 2, always authenticated (IA S3 key from `$IA_S3_AUTH` or the keychain item `archive-org-s3`; exits rather than going anonymous), 6/min under the 7/min cap with the account's concurrent sessions, polls each job, retries SPN-side errors. Default = every distinct backend `[ref]` URL minus banned shapes; `--urls FILE`, `--sheet-rows`, `--within 30d`, `--retry-errors`, `--dry-run`. Resumable `work/wayback_save.jsonl` with citable `snapshot` URLs; never edits the backend | Changing SPN2 options, retry set, or rate |
| `fetch.py` | shared curl layer — `fetch_page()` (compressed, charset-aware, PDF/ZIP→text with OCR, TLS/UA retries, empty-PDF re-fetch, extra headers) + `fetch_text()` / `download()`. Clears bot walls itself: Cloudflare firewall page → `curl_cffi` Chrome TLS impersonation (`cf_impersonate`); JS challenge (Cloudflare, AWS WAF, Imperva) → real-Chrome clearance cookies (`cf_clearance`), once per host per process. **Byte-identical copy in the terminals and pipelines repos — change it in all three** | A host needs a new fetch quirk; PDF extraction failing; a new kind of bot wall (add its cookie prefix to `cf_clearance.WALL_COOKIE_PREFIXES` and its body marker to `_WALL_MARKERS_ANY_STATUS`) |
| `sweep.py` | polite bulk fetch — **the only way to sweep many URLs on one host** (wraps `fetch_page()`; `fetch.py` itself is untouched). Per-host pacing with jitter (6 s ± 2 s; tracker hosts vesselfinder.com / marinetraffic.com / marinetraffic.org 10 s ± 3 s — `--delay` can raise a floor, not lower it); per-host circuit breaker (3 consecutive `000`/429/403, or 8 consecutive 404s after 200s — the soft-block pattern — stop the host for the run and record its remaining URLs as skipped, retried with the failures on re-run; a host that tripped in an earlier run re-trips on its first failure); `--urls FILE` or `--template '…{imo}' --imos FILE|LIST`, fetched in the order given; `--max` per host per run; resumable JSONL under `work/` (latest record per URL wins); exit 1 when a breaker tripped | Tuning delays / breaker thresholds; a new tracker host for `HOST_DELAYS`; a new failure status |
| `ais_static.py` | AIS static-data cross-check for "has this on-order vessel been delivered and named" — **a lead, never a citable `[ref]`** (cited refs stay shipvault / marinetraffic / class / press through §3.8). Listens to aisstream.io `ShipStaticData` world-wide for a bounded time (`--minutes`, default 20) and keeps messages whose IMO is on the watch list (on-order backend rows; `--statuses`, `--imos FILE|LIST`) — the IMO filter is client-side because aisstream filters only by MMSI / bbox. Key from `$AISSTREAM_API_KEY` or the keychain item `aisstream-api-key` (exits rather than asking). Appends `work/ais_static.jsonl` (imo, name, mmsi, ship type, destination, callsign, position, ts; latest per IMO wins); the summary leads with live sheet rows. **"Not seen" is not evidence of anything** (static messages repeat every ~6 min, only for vessels transmitting near a terrestrial receiver) | aisstream message shape or subscription format changed; new watch-list rule; key storage changed |
| `cf_clearance.py` | earns / stores bot-wall cookies (`cf_clearance`, `aws-waf-token`, Imperva `incap_ses_`/`visid_incap_`/`nlbi_`) by driving Google Chrome over DevTools (no automation flags, so Turnstile passes in ~5 s; a page is "cleared" when neither its title nor its rendered DOM looks like a challenge — a real 404 counts); store `work/cf_clearance.json` (gitignored, IP-bound; ~1 yr for Cloudflare, days for AWS WAF); `LNGCT_NO_BROWSER=1` forbids the launch; CLI `python scripts/cf_clearance.py <url>` / `--show` | Chrome path changed; challenge no longer clears; need a different CDP flow |
| `shipvault_api_refs.py` | shipvault companion refs (RF §6a.8 rev 21): where a cited `shipvault.com/ships/{id}` page renders blank in a browser (double-encoded API answer), adds the unit-record URL as a second ref right after it, only where the record corroborates the cell (§3.8c). `--batch <dir>` patches a batch's source JSON in place (idempotent — run before `build_workbook.py`; writes `<dir>/shipvault_api_refs.json`); `--backend-batch <dir> [--skip-fix fix.json …]` writes a ref-only (`prev_state: "corroborate"`) `data_fill.json` for cells already in the backend | shipvault fixes its encoding (companions become unnecessary); a new batch source shape |
| `other_names.py` | former Names → `Other names` (RF §4.16): derives an `append_ref` `Other names` cell from every `Name` cell in a fix batch — existing cell + `"; "` + former Name, gated on the former name alone (`gate_value`; exact name, never scattered tokens; candidates = the new Name's refs + the row's existing `Name [ref]`, then the shipvault record for the IMO as a last resort; an IGU PDF's wrapped `(ex-…)` names are checked against `work/igu_fleet_<edition>.json`; nothing is asked when the former name is part of the new one; trackers paced, not asked about hull placeholders, vesselfinder not asked), Y / blank ref when nothing passes. `--batch <dir or fix.json>` patches in place (idempotent, stamps each Name cell `former_name`; run before `build_workbook.py`); `--collect <dirs> --out fix.json` builds a standalone batch for batches already built; `--include <row_id>` overrides a skip. Skips spelling / truncation fixes (similarity ≥ 0.85 or a prefix), names claimed by another row, placeholder → placeholder | A real rename classified as a spelling fix (or the reverse) — tune `SPELLING_RATIO` / `is_placeholder`; a new multi-valued column |
| `imo_tracker.py` | the §6a.8 IMO->vessel-tracker fallback — shipvault open API first (`shipsearch/{IMO}` → unit record → citable `shipvault.com/ships/{id}`), marinetraffic.org IMO search second | shipvault API / tenant header changed; marinetraffic.org URL pattern changed |
| `build_workbook.py` | xlsx scaffolding — sheets, color fills, frozen panes, headers (modes: ref_fill / discovery / data_fill / fix / fsru / igu). `fix` mode rebuilds corrected full rows from a `fix.json` (optionally `--base <corrected_rows.csv>`) and runs every ref through the §3.8c value↔ref corroboration gate (drops refs that don't contain the cell value); a cell may set `preserve_ref:true` for cosmetic/derived edits (rewrite value, keep the paired `[ref]`, skip the gate), or `append_ref:true` + `gate_value` for an addition to a multi-valued cell (`Other names`, RF §4.16 — gate the added element, append passing refs to the existing `[ref]`); warns when a Name change has had no former-name check. `fsru` mode renders the `work/fsru_reconcile.json` buckets into a 10-sheet GIIGNL↔backend comparison workbook (no `[ref]` cells — GIIGNL not citable). `igu` mode renders `work/igu_reconcile.json` into the 11-sheet IGU↔backend workbook, every table led by the live sheet row (no `[ref]` cells proposed) | Adding a new sheet section; changing color convention; changing fix-mode gating; changing the fsru or igu sheet set |
| `derive_fills.py` | data-fill: select in-scope rows, compute derivable autofills, list per-cluster research targets | New derivable column; changing the row-selection filter |
| `merge_fills.py` | data-fill: merge per-cluster research outputs + run the central §3.8 re-verify gate. Honours `derivable: true` only on the DF §5 autofill columns (`DERIVABLE_FIELDS`); gates a `derived_from: {total, n}` Price on the order **total** and caps it at Y (DF §5a); demotes any other fill left with no URL | Verifier behavior changes; new research-output key; a new derivable column |
| `recalc.py` | open the xlsx, force recalc, return any formula errors | Always run before committing the batch |
| `batch_digest.py` | triage a batch into auto-safe vs needs-a-decision (`digest.md`) | Changing the triage split or digest format |
| `apply_batch.py` | reviewed batch → `decisions.csv` + offset-proof apply artifacts (`apply_rows.csv`, `apply_patch.csv`, `apply.json`, `conflicts.csv`); modes ref_fill / discovery / data_fill / fix (a fix cell's gated refs *replace* the paired `[ref]`; `preserve_ref` cells rewrite the value only; `append_ref` cells append to it) | New batch mode; changing the patch/decision schema |
| `verify_apply.py` | re-pull + diff backend vs `apply.json` (landed/mismatch/missing) + qc the touched rows + dedupe sweep over touched/added rows | Changing match logic; new verify check |
| `dedupe_check.py` | internal duplicate scan — tiered (IMO/builder+hull → HIGH; placeholder↔identified on builder+owner+capacity+delivery → MED; distinct ordinals → LOW sister ships). Advisory; `work/dedupe_report.csv` (reports lead with **live sheet row**, not the column-A `row_id`); `--rows`, `--sheet-rows`, `--strict` (apply.md §5a) | New dup signal/tier; a false positive/negative; new disqualifier |

Trust the scripts by default. They're versioned scaffolding, not throwaway code. If you fix one, commit the fix in the same batch with a note in `notes.md`.

## Working directory convention

Scratch artifacts (intermediate CSVs, cached CSB JSON, draft citation JSON) go in `work/`, which is gitignored. The only things that get committed from a batch are the contents of `batches/<date>_rows_X-Y/`.
