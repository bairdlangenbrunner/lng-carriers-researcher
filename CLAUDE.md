# LNG Carrier Tracker — Claude Code instructions

Read automatically at the start of every session. This file is the **workflow router**; the
rules live in `docs/sops/`, the per-script reference in `docs/scripts.md`. Every command below
runs from the repo root as `python scripts/<name>.py` (`paths.py` anchors `work/` to the repo
root regardless of cwd).

## Repository orientation

- `docs/sops/` — the authoritative SOPs. Abbreviations used everywhere: **RF** `ref_fill.md`
  ([ref]-fill; Rules A–F, confidence §5, the §3.8 / §3.8c verification gate), **DC** `discovery.md`
  (four-ring source model, candidate workbook), **DF** `data_fill.md` (blank-vs-`unknown`
  preserve-ref contract, derivable autofills, controlled vocab), **SR** `sfoc_reconciliation.md`,
  **FR** `fsru_reconciliation.md` (name-keyed GIIGNL comparison; GIIGNL is not citable), **IG**
  `igu_reconciliation.md` (IMO-keyed IGU World LNG Report comparison; IGU is citable via the report
  PDF), **QC** `qc_release.md` (pre-release consistency sweep, Name placeholder conventions, the
  `fix`-mode batch), **AP** `apply.md` (reviewed batch → backend, offset-proof). The current rev of
  each is its `Last revised:` line.
- `docs/pointers.md` — "which SOP section governs X" index. **Start here** for any rule question.
- `docs/scripts.md` — what each script does, its flags, and when to read its source.
- `docs/plans/` — dated plans and state files (working notes, not rules). Active: the sep-17 pass
  (`2026-09-17_sep-17-pass_worklist.md` = what is left to decide / apply / research,
  `…_summary.md`, `…_update.md`), the review app (`2026-09-18_review-app.md` phase 1, built and in
  use; `2026-09-21_review-app-phase2_handoff.md` holds the binding phase-2 decisions — Apps Script,
  not started), `2026-09-23_comprehensive-discovery.md` (whole-orderbook reconciliation pass, batch
  built 2026-09-23), and two closed notes (`2026-09-16_cloudflare_access.md`,
  `2026-09-16_full_research_pass.md`).
- `docs/inclusion_criteria.md` — what's in scope vs out.
- `review_app/` — the review app (`review_app/README.md`): loopback-only surface for deciding a
  batch's holds. Deciding writes only `decisions.csv` + `review_log.jsonl`; its **push changes**
  button is the app's one path to the backend sheet (AP §2b); its **living workbook** (`living.py`,
  AP §2c) mirrors decisions into the `processed` column of the pass's Drive copy and writes nothing
  else. Imports from `scripts/`, never the reverse.
- `data/` — `csb_yard_urls.md` (stable ChinaShipBuild yard URLs), `owner_charterer_map.md`
  (canonical owner names; companion to `normalize.py`), `source_roster.md` (source tiers for
  corroboration URLs), `controlled_vocab.md`, facts tables, the GIIGNL PDFs.
- `batches/` — per-batch outputs, one directory per batch (`batches/README.md` is the index).
- `../lng-carriers-map` — sibling repo: live FSRU/FSU fleet map. Its `data/fleet.json` is
  exported from this repo's `work/backend.csv` via its `tools/export_fleet.py` — re-export after
  fleet changes.

## Before any batch

1. Read `docs/pointers.md`, then the SOP **sections** it names for this batch type (not whole
   SOPs — `ref_fill.md` alone is ~27k tokens). Read a whole SOP only when the task changes its rules.
2. If a cross-reference cites a rev older than the SOP's current `Last revised:` rev, flag it to
   the user before proceeding.
3. `python scripts/pull_backend.py` — **mandatory first step** (RF §3.0). The user edits the
   backend between batches; the column map is re-derived from the fresh header every run.
4. `python scripts/qc_backend.py` — advisory sanity check on the fresh pull. Review
   `work/qc_report.csv` and surface anything in the batch's scope before building.

## Workflow router

### A URL is blocked / 403 / "Just a moment..."

Never conclude anything about a page from WebFetch or a hand-rolled curl. Run it through the fetch
ladder first — `python scripts/fetch.py <url> --head 2000` (curl → `curl_cffi` TLS impersonation →
real-Chrome `cf_clearance` cookie; the notes line says which route worked). Only a wall the ladder
cannot clear grades `blocked`, and bot-block ≠ dead (RF §3.8a).

Status `000` with connection timeouts on every origin IP is an **IP ban, not a bot wall** — no UA,
fingerprint or cookie helps (this is how a 1 req/s vesselfinder loop ended on 2026-09-17). Do not
retry in a loop. Switch source or egress and re-test later with one request. Bulk sweeps of one
host go through `python scripts/sweep.py` (per-host pacing + circuit breaker), never a bare loop.

### Archiving URLs to the Wayback Machine

Triggers: "archive the refs", "save to Wayback". `python scripts/wayback_save.py` (`--dry-run`
first), in the background. Already authenticated with Baird's archive.org S3 key (env or keychain):
don't hand-roll `/save/` calls, don't go anonymous, don't ask for credentials. Budget ~N/6 minutes.
Results in `work/wayback_save.jsonl`; re-running resumes. Whether a snapshot goes into a `[ref]`
cell is RF §7 (last resort, live URL dead).

### [ref]-fill batch

Triggers: "fill refs for rows X to Y", "next batch", "redo batch N", "rebuild rows X-Y". SOP: RF.

1. `pull_backend.py`. Fillable cells = blank `[ref]` paired with a FILLED value (Rule F).
2. Cluster rows by (yard, owner, contract month) — RF §3.2; watch cluster splits within one
   owner/yard when contract dates or delivery years diverge (RF §4.12 Rule E).
3. `csb_fetch.py <yard-slug> --all-pages` per yard (slugs: `data/csb_yard_urls.md`) →
   `work/csb/<yard>.json`. **Every vessel checked in any workflow is also looked up on CSB**
   (RF §3.3b, Baird 2026-09-23): orderbook + `ship.aspx` page; report agreement / disagreement.
   CSB's "Under Construction" = not yet delivered; hull digits repeat across yards (match yard +
   hull, or IMO).
4. Hulls not on CSB → RF §6a fallback (targeted search → DART/KIND → class society → vessel
   database → `imo_tracker.py <imo>` **only at §6a.8, last before** the §6a.9 negative-result log).
5. Trade press / regulatory per RF §3.4; pick sources via `data/source_roster.md`.
6. `url_verifier.py <url> <expected…>` — the §3.8 gate, EVERY url before it goes in the xlsx.
7. `build_workbook.py --mode ref_fill --rows X-Y --citations citations.json --out batches/<dir>/`,
   then `recalc.py <xlsx>` (zero formula errors), then `batches/<dir>/notes.md` (conflicts,
   defects corrected, escalations, Drive link). Commit the batch directory.

### Discovery batch

Triggers: "find new vessels", "discovery run", "gap analysis", "what's missing from the backend",
"catch-up sweep", "comprehensive discovery" / "whole-orderbook reconciliation". SOP: DC.

1. Confirm parameters per DC §2 — gap window, yard coverage, proposed-bucket threshold, FSRU
   handling, output naming. **Do not skip**; discovery is sensitive to scope choices. A
   comprehensive pass is not date-bounded (plan `2026-09-23_comprehensive-discovery.md`).
2. `pull_backend.py`; `dedup_index.py --pending <un-applied discovery batch dirs>` (hull / cluster /
   IMO / name indexes + stub rows, so pending candidates are not re-reported).
3. Ring A — `csb_fetch.py <yard>` per yard in scope (`--all-yards --all-pages` for a comprehensive
   pass; page 1 is the leading edge only). Then `orderbook_reconcile.py` for the CSB ‖ backend ‖
   IGU Appendix 4 ‖ shipvault balance.
4. Ring B — regulatory sweep (DART / KIND / Bursa / HKEX; English proxies by default). Ring C —
   trade press via `data/source_roster.md`. Ring D — charterer programmes, only if the proposed
   threshold is expanded.
5. Cluster, dedup, and let the gate grade confidence (RF §5). `url_verifier.py` on every URL.
6. `build_workbook.py --mode discovery --candidates candidates.json --out batches/<dir>/`, `recalc.py`,
   `dedupe_check.py` (AP §5a), `notes.md`, commit the batch directory.

### Data-fill batch

Triggers: "data fill", "fill the blanks for rows X-Y", "fill missing <column>". SOP: DF.

1. `pull_backend.py`; `dedup_index.py`.
2. `derive_fills.py --since <YYYY-MM-DD>` → `work/data_fill.json` (derivable fills + scope) +
   `work/research_tasks.json`.
3. Research fan-out: one subagent per cluster (DC §3 four rings; controlled vocab in
   `data/controlled_vocab.md`; owner stylization RF §4.14; PRESERVE existing refs on `unknown`
   cells, DF §4). A price reported only as an order total → per-vessel Price with `derived_from`
   (DF §5a: Y max, never `derivable`). Reuse prior batches + backend siblings first. Each writes
   `work/research_<label>.json` — **clear stale `work/research_*.json` first**; the merge globs all.
4. `merge_fills.py` (no flags; runs immediately) — merge + central §3.8c gate; sets confidence from
   the gate (RF §5). Don't hand-grade in step 3.
5. `build_workbook.py --mode data_fill --fills work/data_fill.json --out batches/<dir>/`, `recalc.py`,
   copy `work/data_fill.json` into the batch dir, `notes.md`, commit the batch directory.

### Fix batch (corrections, renames, status changes)

Triggers: "fix batch", "correct rows …", "move X to scrapped". SOPs: QC §4, RF §4.16–§4.19, AP.

1. `pull_backend.py`. Write `work/<name>_fix.json` keyed by `row_id`; `preserve_ref:true` on a
   cosmetic / derived edit keeps the paired `[ref]` and skips the gate (QC §4); sourced corrections
   supply refs and pass the gate.
2. Before building, on any batch with Name cells: `other_names.py --batch work/<name>_fix.json`
   (RF §4.16); with Delivery year cells: `delivery_history.py --batch …` (RF §4.19); with shipvault
   refs: `shipvault_api_refs.py --batch …` (RF §6a.8).
3. `build_workbook.py --mode fix --fix work/<name>_fix.json --out batches/<date>_<HHMMET>_<label>/`
   — gates every ref, computes the grade, and writes the **gated** `fix.json` into the batch dir
   (that copy is what `apply_batch.py` reads; do not overwrite it with the source). `recalc.py`,
   `notes.md`, commit. Apply via the Apply SOP.

### SFOC / FSRU / IGU reconciliation batches

Triggers: "SFOC pass" / "reconcile against SFOC" (SR); "FSRU reconciliation", "compare FSRUs to
GIIGNL" (FR); "IGU reconciliation", "new IGU edition", "what did IGU drop / change" (IG). All are
comparison passes: the backend is never auto-edited, findings promote through a `fix` / discovery
batch, and the batch closes with `dedupe_check.py` (AP §5a).

- **SR** is script-light: follow `sfoc_reconciliation.md` end to end (stage inputs in `work/`,
  four buckets, nine-sheet workbook, `recalc.py`, commit).
- **FR**: `pull_backend.py` → extract with the terminals repo's parser
  `python ../lng-terminals-researcher/scripts/giignl_fsru_fleet.py data/GIIGNL-<year>-Annual-Report-<ver>.pdf --output work/giignl_fsru_fleet.json`
  → `fsru_reconcile.py` → `build_workbook.py --mode fsru --reconcile work/fsru_reconcile.json --out batches/<dir>/`
  → `recalc.py`; copy `fsru_reconcile.json` into the batch dir. GIIGNL is a comparison artifact,
  not a citable `[ref]`.
- **IG**: `pull_backend.py` → `igu_fleet.py <IGU PDF>` for **both** editions, fresh every time
  (layout changes; expected residue = IGU's own duplicate IMOs) → `igu_reconcile.py --pending
  batches/<un-applied dirs> --fetch-leads` → `build_workbook.py --mode igu --reconcile
  work/igu_reconcile.json --out batches/<dir>/` → `recalc.py`; copy both `igu_fleet_*.json`,
  `igu_reconcile.json` and the leads file into the batch dir. IGU rules: IG §1 (PDF by IMO), §5.2
  (dropped vessels → `scrapped`, never deleted), §5.4 (sole source; Names excepted — see Hard
  requirements).

### Pre-release QC batch

Triggers: "qc pass", "pre-release qc", "prep for data release", "name consistency check". SOP: QC.

1. `pull_backend.py`; `qc_backend.py` whole-sheet (`--strict` to gate). Triage by check (QC §3):
   column-offset / misplaced-vocab / url-in-value / bad-shape = corruption, escalate; orphan-ref /
   lookup-mismatch MED; name-builder-drift / name-ordinal-gap LOW. Confirm the canonical Name form
   with the user before any mass rename.
2. Package mechanical corrections as a fix batch (above). Release gate: re-pull + re-run
   `qc_backend.py`; clear when HIGH/MED are resolved or allowlisted and the Name checks are at zero.

### Review a batch's decisions

Triggers: "review app", "decide the holds". SOP: AP step 2 / §2b / §3; usage in `review_app/README.md`.

```bash
python scripts/pull_backend.py                                   # review_data refuses without a fresh pull
python review_app/server.py --batches batches/<dir> [<dir> ...]   # work/review_data.json, serves 127.0.0.1:8765
python review_app/suggestions.py --batches batches/<dir> ...      # suggestions push could not gate -> work/review_suggestions_fix.json (+ _notes.md to-do list)
python review_app/living.py --rebuild --xlsx batches/<combined dir>/<workbook>.xlsx   # refresh the Drive copy; rebuild, never --create
```

`↻ sync backend` re-pulls and rebuilds in place (a held line the backend already holds → `accept`;
a resolved open item → `resolved`). `⇪ push changes` (AP §2b, `review_app/push.py`) lists every
cell (live row, column, old → new) and, on **Baird's confirmation in the browser**, writes accepted
value / `[ref]` lines and gated suggestions through `gws-gem-write`, verifies, and appends
`<dir>/push_log.jsonl`. New rows and conflicts stay by hand; reject writes nothing. **Never call
`/api/push`, `push.write_sheet` or `App.push` from a session, script or test**, and never write a
fake `review_log.jsonl` accept — a directed session write is AP §2d, not the app's endpoints.
After a session, re-run `apply_batch.py` for each batch the session summary lists.

### Apply a reviewed batch

Triggers: "apply batch", "incorporate batch X", "verify the apply". SOP: AP (offset-proof; replaces
the manual copy/paste that corrupted rows 1216/1217).

1. `batch_digest.py --batch batches/<dir>` → `digest.md` (auto-safe vs needs-a-decision).
2. `apply_batch.py --batch batches/<dir>` — first run pre-fills `decisions.csv` by confidence;
   decide the holds (review app), re-run to finalise → `apply.json`, `apply_rows.csv`,
   `apply_patch.csv`, `conflicts.csv`.
3. Apply (pick one): paste `apply_rows.csv` full rows over matching backend rows, OR run
   `tools/apply_patch.gs` on `apply_patch.csv` (by name, `DRY_RUN` first). Several un-applied batches
   sharing rows → **patch path only** (full rows revert each other); `OVERWRITE_NONBLANK=true` for
   fix / ref-append batches (AP §2a).
4. `verify_apply.py --batch batches/<dir> --pull` → `verify_report.csv` + `dedupe_report.csv`
   (AP §5a; review any HIGH/MED group — a new row may duplicate an existing vessel).

Conflicts (research vs a non-blank backend value) go to `conflicts.csv` and are decided by hand,
never auto-applied.

## Hard requirements (these override anything above)

- **Never modify the backend directly.** Outputs are candidate xlsx files for human review (RF §4.7).
  Two paths write the sheet, both human-authorised: the review app's **push changes** (AP §2b, Baird
  confirms in the app) and a **directed session write** (AP §2d, Baird 2026-09-22) — Claude may
  write the sheet **only when Baird directs that specific write in that session**; never automatic,
  never inferred from a plan, a picker option or an earlier permission; per write, never carried
  forward. Preconditions every time (AP §2d): fresh pull, plan printed cell by cell, a revert file,
  re-pull verification, scope exactly as named, honest `push_log.jsonl` attribution — **never forge
  a reviewer click**.
- **Never propose deleting the row of a vessel that leaves service.** It keeps its row and moves to
  Status `scrapped` (Baird 2026-09-17; `docs/inclusion_criteria.md`, IG §5.2). Duplicates are the
  exception: the same vessel entered twice is flagged (`dedupe_check.py`, AP §5a) and Baird deletes
  the duplicate by hand, carrying a placeholder name worth keeping into the survivor's `Other names`.
- **Every URL passes §3.8 before going in the xlsx.** No exceptions, even for URLs that worked in
  prior batches — URLs decay. **Confidence is computed, not declared** (RF §5 rev 28): a ref that
  survives §3.8c on a **live** page stating the value for this vessel is Green — one source is
  enough; `scripts/confidence.py` overwrites a researcher's label. A researcher may argue a line
  **down** with a `cap_reason`, never up. Caps at Y: RF §4.18 delivery roll-forward, DF §5a
  order-total Price, a §3.8c conflict.
- **No value without a ref.** Never propose a value (even Vessel type `conventional`) with a blank
  `[ref]`; leave the cell blank. **Rule F always**: no orphan `[ref]` with no paired value (RF §4.13).
- **Never cite GEM** (`gem.wiki` or any GEM page or dataset) as a `[ref]` or corroboration — GEM is
  downstream of this tracker (RF §4.2). **Banned source: abarrelfull** (`abarrelfull.wikidot.com`,
  `abarrelfull.co.uk`) — never, in any output or lane (Baird 2026-07-17); chase the primary source
  it footnotes.
- **An IGU landing-page ref means: confirm the data point in that edition's report PDF, by IMO**
  (Baird 2026-09-21; IG §1) — 2025 always, 2026 where the landing page rather than the PDF is the
  URL. Look the row's IMO up in `work/igu_fleet_<edition>.json` (`igu_refs.IguTable.check`; extract
  the edition if missing) or the PDF and read the column. Never call the value unsourced because
  the landing page shows nothing; never count a text hit in another vessel's row. The backend's
  landing-page refs stay as they are (no bulk swap). New proposals cite the **PDF** (`url_verifier.
  citable_form` / `IGU_PDF`); the PDF is a ref only for what it prints for the row's IMO in that
  column (`igu_refs.corroborates_cell`); a row with no IMO gets no IGU ref.
- **IGU 2026 is a sufficient sole source** (Baird 2026-09-17, settled 2026-09-21; IG §5.4), Vessel
  type included — no second ref unless Baird explicitly says otherwise. IGU's *silence* (a dropped
  vessel) is not a statement and still needs its own verified ref. **A Name is the exception**: look
  the IMO up in shipvault / marinetraffic.org / vesseltracker first; unless one explicitly agrees
  with IGU's name, the databases' name (or the backend's) is the `Name` and IGU's goes to `Other
  names`.
- **A proposed Name change carries the former Name into `Other names`** (RF §4.16, Baird
  2026-09-17): appended with `"; "`, never replacing; a hull placeholder counts as a former name;
  spelling / truncation corrections, a name belonging to another row, and placeholder →
  placeholder restylings do not. Hull numbers are always `Hull NNNN (Tag)` (RF §4.17).
- **A proposed later Delivery year carries a second source and its history** (RF §4.18–§4.19, Baird
  2026-09-21): shipvault alone is Y / held — add the IGU PDF where IGU prints the same year, else
  press; the former year is appended to `Previous delivery year(s)` (`"; "`, oldest first) with
  `Delivery delayed` = `yes`, decided together with the Delivery year line.
- **Price is the full USD integer + `USD`** (`250000000`, never `250` + `$m`; `$m` retired 2026-09-18).
- **Data-fill is additive to blanks / `unknown`s only** — value + verified-`[ref]` pairs for human
  review; existing `[ref]` URLs on `unknown` cells are appended to, never replaced (DF §4, §9).
- **Always pull a fresh backend CSV at the start of a batch** and re-derive the column map.
- **Report live sheet rows**, not the column-A `row_id`, wherever a row is named to Baird.
- **Git:** branch → commit → push → PR → merge is pre-authorised for this repo (Baird 2026-06-07);
  commits all-lowercase and succinct, scoped to the task, no Claude attribution. **Never commit**
  credentials or anything in `work/` (gitignored).

## When to escalate

Per RF §11 and DC §7, pause and ask the user when: CSB is broken AND the §6a fallback is exhausted
on at least one cluster; a whole class of backend values looks systematically wrong; a new rule
would invalidate prior batches; corroboration is too thin for even Yellow after §6a; discovery
surfaces more than ~5 candidate clusters in one gap window; or the gap window is unclear.

## Scripts

`docs/scripts.md` holds the per-script table (purpose, flags, when to read the source). Read the
row for a script before changing it or when its output looks wrong; trust the scripts otherwise.
If you fix one, commit the fix with the batch and note it in that batch's `notes.md`.

## Working directory convention

Scratch artifacts (intermediate CSVs, cached CSB JSON, draft citation JSON) go in `work/`, which is
gitignored. The only things committed from a batch are the contents of `batches/<dir>/`.
