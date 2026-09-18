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
   Keys: `j`/`k` line, `J`/`K` vessel, `a`/`h`/`r` accept / hold / reject, `u` undo,
   `o` open the first ref, `/` search, `?` help.

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
