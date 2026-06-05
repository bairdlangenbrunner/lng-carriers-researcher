# LNG Carrier Tracker — Apply & Verify SOP

**Document purpose:** Operating manual for the **apply** workflow — getting a reviewed
batch's accepted proposals from the candidate workbook back into the Google Sheets
backend, safely and trackably, then verifying they landed. Complements the [ref]-Fill,
Discovery, and Data-fill SOPs (which *produce* candidate batches). **Authoritative** for
the review→apply→verify round-trip. Abbreviated **AP**.

**Last revised:** 2026-06-05 rev 1 (initial SOP). Built after a manual copy/paste column
offset corrupted rows 1216/1217 (CMHI-282-07/-08). The whole point of this workflow is
that the offset class of bug becomes impossible.

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

## 8. Changelog

- **rev 1** (2026-06-05): Initial SOP. Adds `batch_digest.py` (triage), `apply_batch.py`
  (decisions + `apply.json`/`apply_rows.csv`/`apply_patch.csv`/`conflicts.csv`),
  `verify_apply.py` (re-pull diff + qc), and `tools/apply_patch.gs` (by-name applier).
  Built in response to the 1216/1217 manual-paste offset.
