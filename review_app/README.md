# review_app — decide a batch's proposals

The review surface for accept / hold / reject decisions, replacing the combined xlsx.
Build spec: `docs/plans/2026-09-18_review-app.md`. Run everything from the repo root.

Deciding never touches the backend: accept / hold / reject write only the `decision` column of
each batch's `decisions.csv` plus an append-only audit log (`review_log.jsonl`). Accepted
proposals reach the sheet through the Apply SOP (`docs/sops/apply.md`) — by hand as before, or
with the **push accepted** button below (AP §2b), the app's one backend write: it lists every
cell first and writes on one confirmation.

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
   standard library; its outward calls are the **sync backend** pull and the **push accepted**
   write below):

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

   **Sync backend** (the `↻ sync backend` button, `POST /api/refresh`). Re-runs
   `scripts/pull_backend.py` (read-only profile), rebuilds the dataset over the same batch dirs
   and takes it in place — filters and the session summary stay. Every line is compared with
   the fresh pull (whitespace- and number-normalised, as `verify_apply.py` does): value and
   proposed refs both there → flag `in the backend`; value there, a proposed ref missing →
   `value in the backend` (shown, never auto-decided). A discovery row is in the backend when
   its Name or Hull number is. Then what the backend already settles is settled: a **held**
   line that is `in the backend` becomes `accept`, an **open** conflict whose proposed value
   the backend now holds, or duplicate pair with a row gone, becomes `resolved` — through the
   ordinary write paths, logged as reviewer `backend sync`, `via: "sync:backend"`. A line
   someone already decided is never touched. A failed pull changes nothing. The sync reads
   the backend; it never writes it.

   **Push accepted** (the `⇪ push accepted` button; `POST /api/push/plan`, `POST /api/push`;
   `push.py`). Never on a click of `accept` — and only for lines someone did click accept on
   (latest `review_log.jsonl` record is a reviewer's accept; a pre-filled or backend-sync accept
   is counted in the dialog and not pushed). The server re-pulls, then plans: every cell the
   accepted lines would change — the same cells `apply_patch.csv` carries
   (`apply_batch.cell_writes`), laid over the pull in apply order — and the dialog lists them by
   batch (live row, vessel, column, now → becomes). One confirmation writes exactly that plan: it
   carries the plan's token, the server re-pulls and recomputes, and a plan that changed in
   between (the sheet or a decision moved) is refused with nothing written. Cells are addressed
   by row_id + header against the fresh pull, written RAW through `gws` under the work **write**
   profile (`~/.config/gws-gem-write`), then re-pulled and verified cell by cell; what landed is
   appended to `<dir>/push_log.jsonl`. With a batch picked in the Batch filter the push covers
   that batch only. Not pushed — these stay by hand: discovery new rows, conflicts, suggestions
   (a fix batch), and a data-fill / ref-fill value whose cell is no longer blank or `unknown`
   (additive to blanks; the dialog lists these under "not pushed"). Cells of an
   already-applied batch that differ from the sheet (likely a later hand edit) are listed apart
   and written only when the box is ticked. Reject and hold write nothing, and a reject never
   reverts a cell. A push does not write `verify_report.csv`: run `verify_apply.py --pull` to
   close the batch (dedupe sweep included).

   **Card links and Back.** On a card, the vessel name, IMO, shipbuilder and shipowner are links:
   a click filters the queue to just that (every other filter cleared, decision `any`), so a
   name or IMO shows everything queued for the vessel. The tab, the filters and the selected
   vessel live in `location.hash`: a changed tab or filter is a history entry (moving between
   vessels and typing on in the search box replace it), so the browser's Back / Forward walk the
   filter history and a reload or bookmark returns to the same view. Only the view is restored —
   decisions are saved as they are made and stay.

   **Bulk.** The status bar's "apply to all N filtered" (accept / hold / reject) always confirms
   first, restating the filter and how many lines change; records carry `via: "bulk:<filter>"`.
   When the filter catches only one half of a linked pair the dialog names the partners and
   offers to include them (`Name` ↔ `Other names` partners are always included).

   **Filters.** Decision, Batch and Search stay in view; Column, Confidence, Kind, Flag, Builder,
   Owner and "changed by me" sit behind **More filters**. Whatever is set there shows as a
   removable chip while the panel is closed, so a hidden control never filters silently.

   **New rows.** A discovery row's sources are numbered once under **Sources**; the row table
   cites them as `[1] [2]` beside each value instead of repeating the URLs. A long reason is
   clamped to four lines with **more**.

   **Items tab.** Conflicts, manual-review entries, the proposed bucket, duplicate pairs and
   discovery flags, grouped by backend row (the row link opens the vessel in the queue) and
   opening on `open` items. Status (`open` / `resolved` / `needs research`) and a conflict's call
   are one-click buttons that save at once (a call other than `hold` also resolves an open
   item); the note saves when you leave the box. Each save is appended
   to `batches/<dir>/review_items.jsonl`. They feed the worklist, not the apply. A conflict also
   takes a call (accept / hold / reject), written into that record's `decision` cell in
   `conflicts.csv` (byte-preserving, refused if the record no longer matches). An accepted
   conflict is still applied by hand (AP §4). `apply_batch.py` regenerates `conflicts.csv` with
   every call back at `hold`; the log keeps the call and the tab flags the drift — press the call
   again to rewrite it.

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
| `decisions.csv` | the `decision` column only (a sync's accepts included) | yes (it already is) |
| `review_log.jsonl` | every decision, undo, suggestion and sync accept — append-only, latest record per key wins | yes |
| `push_log.jsonl` | every cell a push wrote and verified (row, column, old → new, who, when) — append-only | yes |
| `review_items.jsonl` | Items-tab statuses, notes, conflict calls and sync resolutions — append-only | yes |
| `conflicts.csv` | a conflict's call in `decision` (reset to `hold` by `apply_batch.py`) | yes |

`work/review_data.json` (backend data) and the `--out` of `suggestions.py` stay in `work/`.
Tests: `tests/test_review_data.py`, `tests/test_review_app.py`, `tests/test_review_suggestions.py`.
