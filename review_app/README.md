# review_app — decide a batch's proposals

The review surface for accept / hold / reject decisions, replacing the combined xlsx.
Build spec: `docs/plans/2026-09-18_review-app.md`. Run everything from the repo root.

Deciding never touches the backend: accept / hold / reject write only the `decision` column of
each batch's `decisions.csv` plus an append-only audit log (`review_log.jsonl`). Accepted
proposals — and the reviewer's own suggestions — reach the sheet through the Apply SOP
(`docs/sops/apply.md`): by hand as before, or with the **push changes** button below (AP §2b),
the app's one backend write: it lists every cell first and writes on one confirmation.

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
   standard library; its outward calls are the **sync backend** pull, the **push changes**
   write and the living-workbook sync below):

   ```bash
   python review_app/server.py --batches batches/<dir> [<dir> ...]   # rebuilds review_data.json first
   python review_app/server.py                                         # serves the existing one
   ```

   `--reviewer NAME` (default `git config user.name`), `--port`, `--no-open`, `--no-living`
   (leave the living workbook alone this session). The page shows
   the batches' current `decisions.csv` state, so it can be reloaded at any time.
   Keys: `j`/`k` line, `J`/`K` vessel, `a`/`h`/`r` accept / hold / reject, `s` suggest, `u` undo,
   `o` open the first ref, `d` details, `/` search, `?` help.

   **Suggested vs decided.** A line carries two things. `decision` is what `decisions.csv`
   holds — pre-filled by the batch (`apply_batch.py`, by confidence) until someone decides —
   and `reviewed` is the researcher's own call (`store.reviewed`: the latest
   `review_log.jsonl` record, when it is a person's, is not an undo back to undecided, and
   still matches the csv; else `null`). The page is drawn from `reviewed` alone: every card
   starts undecided, with the pre-fill shown as a `batch suggests …` chip coloured by the
   confidence grade (green G / yellow Y / red R — there is no separate letter chip). Accept, reject and
   suggest gray the card out; hold keeps it bright. **Clicking the pressed button again clears
   the call** — the line is undecided again and `decisions.csv` gets the batch's pre-fill back
   (an `undecided` log record, the same one an undo writes; a linked partner is asked about as
   usual). A suggestion is cleared from its form (*Clear suggestion*). The `a`/`h`/`r` keys
   never clear — `u` undoes. A line of an already-applied batch, or one
   the backend already holds, is grayed too. Gray never means "filtered out": a line the set
   filter does not match is not drawn at all (the card ends with `N more lines on this vessel are
   hidden by the filter — show all`); the one exception is a line decided on the open card, which
   stays, grayed, until the vessel or the filter changes, so a misclick can be clicked back. A line `in the backend` (value and refs, as
   of the last sync) leaves the queue altogether, unless someone rejected it or suggested
   another value (More filters → *show lines already in the backend* brings them back). The
   Decision filter follows `reviewed`; its default, *to decide*, is every bright card
   (*not reviewed* + hold). The pipeline still reads `decisions.csv`, pre-fills included —
   `apply_batch.py` is unchanged; only **push changes** asks for a clicked accept.

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
   batch; `via` says how: `click`, `key`, `linked`, `undo`, `bulk:<filter>`, `single` = a suggestion or a
   record older than 2026-09-21. A keypress also shows a toast naming the line, with an undo button), then only the `decision` cell of that line in `decisions.csv` is rewritten (every
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

   **Push changes** (the `⇪ push changes` button; `POST /api/push/plan`, `POST /api/push`;
   `push.py`). Never on a click of `accept` — and only for lines someone did click accept on
   (latest `review_log.jsonl` record is a reviewer's accept; a pre-filled or backend-sync accept
   is counted in the dialog and not pushed) plus the reviewer's **suggestions** (latest record
   `suggest`). The server re-pulls, then plans: every cell the accepted lines would change — the
   same cells `apply_patch.csv` carries (`apply_batch.cell_writes`), laid over the pull in apply
   order — and, for each suggestion, the cell `suggestions.py` would put in a fix batch
   (`cell_for`: the suggested value; its refs = the URLs typed in the suggestion, gated one by one
   against the suggested value through the §3.8c gate — `igu_refs.corroborates_cell`, IGU landing
   pages swapped for the PDF — passing refs replace the cell's `[ref]`; `cosmetic` with the refs
   left as they were keeps the cell's `[ref]`; `Other names` appends). A suggestion no ref
   corroborates is listed under "not pushed" with each ref's verdict and is never written — add a
   source in the suggestion or take the fix-batch path. The dialog lists every cell by batch
   (live row, vessel, column, now → becomes; a suggested cell carries a *suggested* chip). One
   confirmation writes exactly that plan: it
   carries the plan's token, the server re-pulls and recomputes, and a plan that changed in
   between (the sheet or a decision moved) is refused with nothing written. Cells are addressed
   by row_id + header against the fresh pull, written RAW through `gws` under the work **write**
   profile (`~/.config/gws-gem-write`), then re-pulled and verified cell by cell; what landed is
   appended to `<dir>/push_log.jsonl`. With a batch picked in the Batch filter the push covers
   that batch only. Not pushed — these stay by hand: discovery new rows, conflicts, a suggestion
   without a passing ref (a fix batch), and a data-fill / ref-fill value whose cell is no longer
   blank or `unknown` (additive to blanks; the dialog lists these under "not pushed"). Cells of an
   already-applied batch that differ from the sheet (likely a later hand edit) are listed apart
   and written only when the box is ticked. Reject and hold write nothing, and a reject never
   reverts a cell. A push does not write `verify_report.csv`: run `verify_apply.py --pull` to
   close the batch (dedupe sweep included).

   **Living workbook** (`living.py`, entry point 4 below). Every **sync backend** and every
   **push changes** also mirrors the current decisions into the reconciliation's copy on the
   work Drive — the `processed` column of its `all_proposals` and
   `remaining_changes_backend_shape` tabs — and the banner says how many cells it updated. It
   writes nothing else, anywhere: not a backend cell, not another column. A failure there is
   reported in the banner and changes nothing about the pull or the push.

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

   **Filters.** Decision, Batch, Search and Row stay in view; Column, Confidence, Kind, Flag, Builder,
   Owner and "changed by me" sit behind **More filters**. Row takes live sheet rows — one, a range or
   a list (`1130-1180, 1215`); new rows have no live row and never match it, and the card's `row N`
   label is a click-to-filter link. Every filter that is set — Decision,
   Batch, the search text and the rows included — shows as a chip with an × that clears it, so a hidden
   control never filters silently. The status bar's *N to decide* and its progress bar follow the
   filter too (every facet but Decision, so the bar shows how far the scoped set has come; it reads
   *N to decide here* when a filter is set). The vessel list's badge counts the lines the filter matches
   (it sums to the status bar's count), not everything on the vessel. Under *to decide*, lines
   already in the backend or already applied stay out unless asked for by name — *show lines
   already in the backend*, or Flag → *in the backend* / *already applied* — and then come
   through unless a person settled them. A card link and an Items row link clear every filter,
   that checkbox included. The Items tab's Status / Type / Batch filters keep an item saved
   this session in view until one of them changes.

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
   its **refs** (a box, one URL per line, prefilled with the proposal's own refs — keep, edit or
   replace them; each must be an http(s) URL; stored as `suggested_refs`), a required note, and
   a kind — `value` (a different fact; the refs are gated against it at push time) or `cosmetic`
   (spelling / stylization, same fact; the cell's `[ref]` is kept unless the refs were changed).
   It is stored as `reject` in `decisions.csv` and as `suggest` in the log. Nothing is written
   on submit: **push changes** writes it with the accepted lines once its refs pass the gate.
   Not offered on discovery new rows or ref-only lines. Clicking outside the box
   (or Esc) closes it and keeps what was typed for the next time it opens on that line; Cancel
   discards it. The button reads **Submit suggestion**, or **Resubmit suggestion** once one was
   submitted for the line from this page.

3. `suggestions.py` turns the pending suggestions into a standard `fix.json` — the path for a
   suggestion **push changes** could not write (no passing ref, or the sheet is edited by batch)
   — so it reaches the backend through the QC-SOP path (`docs/sops/qc_release.md`):

   ```bash
   python review_app/suggestions.py --batches batches/<dir> [<dir> ...]   # -> work/review_suggestions_fix.json
   python scripts/other_names.py --batch work/review_suggestions_fix.json  # when a Name changes (RF §4.16)
   python scripts/build_workbook.py --mode fix --fix work/review_suggestions_fix.json \
       --out batches/<date>_<HHMMET>_fix_review_suggestions/
   python scripts/recalc.py batches/<dir>/lng_carrier_fix.xlsx
   ```

   **Reviewer notes are a to-do list.** No script acts on a suggestion's note ("wrong ship, check
   the IMO", "find a better source") — it is only copied into the cell's `note`. So
   `suggestions.py` also prints every suggestion's note, led by the live sheet row, and writes
   them as a checklist to `work/review_suggestions_fix_notes.md`. The session building the fix
   batch reads each one and follows it up (research, another ref, a corrected cell in the
   `fix.json`) **before** `build_workbook.py`; copy the checklist into the batch dir's `notes.md`.

   A suggestion = latest log record `suggest` while the csv line still says `reject` (a later
   decision or a hand edit supersedes it). Each cell carries the refs typed in the suggestion
   (`suggested_refs`; the original proposal's refs when none were) and the proposal's
   confidence, and `build_workbook.py`'s §3.8c gate is the re-gate. `cosmetic` → `preserve_ref`
   (gated as a value when the backend cell has no `[ref]`, or when the refs were changed);
   `Other names` → `append_ref` with
   the one added element as `gate_value`; a data-fill cell that already carries refs →
   `append_ref` (Data-fill SOP §4). The same cell suggested in two batches keeps the later one.
   Discovery and ref-only suggestions are reported, not emitted. Read-only over the batches and
   the backend; writes only `--out`.

4. `living.py` keeps the **living workbook** on the work Drive in step with the backend —
   one Google Sheet in the `claude-output` folder, converted from the reconciliation's combined
   workbook, created once and updated in place so its URL is stable and shareable
   (`data/living_workbook.json` records its id, URL, source workbook and batch set):

   ```bash
   python review_app/living.py --create [--xlsx <combined workbook>]   # once
   python review_app/living.py --sync [--dry-run]                      # what the app does
   python review_app/living.py --rebuild [--xlsx <path>]               # new content, same URL
   ```

   Two tabs carry a `processed` column, written from the current decisions and nothing else:

   | value | means |
   |---|---|
   | `processed - incorporated` | the pulled backend holds it — value and refs (the app's own `in the backend` test), or, for a suggestion, the backend holds the suggested value |
   | `processed - rejected` | someone rejected the line (`apply_batch.py` never pre-fills a reject, so a reject is always a person's call) |
   | `partly processed - N of M` | a backend-shape row with some of the vessel's lines still open |
   | (blank) | still open: undecided, on hold, accepted but not yet written, or a value in the backend whose proposed ref is not |

   The join is by key, not by position: `build_combined.py` writes a `line id`
   (`<batch dir>::<decision id>`) on `all_proposals` and a `line key` (`row:<row_id>`, or
   `cluster:<batch>:<cluster_id>` for a row not in the backend yet) on
   `remaining_changes_backend_shape`, and the sync reads those columns live — so sorting,
   filtering or hiding rows in the sheet can never put a `processed` value on the wrong line, and
   a key the current batch set does not know is left alone. `plan()` refuses any range outside
   the `processed` column. The sync runs only for the batch dirs the workbook was built from
   (`Living.matches`), so a review session over other batches never writes it; `--no-living` or
   `LNGCT_LIVING_SYNC=0` switches it off. Rebuild (not create) after rebuilding the combined
   workbook — `--create` would leave a second copy on the Drive.

## What a session leaves in a batch dir

| file | written by | commit it |
|---|---|---|
| `decisions.csv` | the `decision` column only (a sync's accepts included) | yes (it already is) |
| `review_log.jsonl` | every decision, undo, suggestion and sync accept — append-only, latest record per key wins | yes |
| `push_log.jsonl` | every cell a push wrote and verified (row, column, old → new, who, when) — append-only | yes |
| `review_items.jsonl` | Items-tab statuses, notes, conflict calls and sync resolutions — append-only | yes |
| `conflicts.csv` | a conflict's call in `decision` (reset to `hold` by `apply_batch.py`) | yes |

`work/review_data.json` (backend data) and the `--out` of `suggestions.py` stay in `work/`.
Tests: `tests/test_review_data.py`, `tests/test_review_app.py`, `tests/test_review_suggestions.py`, `tests/test_living.py`.
