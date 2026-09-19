# review_app — decide a batch's proposals

The review surface for accept / hold / reject decisions, replacing the combined xlsx.
Build spec: `docs/plans/2026-09-18_review-app.md`. Run everything from the repo root.

The app never touches the backend. It writes only the `decision` column of each batch's
`decisions.csv` plus an append-only audit log (`review_log.jsonl`). Accepted proposals reach the
sheet through the Apply SOP (`docs/sops/apply.md`), unchanged.

## Entry points

1. `review_data.py` builds `work/review_data.json` (gitignored — it holds backend data):

   ```bash
   python scripts/pull_backend.py                      # fresh pull first (refuses without one)
   python review_app/review_data.py --batches batches/<dir> [<dir> ...]
   ```

   Labels, apply order and the applied marker come from a `review_batches.json` in a
   `batches/*/` dir that names the batches (the sep-17-pass one lives in its combined dir);
   without one, label = dir name, order = dir sort order, applied = `verify_report.csv` exists.

2. `server.py` serves the front end (`web/`) on `http://127.0.0.1:8765/` (loopback only;
   standard library, no network calls of its own):

   ```bash
   python review_app/server.py --batches batches/<dir> [<dir> ...]   # rebuilds review_data.json first
   python review_app/server.py                                         # serves the existing one
   ```

   `--reviewer NAME` (default `git config user.name`), `--port`, `--no-open`. The page shows
   the batches' current `decisions.csv` state, so it can be reloaded at any time.
   Keys: `j`/`k` line, `J`/`K` vessel, `a`/`h`/`r` accept / hold / reject, `s` suggest, `u` undo,
   `o` open the first ref, `d` details, `/` search, `?` help.

   **What a line shows.** Column, `was → proposed`, then **Why** (the note's one reason) and
   **Source** (a named link — `IGU World LNG Report 2026, p.71` opens the PDF at that page; a
   shipvault page and its unit-record companion are one source, the record behind `(data ↗)`)
   with the §3.8 gate's result in words: `✓ verified`, `✗ failed the gate` (+ the gate's
   reason), `read by hand`, `not checked`. Everything else — the note's provenance tail, the
   `[ref]` being replaced, the raw gate verdicts — is under **details** (`d`). `review_data.py`
   makes the split at build time (`why` / `detail` / `sources`, next to the untouched `note` /
   `refs`); nothing is dropped except a leading restatement of `'current' -> 'proposed'`.

   Each decision is saved the moment it is made, per batch and under a lock: the record is
   appended to `batches/<dir>/review_log.jsonl` (who, when, via, note — commit it with the
   batch), then only the `decision` cell of that line in `decisions.csv` is rewritten (every
   other byte kept; temp file + rename). A bad request writes nothing. Undo appends a new
   record; the log is never rewritten. Deciding one side of a linked pair (`Name` ↔
   `Other names`, `Price` ↔ `Price currency`, `Capacity` ↔ `Capacity units`, `X` ↔ `X [ref]`)
   asks about the other; for `Name` ↔ `Other names` the answer is both or neither (RF §4.16).
   A line from an already-applied batch stays decidable, but changing it unapplies nothing.

   **Bulk.** The status bar's "apply to all N filtered" (accept / hold / reject) always confirms
   first, restating the filter and how many lines change; records carry `via: "bulk:<filter>"`.
   When the filter catches only one half of a linked pair the dialog names the partners and
   offers to include them (`Name` ↔ `Other names` partners are always included).

   **Items tab.** Conflicts, manual-review entries, the proposed bucket, duplicate pairs and
   discovery flags, with a status (`open` / `resolved` / `needs research`) and a note, appended
   to `batches/<dir>/review_items.jsonl`. They feed the worklist, not the apply. A conflict also
   takes a call (accept / hold / reject), written into that record's `decision` cell in
   `conflicts.csv` (byte-preserving, refused if the record no longer matches). An accepted
   conflict is still applied by hand (AP §4). `apply_batch.py` regenerates `conflicts.csv` with
   every call back at `hold`; the log keeps the call and the tab flags the drift — save again to
   rewrite it.

   **Session summary.** Decisions and item calls made this session by batch, the
   `apply_batch.py` command for each batch whose decisions changed, and the suggestions pending.

   **Suggest…** (`s`) records a different value for a line instead of its proposal: the value,
   a required note, and a kind — `value` (a different fact; the original refs are re-gated
   against it) or `cosmetic` (spelling / stylization, same fact; the cell's `[ref]` is kept).
   It is stored as `reject` in `decisions.csv` and as `suggest` in the log. Nothing is applied
   from the app. Not offered on discovery new rows or ref-only lines.

3. `suggestions.py` turns the pending suggestions into a standard `fix.json`, so a suggested
   value reaches the backend only through the QC-SOP path (`docs/sops/qc_release.md`):

   ```bash
   python review_app/suggestions.py --batches batches/<dir> [<dir> ...]   # -> work/review_suggestions_fix.json
   python scripts/other_names.py --batch work/review_suggestions_fix.json  # when a Name changes (RF §4.16)
   python scripts/build_workbook.py --mode fix --fix work/review_suggestions_fix.json \
       --out batches/<date>_<HHMMET>_fix_review_suggestions/
   python scripts/recalc.py batches/<dir>/lng_carrier_fix.xlsx
   ```

   A suggestion = latest log record `suggest` while the csv line still says `reject` (a later
   decision or a hand edit supersedes it). Each cell keeps the original proposal's refs and
   confidence, and `build_workbook.py`'s §3.8c gate is the re-gate. `cosmetic` → `preserve_ref`
   (gated as a value when the backend cell has no `[ref]`); `Other names` → `append_ref` with
   the one added element as `gate_value`; a data-fill cell that already carries refs →
   `append_ref` (Data-fill SOP §4). The same cell suggested in two batches keeps the later one.
   Discovery and ref-only suggestions are reported, not emitted. Read-only over the batches and
   the backend; writes only `--out`.

## What a session leaves in a batch dir

| file | written by | commit it |
|---|---|---|
| `decisions.csv` | the `decision` column only | yes (it already is) |
| `review_log.jsonl` | every decision, undo and suggestion — append-only, latest record per key wins | yes |
| `review_items.jsonl` | Items-tab statuses, notes and conflict calls — append-only | yes |
| `conflicts.csv` | a conflict's call in `decision` (reset to `hold` by `apply_batch.py`) | yes |

`work/review_data.json` (backend data) and the `--out` of `suggestions.py` stay in `work/`.
Tests: `tests/test_review_data.py`, `tests/test_review_app.py`, `tests/test_review_suggestions.py`.
