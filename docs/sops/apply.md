# LNG Carrier Tracker — Apply & Verify SOP

**Document purpose:** Operating manual for the **apply** workflow — getting a reviewed
batch's accepted proposals from the candidate workbook back into the Google Sheets
backend, safely and trackably, then verifying they landed. Complements the [ref]-Fill,
Discovery, and Data-fill SOPs (which *produce* candidate batches). **Authoritative** for
the review→apply→verify round-trip. Abbreviated **AP**.

**Last revised:** 2026-09-22 rev 10 (§2b / §3: the grade `decisions.csv` pre-fills from is
computed by the §3.8c gate (RF §5 rev 28), and a machine's `review_log.jsonl` record — the
backend sync, a `§5 regrade` — is never a click: the review app leaves the line undecided and
the push leaves it alone). Prior: 2026-09-22 rev 9 (§2d: the **directed session write** — Claude may write the
sheet when Baird directs it in-session, with a printed plan, a revert file, re-pull verification
and honest `push_log` attribution; never automatic, never a forged reviewer click). Prior:
2026-09-21 rev 8 (§2c: the living workbook — the reconciliation's copy on
the work Drive, whose `processed` column every sync and push mirrors; §7 follows). Prior:
2026-09-21 rev 7 (§2b: the button is **push changes** — it also writes the
reviewer's suggestions, each ref §3.8c-gated against the suggested value at plan time; §3 / §7
follow). Prior: 2026-09-21 rev 6 (§2b: the review app's **push accepted** — a third apply
path, a listed and once-confirmed sheet write; §7 reworded). Prior: 2026-09-18 rev 5 (step 2 /
§3: the review app, `review_app/`, is the
recommended surface for deciding the holds; `decisions.csv` by hand stays valid). Prior:
2026-09-17 rev 4 (§2a: applying several batches that share rows — full rows
are a snapshot, so go by patch; applier settings per batch mode). Prior: 2026-06-05 rev 3 (dedupe Tier-2 matching corrected: a row with a real hull
or IMO is *identified*, never a placeholder — so identified hulls like `Hull 8254 (HSHI)` no
longer shadow-match genuinely blank slots; delivery-year dropped from the blocking key and
demoted to a >1-year disqualifier; trailing ordinal markers (`… ECC 1)`, `(Seapeak 2)`) now
recognized. Fixes the false-negative where ECC 1 flagged but ECC 2/3 did not). Prior: rev 2
(added §5a — the dedupe sweep: `verify_apply.py` runs `dedupe_check.py` over the rows a batch
touched/added, so a newly-added row that duplicates an existing vessel is caught at apply time.
Tiered HIGH/MED/LOW, advisory, writes `<dir>/dedupe_report.csv`; also runnable standalone).
Prior: 2026-06-05 rev 1 (initial SOP).
Built after a manual copy/paste column offset corrupted rows 1216/1217 (CMHI-282-07/-08). The
whole point of this workflow is that the offset class of bug becomes impossible.

---

## 1. Why this exists

Every batch up to the candidate workbook is automated. The last mile — a human copying
accepted values back into the backend — was pure manual paste, and a column-misaligned
paste is what corrupted rows 1216/1217. This workflow makes the apply step **offset-proof,
trackable, and verifiable** while keeping the hard rule intact: the backend is human-edited,
and nothing here writes to it without the reviewer's explicit accept decision ([ref]-Fill
SOP §4.7).

## 2. The pipeline (three scripts + the backend)

```bash
# 1. Triage: split the batch into auto-safe vs needs-a-decision (read-only).
python scripts/batch_digest.py --batch batches/<dir>
#   -> <dir>/digest.md

# 2. Decisions + apply artifacts. First run pre-fills decisions.csv by confidence
#    (Green/derivable -> accept, Yellow/Red -> hold). Decide the holds, then re-run.
#    Recommended surface: the review app (review_app/README.md) —
#      python review_app/server.py --batches batches/<dir> [<dir> ...]
#    Editing decisions.csv by hand stays valid.
python scripts/apply_batch.py --batch batches/<dir>
#   -> <dir>/decisions.csv   (acceptance tracking — editable)
#      <dir>/apply.json      (canonical record of what was accepted)
#      <dir>/apply_rows.csv   (full backend-width rows — offset-proof wholesale paste)
#      <dir>/apply_patch.csv  (flat cell patch for the by-name Apps Script applier)
#      <dir>/conflicts.csv    (research vs a non-blank backend value — decide separately)

# 3. Apply — pick ONE path (both are offset-proof):
#    (a) Full-row paste: open apply_rows.csv, paste each row over the matching backend
#        row (matched by the row_id in column A) — or, for discovery rows (blank row_id),
#        into a new backend row. Full-width paste can't shift a column.
#    (b) By-name applier: paste apply_patch.csv into the backend sheet's "apply_patch"
#        tab and run tools/apply_patch.gs (DRY_RUN=true first to preview, then false).
#        It writes each cell by row_id + header, so a column offset is impossible.
#    (c) Review app push (§2b): the "push changes" button — accepted value / [ref] lines and
#        the reviewer's gated suggestions; new rows and conflicts still go by (a) / (b).

# 4. Verify: re-pull the backend and confirm everything landed.
python scripts/verify_apply.py --batch batches/<dir> --pull
#   -> <dir>/verify_report.csv  (landed / MISMATCH / MISSING per accepted cell)
#      <dir>/dedupe_report.csv  (advisory: did a touched/added row duplicate an existing
#                                vessel? — §5a; also runnable standalone via dedupe_check.py)
```

## 2a. Several batches that share rows — go by patch

`apply_rows.csv` is a **snapshot**: each full row is the backend row as it stood when
`apply_batch.py` last ran, plus that batch's accepted cells. Paste it after another batch has
changed the same row and the paste **reverts that batch's cells**. So when more than one
un-applied batch touches a row:

- apply by `apply_patch.csv` (path b) — it writes only the batch's own cells; **or**
- before each full-row paste, re-pull and re-run `apply_batch.py --batch <dir>` so the rows are
  rebuilt on the current backend (decisions are preserved).

Applier settings (`tools/apply_patch.gs`): `BACKEND_SHEET_NAME` must be the backend tab's real
name (`data - backend`), and `OVERWRITE_NONBLANK` follows the batch mode. A **fix** batch, or a
ref-append batch, replaces non-blank cells by design — set it `true`, or every such cell is
logged `SKIP set (non-blank)` and nothing lands. A **data-fill** or **[ref]-fill** batch is
additive to blanks — leave it `false`, so a cell someone filled since the pull is skipped and
shows up in the verify report instead of being overwritten. Discovery rows are `append` ops and
ignore the flag. Always read the DRY_RUN log first: the `would set` count should equal the
batch's `set` lines.

## 2b. Push from the review app

The review app's **push changes** button (Baird 2026-09-21, renamed from *push accepted* the
same day; `review_app/push.py`, `review_app/README.md`) writes accepted lines and the reviewer's
suggestions straight into the backend sheet. It is path (b) without the paste: the same cells
`apply_patch.csv` carries, addressed by row_id + header against a fresh pull, with fix /
ref-append semantics taken from each line (no `OVERWRITE_NONBLANK` switch) and every batch laid
over the pull in apply order, so §2a's overlap problem does not arise.

- **Listed, then confirmed once.** The dialog shows every cell that will change (live row,
  column, now → becomes). The confirmation is bound to that plan: the server re-pulls and
  recomputes before writing and refuses a plan that changed. This confirmation is the human
  edit of §7 — nothing is written on a click of `accept`.
- **Clicked accepts only** (Baird 2026-09-21). A line is pushed only when its latest
  `review_log.jsonl` record is a reviewer's accept. An accept `apply_batch.py` pre-filled by
  the computed grade, one typed into `decisions.csv`, or one a **machine** wrote — the backend
  sync, a `§5 regrade` (`store.MACHINE_REVIEWERS`) — was never clicked: the dialog counts these
  and leaves them alone.
- **Suggestions are pushed, gated** (Baird 2026-09-21). A line whose latest record is
  `suggest` is written as the cell `review_app/suggestions.py` would put in a fix batch: the
  suggested value, with the refs typed in the suggestion (prefilled from the proposal's) gated
  one by one against that value by the §3.8c gate (`igu_refs.corroborates_cell`; an IGU
  landing page → the PDF) at plan time — passing refs replace the paired `[ref]` (Rule F holds:
  no value goes in without one); `cosmetic` with the refs unchanged keeps the cell's `[ref]`;
  `Other names` appends. A suggestion no ref corroborates is listed as not pushed with each
  ref's verdict, never written (§3.8c is a hard block); it takes the fix-batch path.
- **Value / `[ref]` lines only.** Discovery new rows and conflicts stay on paths (a) / (b) and
  §4. A data-fill or ref-fill value is written only into a blank or `unknown` cell; otherwise
  it is listed as not pushed (it is a conflict).
- **An applied batch is not re-pushed by default.** Where the sheet differs from an applied
  batch's accepted value, the likelier cause is a later hand edit; those cells are listed apart
  and need their own tick.
- **Reject writes nothing** and never reverts a cell that is already in the sheet.
- The push verifies its own cells and appends `<dir>/push_log.jsonl`. Step 4 still closes the
  batch: `verify_apply.py --batch <dir> --pull` writes `verify_report.csv` and runs §5a.

## 2d. Directed session write (Baird 2026-09-22)

Claude may write the backend sheet itself — **only when Baird directs it to, in that session,
for that specific write.** It is never automatic, never inferred, and never a way to finish a
task faster. Absent an explicit direction, §2b stands: the push button is the only script path
to the sheet, and Baird confirms it in the browser.

What counts as a direction, and what does not:

- **Counts:** Baird saying, in the session, to make this write / apply these cells / do it for
  him, with the cells identifiable from the conversation.
- **Does not count:** a selected option in a picker; approval of a *plan* that mentioned a
  write; permission given for an earlier write in the same session; "go ahead" on an unrelated
  step; silence; inferring that he would obviously want it. Permission is per write — it does
  not carry to the next batch, the next cluster, or the next day.

Preconditions, every time:

1. **Fresh pull immediately before** building the plan (`pull_backend.py`), not a pull from
   earlier in the session.
2. **The plan is printed cell by cell** — live sheet row, column, old → new — and no-ops are
   dropped. If the plan is too long to show, it is too long to write this way; use §2b.
3. **A revert file** next to the batch: every cell's pre-write value, keyed by A1
   (`arc7_revert.csv` is the pattern).
4. **Verify by re-pull** after writing, and report the count that actually holds its new value.
5. **Honest attribution in `push_log.jsonl`**: `reviewer` names the session and the direction
   (`via`, `directive`). **Never forge a reviewer click.** A line written this way still has no
   `review_log.jsonl` record, and §2b will still count it `unclicked` — that is correct and
   must not be "fixed" by writing a fake accept record.
6. **Scope is exactly what Baird named.** Neighbouring cells that look wrong are reported, not
   written.

The write itself is the same `gws-gem-write` `values.batchUpdate` §2b uses. Record the
deviation in the batch's `notes.md` — what was written, on whose direction, and where the
revert file is.

First exercised 2026-09-22: the six Hanwha Arc7 rows, 42 cells, after the push button skipped
them as `unclicked`.

## 2c. The living workbook (the reconciliation's copy on Drive)

A pass that runs over weeks needs one place a reader can open to see what has landed. That is
the **living workbook** (Baird 2026-09-21; `review_app/living.py`, `data/living_workbook.json`):
one Google Sheet in the work Drive folder `claude-output`, converted from the pass's combined
workbook, created once and updated in place so its URL stays shareable.

- **It is a mirror, never a source.** Nothing is ever read back from it into a batch, a
  decision or the backend. It is not a `[ref]`.
- **Two tabs carry a `processed` column**, and those cells are the only ones the sync writes:
  `all_proposals` (one line per proposed cell) and `remaining_changes_backend_shape` (one row
  per vessel). `processed - incorporated` = the pulled backend holds it (the app's own `in the
  backend` test — value *and* refs; for a suggestion, the suggested value);
  `processed - rejected` = someone rejected it (`apply_batch.py` never pre-fills a reject, so
  a reject is always a person's call); `partly processed - N of M` on a vessel with lines still
  open; blank = still open, accepted-but-unwritten included.
- **Every sync backend and every push changes updates it**, straight after the pull that
  settles what the backend holds. A failure there is reported in the banner and nothing else
  changes: it is not on the backend's write path.
- **The join is by key, not by position.** `build_combined.py` writes `line id`
  (`<batch dir>::<decision id>`) and `line key` (`row:<row_id>`, or `cluster:<batch>:<cluster_id>`)
  columns, and the sync reads them live — so sorting or filtering the sheet cannot put a value
  on the wrong line, and a key the current batch set does not know is left alone. Leave those
  two columns and the `processed` column to the sync; anything else in the sheet is yours.
- **Rebuild, don't re-create**, after rebuilding the combined workbook
  (`python review_app/living.py --rebuild`): same file id, same URL. `--create` would leave a
  second copy on the Drive. `--no-living` (server) or `LNGCT_LIVING_SYNC=0` switches the sync
  off, and it runs only for the batch dirs the workbook was built from.

## 3. Decisions & acceptance tracking (`decisions.csv`)

`decisions.csv` is the **authoritative decision surface** (the data-fill sheet is
row-oriented and can't track per-cell decisions; the QA_review `decision` column mirrors
the same defaults for in-sheet reading). One row per proposal:

| column | meaning |
|---|---|
| `id` | stable key — `row_id|column` (fills/refs) or `cluster:<id>` (discovery) |
| `default` | the computed grade's default (`accept` for Green/derivable, else `hold`; RF §5 rev 28 — the grade comes from what the §3.8c gate did, not from a researcher's label) |
| `decision` | **what you edit** — `accept` / `hold` / `reject` |

Re-running `apply_batch.py` preserves your edits (an existing `decisions.csv` is never
clobbered) and only regenerates the apply artifacts from the current decisions. This file
is the record of what was accepted for a batch — commit it with the batch.

**The review app** (`review_app/`, recommended) is a local page over one or more batches'
`decisions.csv`. It rewrites only the `decision` cell of the line decided (every other byte
kept) and appends each decision — who, when, how, note — to `<dir>/review_log.jsonl`, the
audit log; commit it with the batch. A record a **machine** wrote (`store.MACHINE_REVIEWERS`:
the backend sync, `scripts/regrade_confidence.py`) says so and is not a reviewer's call — the
app draws the line as an un-clicked pre-fill, and §2b will not push it. A value suggested *instead of* a proposal is recorded
as `reject` here and `suggest` in the log (value, kind, note, `suggested_refs`), and reaches
the backend through the §2b push (gated) or as its own fix batch (`review_app/suggestions.py`
→ the QC-SOP fix path, re-gated). Deciding never touches the backend. Hand edits of
`decisions.csv` remain valid; the app reads the csv as the truth.

## 4. Conflicts are not fills (`conflicts.csv`)

A proposal that contradicts a **non-blank** backend value is a **conflict**, never an
automatic fill (data-fill is additive to blanks/`unknown`s — Data-fill SOP §9,
[ref]-Fill SOP §8). `apply_batch.py` routes these to `conflicts.csv` with the backend
value, the research value, sources, and a recommendation. Decide each by hand; if you
accept one, apply it as a deliberate single-cell edit (the by-name applier with
`OVERWRITE_NONBLANK=true`, or a direct edit). Keep the conflict record in the batch.
The review app's Items tab records a conflict's call in `conflicts.csv` `decision` and in
`<dir>/review_items.jsonl`; a re-run of `apply_batch.py` regenerates `conflicts.csv` with every
call back at `hold`, so the jsonl is the durable record (the app flags the drift).

## 5. Verify (`verify_apply.py`) — close the loop

After applying, **always** re-pull and verify. `verify_apply.py` diffs the re-pulled
backend against `apply.json`:
- **landed** — backend now holds the accepted value. ✓
- **MISMATCH** — backend holds something different (a bad paste, or a since-changed value).
- **MISSING** — the accepted value isn't in the backend (not applied, or applied to the
  wrong row).

It also runs the `qc_backend.py` content checks over the touched rows, so a column offset
introduced *during* apply is caught immediately (this is the check that would have flagged
1216/1217 the moment it happened). `--strict` exits non-zero if anything didn't land —
suitable for gating. A clean verify is the definition of "batch incorporated."

## 5a. Dedupe sweep (`dedupe_check.py`) — did this batch shadow an existing vessel?

`verify_apply.py` also runs an **internal duplicate scan** over the rows this batch
touched or newly added (`dedupe_check.scan_duplicates`, focused on those row_ids), so a
freshly-added row that duplicates a vessel already in the tracker is caught at apply time —
before it ossifies. Hits are written to `<dir>/dedupe_report.csv` and surfaced on stderr.
The sweep is **advisory**: duplicates are judgment calls (a placeholder slot vs a distinct
sister ship), so they never fail the apply by themselves — but you must look at any HIGH/MED
group before calling the batch done.

The scan is tiered, highest-confidence first:
- **Tier 1 (HIGH)** — two rows share a real **IMO**, or a real **(builder, hull)**. Same
  vessel; merge (keep the most complete row, retire the other).
- **Tier 2 (MED)** — an **unidentified slot** (no hull AND no IMO — blank / `unknown` /
  `TBN` / a discovery row not yet christened) and another row match on builder + owner +
  capacity (±8,000 cbm), delivery years within a year, with **no distinguishing hull, IMO,
  or ordinal**. Probably the same order slot entered twice; verify by source. A row that
  carries a real hull or IMO (e.g. `Hull 8254 (HSHI)`) is *identified*, never a placeholder.
- **Tier 3** — disqualifiers applied while building Tier 2: distinct non-blank hulls,
  distinct non-blank IMOs, clearly different capacities, or delivery years >1 apart mean
  *sister ships / separate orders*, never paired.
- **Tier 4 (LOW)** — a Tier-2 candidate whose rows carry **different ordinal markers**
  ("8th ship" vs "9th ship", `…-07` vs `…-08`) is downgraded — distinct sisters (the Knutsen
  8th-vs-9th lesson). Reconcile by ordinal, then dismiss.

Run it standalone over the whole backend (or a focus set) any time, not just at apply:

```bash
python scripts/dedupe_check.py [--rows 1216,1217] [--sheet-rows 1211,1212] [--strict]
#   -> work/dedupe_report.csv
```

`--rows` focuses by `row_id`; `--sheet-rows` focuses by live tab row; `--strict` exits
non-zero if any HIGH/MED group exists. The SFOC reconciliation pass should run the
standalone full-backend scan as its closing step too.

**Row identity — always read the live sheet row.** `row_id` (colmap `row_id`) is column A,
*"original order in sheet"* — a static stamp that drifts from the live tab row as rows are
deleted (on the 2026-06-05 pull, row_id 1216 sat at sheet row 1211). Every report
(`verify_report.csv`, `dedupe_report.csv`) carries a `sheet_row`/`sheet_rows` column and the
stderr lines lead with the live row (`sheet row 1211 (id 1216)`), resolved by
`apply_batch.sheet_row_map` (live row = CSV line index + 1). Matching and pasting still key
on `row_id` — it's the stable, offset-proof identifier — so the apply itself is unaffected;
only the human-facing presentation uses sheet rows.

## 6. Publishing the candidate workbook (optional, for shared review)

To share the xlsx for review (the digest + decisions.csv cover local review):
1. Upload the batch xlsx to the project Google Drive folder.
2. Share → "Anyone with the link" → Viewer; open once → "Open with → Google Sheets".
3. Put the Sheets URL in the `Drive` column of `batches/README.md` (prefer the Sheets URL).

## 7. Hard requirements

- **The backend is still human-edited.** Every cell written is one the reviewer set to
  `accept` in `decisions.csv`, or a value the reviewer suggested themself with a ref that
  passes §3.8c. No script writes to the backend without that ([ref]-Fill §4.7).
  The one script that writes the sheet at all is the review app's push (§2b), and only the
  listed cells, on the reviewer's confirmation in the app — never from a command line, a batch
  build or an agent session. The living workbook's sync (§2c) is a separate outward write and
  touches no backend cell: only the `processed` column of its own two tabs.
- **Apply by name or by full row — never cherry-pick cells by hand.** Both supported paths
  address columns by header (applier) or paste full backend-width rows (apply_rows.csv);
  neither can land a value in the wrong column.
- **Always `verify_apply.py --pull` after applying.** An unverified apply is an open loop.
- **Conflicts are decided, not auto-applied.** Additive-to-blanks holds.
- **Review the dedupe sweep before calling a batch done.** §5a is advisory (it won't fail
  the apply), but a HIGH/MED group means a row may duplicate an existing vessel — resolve it.

## 8. Changelog

- **rev 10** (2026-09-22): §2b / §3 follow RF §5 rev 28: the `default` a batch pre-fills is the
  grade `scripts/confidence.py` computes from the §3.8c gate, and a machine's log record (the
  backend sync, `scripts/regrade_confidence.py`'s `§5 regrade`) leaves the line undecided in the
  review app and unpushed by §2b — `store.MACHINE_REVIEWERS` is the list.
- **rev 9** (2026-09-22): §2d **directed session write** — a second sanctioned path to the
  sheet, gated on an explicit per-write direction from Baird rather than a browser click.

- **rev 8** (2026-09-21): Added §2c: the living workbook — the pass's copy on the work Drive
  (`review_app/living.py`), whose `processed` column every **sync backend** and **push changes**
  mirrors from the current decisions, keyed by `line id` / `line key` rather than by row
  position. A mirror only: never read back, never a `[ref]`, never a backend cell. §7 follows.
- **rev 7** (2026-09-21): §2b: **push accepted** → **push changes**. The push also writes the
  reviewer's suggestions — value + the refs typed in the suggestion (a box in the Suggest
  dialog, prefilled with the proposal's refs; `suggested_refs` in the log), each gated against
  the suggested value at plan time; a suggestion no ref corroborates is listed as not pushed.
  Step 3(c), §3 and §7 follow.
- **rev 6** (2026-09-21): Added §2b and step 3(c): the review app's **push accepted** button
  writes accepted value / `[ref]` lines into the sheet after listing every cell and one
  confirmation (plan token, re-pull before and after, `push_log.jsonl`). New rows, conflicts
  and suggestions stay by hand; reject writes nothing. §7 names it as the only script write.

- **rev 5** (2026-09-18): Step 2 and §3 name the review app (`review_app/`) as the recommended
  surface for deciding holds, replacing the combined xlsx; `review_log.jsonl` /
  `review_items.jsonl` join the batch record; suggestions go through a fix batch. §4 notes that
  `apply_batch.py` resets conflict calls. Hand-editing `decisions.csv` stays valid.

- **rev 4** (2026-09-17): Added §2a. The sep-17-pass queued twelve batches with heavy row
  overlap (batch 8 shares 138 rows with batch 1 and 193 with batch 4); full-row pastes in
  sequence would have reverted one another. Also records the applier's `OVERWRITE_NONBLANK`
  setting per batch mode — a fix batch applied with the default `false` silently lands nothing.

- **rev 3** (2026-06-05): Dedupe Tier-2 matching corrected after a false-negative (the
  scan flagged Capital Clean ECC 1 as a possible dup of the Capital Hull 8254-8257 order but
  silently dropped ECC 2 and ECC 3). Three fixes in `dedupe_check.py`: (1) a row carrying a
  real normalized hull or IMO is *identified*, never a placeholder — `placeholder = not hull
  and not imo` — so identified hulls (`Hull 2656 (SHI)`, IMO present) stopped shadow-matching
  the genuinely blank discovery slots and the MED count stopped exploding; (2) `delivery_year`
  removed from the Tier-2 blocking key (one order's sisters slip a year, which an exact-year
  key split apart, hiding ECC 2/3 at 2029 from the 2028 hulls) and demoted to a >1-year
  *disqualifier*; (3) the ordinal extractor now catches trailing sister markers (`… ECC 1)`,
  `(Seapeak 2)`) with a `(?<!\d)` guard so 4-digit hulls/years (`…Geoje 2775`, `…May 2026`)
  don't masquerade as ordinals — so same-order sisters correctly demote to Tier-4 LOW. No
  schema change; advisory behavior unchanged.
- **rev 2** (2026-06-05): Added §5a — the dedupe sweep. `verify_apply.py` runs
  `dedupe_check.py` (`scan_duplicates`) over the rows a batch touched/added and writes
  `<dir>/dedupe_report.csv`; tiered HIGH (shared IMO / builder+hull) / MED (placeholder↔
  identified on builder+owner+capacity+delivery, no distinguishing hull/IMO) / LOW (distinct
  ordinal markers → sister ships). Advisory — never fails the apply. Also runnable standalone
  (`python scripts/dedupe_check.py [--rows …] [--sheet-rows …] [--strict]`), which the SFOC
  pass closes with. Reports now resolve and lead with the **live sheet row** (`row_id` is the
  static column-A "original order in sheet" stamp, not the tab row) via the new
  `apply_batch.sheet_row_map`; `verify_report.csv` gained a `sheet_row` column,
  `dedupe_report.csv` a `sheet_rows` column. Matching still keys on `row_id`.
- **rev 1** (2026-06-05): Initial SOP. Adds `batch_digest.py` (triage), `apply_batch.py`
  (decisions + `apply.json`/`apply_rows.csv`/`apply_patch.csv`/`conflicts.csv`),
  `verify_apply.py` (re-pull diff + qc), and `tools/apply_patch.gs` (by-name applier).
  Built in response to the 1216/1217 manual-paste offset.
