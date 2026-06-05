# LNG Carrier Tracker — Apply & Verify SOP

**Document purpose:** Operating manual for the **apply** workflow — getting a reviewed
batch's accepted proposals from the candidate workbook back into the Google Sheets
backend, safely and trackably, then verifying they landed. Complements the [ref]-Fill,
Discovery, and Data-fill SOPs (which *produce* candidate batches). **Authoritative** for
the review→apply→verify round-trip. Abbreviated **AP**.

**Last revised:** 2026-06-05 rev 3 (dedupe Tier-2 matching corrected: a row with a real hull
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
#    (Green/derivable -> accept, Yellow/Red -> hold). Edit the holds, then re-run.
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

# 4. Verify: re-pull the backend and confirm everything landed.
python scripts/verify_apply.py --batch batches/<dir> --pull
#   -> <dir>/verify_report.csv  (landed / MISMATCH / MISSING per accepted cell)
#      <dir>/dedupe_report.csv  (advisory: did a touched/added row duplicate an existing
#                                vessel? — §5a; also runnable standalone via dedupe_check.py)
```

## 3. Decisions & acceptance tracking (`decisions.csv`)

`decisions.csv` is the **authoritative decision surface** (the data-fill sheet is
row-oriented and can't track per-cell decisions; the QA_review `decision` column mirrors
the same defaults for in-sheet reading). One row per proposal:

| column | meaning |
|---|---|
| `id` | stable key — `row_id|column` (fills/refs) or `cluster:<id>` (discovery) |
| `default` | confidence-based default (`accept` for Green/derivable, else `hold`) |
| `decision` | **what you edit** — `accept` / `hold` / `reject` |

Re-running `apply_batch.py` preserves your edits (an existing `decisions.csv` is never
clobbered) and only regenerates the apply artifacts from the current decisions. This file
is the record of what was accepted for a batch — commit it with the batch.

## 4. Conflicts are not fills (`conflicts.csv`)

A proposal that contradicts a **non-blank** backend value is a **conflict**, never an
automatic fill (data-fill is additive to blanks/`unknown`s — Data-fill SOP §9,
[ref]-Fill SOP §8). `apply_batch.py` routes these to `conflicts.csv` with the backend
value, the research value, sources, and a recommendation. Decide each by hand; if you
accept one, apply it as a deliberate single-cell edit (the by-name applier with
`OVERWRITE_NONBLANK=true`, or a direct edit). Keep the conflict record in the batch.

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
  `accept` in `decisions.csv`. No script writes to the backend without that ([ref]-Fill §4.7).
- **Apply by name or by full row — never cherry-pick cells by hand.** Both supported paths
  address columns by header (applier) or paste full backend-width rows (apply_rows.csv);
  neither can land a value in the wrong column.
- **Always `verify_apply.py --pull` after applying.** An unverified apply is an open loop.
- **Conflicts are decided, not auto-applied.** Additive-to-blanks holds.
- **Review the dedupe sweep before calling a batch done.** §5a is advisory (it won't fail
  the apply), but a HIGH/MED group means a row may duplicate an existing vessel — resolve it.

## 8. Changelog

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
