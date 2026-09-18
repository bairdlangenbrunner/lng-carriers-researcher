# Review app — plan (written 2026-09-18)

An interactive way to make a batch's accept / hold / reject decisions, replacing the combined
xlsx as the review surface. Built locally first (phase 1), then shared with Rob and other
researchers through Google Apps Script (phase 2). This file is the build spec: a fresh session
should be able to build phase 1 from it without the conversation that produced it.

## Decisions already made (Baird, 2026-09-18)

- **Shared backend = Google Apps Script + a Google Sheet.** Free (no billing account exists to
  charge), GEM Google login for free, data never on the public web. Not Supabase, not GitHub
  Pages — Pages is static and public, and the proposals are unreleased tracker data.
- **One reviewer's decision settles a proposal.** No second sign-off. Every decision still
  records who and when.
- **Edits go through "suggest a value" (option 2).** A reviewer never types a value that gets
  applied directly. A suggestion is recorded, then routed through a `fix` batch, whose build
  already runs the §3.8c value↔ref gate. Cosmetic suggestions use `preserve_ref`.
- **Nothing may cost money.**
- **Build on a cheaper model.** The design is settled here; the build is well-specified. See
  "Model guidance" at the end.

## What was borrowed from allfrequencies.app

A colleague's artist directory (Next.js + Supabase; source not public; the admin queue is behind
a login and was not seen). What its public side and one shipped moderation component show:

- The unit of review is the **entity** (an artist), not a field. Ours: a **vessel card**.
- A correction is the record's own form, **pre-filled with current data**, plus "what changed and
  why". Ours: every line shows current → proposed, with the note and the refs.
- Decide **in place**, each decision **saved the moment it is made**, the result shown at once
  ("Saving…" → a quiet "Approved" label). No separate save step, nothing to lose.
- A **confirm step** before a write. Ours: confirm only on bulk actions; single decisions are
  one keypress with undo (528 holds with a confirm each would be slower than the xlsx).
- Status enum `pending / approved / rejected / not_eligible` ↔ our `hold / accept / reject`.

## Hard rules the app must keep

- **It never touches the backend.** It only writes decisions. Accepted proposals still reach the
  sheet through the Apply SOP (`apply_batch.py` → `apply_patch.csv` → `tools/apply_patch.gs` →
  `verify_apply.py`), unchanged.
- **No value is applied that has not passed §3.8c.** Hence suggestions, not edits.
- **Always show the live sheet row**, never the column-A `row_id`, to a human
  (`apply_batch.sheet_row_map`). `row_id` stays the key.
- **The Name line and its `Other names` line are decided together** (RF §4.16).
- The app makes **no network calls** of its own (refs open in the reviewer's browser).
- `work/` is gitignored and stays so; `review_data.json` holds backend data and lives there.
- No push without Baird's approval; commits lowercase and succinct; no Claude attribution.

## Facts about the existing data the builder must know

Verified against the repo on 2026-09-18:

1. **`decisions.csv` is the decision store the pipeline reads**, one per batch dir. Columns:
   `id, kind, row_id, cluster_id, column, confidence, derivable, default, decision,
   proposed_value, note`. `id` is `row_id|column` (or `cluster:<cid>` for a discovery new row).
2. **`decisions.csv` is lossy — do not use it as the display source.** `_write_decisions`
   truncates `proposed_value` and `note` to 80 characters; 1,282 of the 2,125 sep-17-pass lines
   hit that cut. Full values come from `apply_batch._detect(batch_dir)` +
   `apply_batch._items_and_conflicts(mode, payload, header, colmap)`, which return each item with
   full `value`, `ref_value` (comma-joined URLs), `ref_column`, `note`, `prev_state`, and for
   discovery `row_data` / `cluster_label`. Import and call these; do not re-parse the batch JSON.
3. **`apply.json` holds accepted cells only** — useless for showing holds.
4. **Re-running `apply_batch.py` preserves only the `decision` column** (`_load_or_init_decisions`
   reads `id` → `decision`). Any extra column written into `decisions.csv` is lost on the next
   run. Reviewer, timestamp, note and suggestion therefore live in a sidecar (below).
5. **`id` is unique within a batch, not across batches.** 36 ids appear in more than one
   sep-17-pass batch (the same cell proposed twice). The app's key is `<batch_dir>::<id>`.
6. **Gate verdicts**: two fix batches carry `gate_log.json` (list of `{row_id, field, value, url,
   ok, reason, grade}`). For the rest, the combined builder reads the QA sheets of each batch
   workbook (`qa_sections` in `batches/2026-09-17_1017ET_sep-17-pass_combined/build_combined.py`)
   — reuse that approach; a missing verdict is shown as "—", never invented.
7. **Non-cell review items** exist alongside proposals: `conflicts.csv` per batch
   (`row_id, column, backend_value, proposed_value, sources, recommendation, decision`),
   `manual_review.json`, `proposed_review.json`, and the dedupe reports. The combined
   `report_data.json` shows the shapes already flattened (`flags` 155, `manual` 54,
   `proposed_bucket` 34) and `build_combined.py` shows how each was assembled.
8. **Linked columns**, by exact backend header: `Name` ↔ `Other names`; `Price` ↔
   `Price currency`; `Capacity` ↔ `Capacity units`; and every `X` ↔ `X [ref]` (a `kind: ref`
   line). Derive the header from the fresh pull — never hard-code indices.
9. Default decision = `accept` when `derivable` or confidence `G`, else `hold`
   (`apply_batch._default_decision`). The sep-17-pass: 2,125 proposals, 1,596 accept / 528 hold /
   1 reject; 414 of the holds are batch 4's single-source (Y) cells, heavily patterned by column.
10. `tests/` uses pytest from the repo root; `conftest.py` puts `scripts/` on `sys.path`.

## Architecture

```
batches/<dir>/{fix,data_fill,candidates,citations}.json ─┐
batches/<dir>/decisions.csv, conflicts.csv, gate_log.json ├─> review_app/review_data.py ─> work/review_data.json
work/backend.csv (fresh pull)                            ─┘                                   │
                                                                                              v
                       review_app/web/ (static front end, vanilla JS)     <── Store adapter ──>  review_app/server.py
                                                                                          (local server, phase 1)
                                                                                              │ writes
                                          batches/<dir>/decisions.csv (decision column only) ─┤
                                          batches/<dir>/review_log.jsonl (audit sidecar)      ─┘
                                                                                              v
                     review_app/suggestions.py ─> work/review_suggestions_fix.json ─> normal `fix` batch
                     then, per touched batch: python scripts/apply_batch.py --batch <dir>   (Apply SOP, unchanged)
```

Phase 2 swaps the Store adapter (local HTTP → `google.script.run`) and adds a publish / pull
pair; the front end and everything downstream of `decisions.csv` do not change.

### Where it lives

Everything app-specific sits in one folder, apart from the research pipeline in `scripts/`:

```
review_app/
  README.md          how to run it; the three entry points
  review_data.py     builds work/review_data.json
  server.py          local server (phase 1 Store); --bundle for phase 2
  suggestions.py     suggestions -> fix.json
  web/               index.html, app.js, style.css
  gas/               phase 2: Code.gs + the bundled index.html (publish.py / pull.py join review_app/)
tests/test_review_*.py   with the other tests
```

- The app imports pipeline code (`apply_batch`, `backend_io`, `paths`) from `scripts/`: each entry
  point puts `scripts/` on `sys.path` (as `build_combined.py` does) and `tests/conftest.py` gains
  `review_app/`. Nothing in `scripts/` imports from `review_app/` — the dependency runs one way.
- `.claude/settings.json` allows `Bash(python scripts/*)`; add `Bash(python review_app/*)` beside it.
- Run from the repo root, like everything else; `paths.py` anchors `work/` regardless.

### 1. `review_app/review_data.py` — build the review dataset

`python review_app/review_data.py --batches batches/<dir> [<dir> ...] [--out work/review_data.json]`

- Requires a fresh `work/backend.csv` (refuse to run if it is missing; warn if older than a day).
- Per batch: `_detect` + `_items_and_conflicts`, joined with `decisions.csv` (current decision)
  and the backend row (context + current value).
- Output shape:

```jsonc
{
  "built": "2026-09-18T14:05:00-04:00",
  "backend_pulled": "…",                       // mtime of work/backend.csv
  "batches": [{"dir": "2026-09-17_0421ET_fix_delivery_rollforward", "mode": "fix",
               "label": "…", "apply_order": 1, "counts": {"accept": 0, "hold": 0, "reject": 0}}],
  "vessels": [{
    "row_id": "6", "live_row": 827,            // live_row null + "new": true for a discovery cluster
    "name": "Hull 045 (Zvezda)", "imo": "9904704", "status": "on order",
    "shipbuilder": "…", "shipowner": "…",
    "proposals": ["<key>", …]                  // ordered by apply_order, then backend column order
  }],
  "proposals": {
    "<batch_dir>::<id>": {
      "batch": "<batch_dir>", "id": "6|Status", "kind": "fill|ref|new_row",
      "row_id": "6", "cluster_id": "", "column": "Status",
      "current": "on order", "proposed": "active",          // FULL values, untruncated
      "refs": [{"url": "…", "verdict": "PASS (OK …)" }],    // verdict null when unknown
      "ref_column": "Status [ref]", "current_refs": ["…"],
      "confidence": "G", "derivable": false, "prev_state": "fix",
      "default": "accept", "decision": "accept",
      "note": "…",                                          // full
      "links": ["<key>", …],      // linked-cell partners (fact 8) + same cell in another batch
      "flags": ["preserve_ref", "append_ref", "ref_only", "overlaps_batch"],
      "row_data": null            // discovery: the whole proposed row
    }
  },
  "items": [{"item_id": "…", "type": "conflict|manual|proposed_bucket|duplicate|flag",
             "batch": "…", "live_rows": [1168], "title": "…", "detail": "…", "urls": ["…"]}]
}
```

- `label` / `apply_order` come from an optional `batches/<combined>/review_batches.json`
  (dir → label, order); absent that, label = dir name and order = dir sort order. Do not import
  the sep-17-pass `BATCH_INFO` constant — it is pass-specific.
- Must be deterministic (stable key order) so rebuilds diff cleanly.

### 2. `review_app/web/` — the front end

`review_app/web/index.html`, `app.js`, `style.css`. **Vanilla JS, no framework, no CDN, no build
step, no ES-module imports** — phase 2 serves it from Apps Script `HtmlService`, which wants
inlinable files. All state in one in-memory object loaded once; filtering is client-side.

All I/O goes through one adapter so phase 2 is a swap:

```js
Store.load()            // -> review_data object
Store.decide(records)   // records = [decision record, …]; resolves to the saved records
Store.whoami()          // -> reviewer string
```

**Decision record** (one per proposal per action; the log is append-only, latest wins):

```jsonc
{"key": "<batch_dir>::<id>", "decision": "accept|hold|reject|suggest",
 "suggested_value": "", "suggest_kind": "value|cosmetic",   // only with "suggest"
 "note": "", "reviewer": "baird", "ts": "2026-09-18T14:07:11-04:00",
 "via": "single|bulk:<filter description>|linked"}
```

**Screens**

- **Queue (default).** Left: vessel list (live row, name, builder/owner, count of undecided
  lines). Right: the selected **vessel card** — header with backend context, then one line per
  proposal: column · current → proposed (a real diff for long text such as `Other names`) ·
  confidence chip (G / Y / R colours as in the workbooks) · gate verdict · refs as links
  (open in a new tab) · note · batch label · the accept / hold / reject / suggest control.
  Linked lines are visually bracketed. A discovery cluster renders its `row_data` as a full
  proposed row and is decided as one unit.
- **Filters** (combine freely; the count updates live): decision state, batch, column,
  confidence, kind, shipbuilder, shipowner, "changed by me", text search (name / IMO / row).
  Default view = `decision: hold`. Progress bar: decided-this-session and holds remaining.
- **Bulk.** "Apply to all N filtered": accept / hold / reject. Always a confirm dialog that
  restates the filter and N ("accept 68 lines — batch 4 · Contract date · Y"). The records carry
  `via: "bulk:<filter>"`. Bulk never crosses a linked pair silently: if a filter catches one
  half of a pair, the dialog says so and offers to include the partners.
- **Items tab.** Conflicts, manual-review entries, proposed bucket, duplicate pairs, flags:
  read-only detail + status `open / resolved / needs research` + note. These feed the worklist;
  they do not feed the apply. (Conflicts are still decided by hand per AP — the app records the
  call, `conflicts.csv` `decision` column gets it on import.)
- **Session summary.** Decisions made this session by batch, the list of touched batch dirs, and
  the exact commands to run next (section 4). Suggestions pending.

**Behaviour**

- Single decision: one click or keypress, saved immediately, inline "Saving…" → state label;
  `u` undoes the last action (writes a new record restoring the prior decision — the log is
  never rewritten).
- Keyboard: `j/k` next / previous line, `J/K` next / previous vessel, `a` accept, `h` hold,
  `r` reject, `s` suggest, `o` open the line's first ref, `/` search, `?` shortcut help.
- Linked pair: deciding one side prompts "same for `<partner>`?" (default yes); a pair left in
  different states shows a warning chip. For `Name` ↔ `Other names` the prompt is not skippable.
- Same cell in two batches (`overlaps_batch`): both lines shown together in apply order with
  "the later batch wins on apply".
- **Suggest.** Opens a small form: the proposed value pre-filled and editable, a
  `value` / `cosmetic (spelling, stylization — same fact)` toggle, a required note. Saving sets
  the line to `suggest`; the UI states plainly that nothing is applied until it passes the gate.
- A save failure is loud (the line turns red and stays undecided); never optimistic-only.
- Light and dark theme; works at laptop width; no horizontal scroll on the card.

### 3. `review_app/server.py` — local server (phase 1 Store)

`python review_app/server.py [--batches …] [--reviewer NAME] [--port 8765] [--no-open]`

- Standard library only (`http.server`), binds `127.0.0.1`. Builds `review_data.json` first if
  `--batches` is given. Reviewer defaults to `git config user.name`.
- `GET /` static files · `GET /api/data` · `GET /api/whoami` · `POST /api/decide` (a list of
  decision records).
- On `decide`, per batch touched, under a process lock:
  1. append the records to `batches/<dir>/review_log.jsonl` (the audit trail; committed with
     the batch);
  2. rewrite **only the `decision` column** of `decisions.csv` for those ids — every other byte
     of every row preserved, same column order, same quoting (`csv` module, `newline=""`);
     `suggest` is written as `reject` (the value as proposed is not wanted; its replacement
     arrives through the fix batch);
  3. write atomically (temp file + `os.replace`) — the repo lives in Dropbox.
  Unknown key or a decision outside the enum → 400, nothing written.
- Item statuses (Items tab) go to `batches/<dir>/review_items.jsonl`; conflict calls are also
  written to that batch's `conflicts.csv` `decision` column.

### 4. `review_app/suggestions.py` — suggestions → a fix batch

`python review_app/suggestions.py --batches <dirs> --out work/review_suggestions_fix.json`

- Collects the latest `suggest` record per key and emits a standard `fix.json` (`corrections` →
  `cells`): `field`, `new_value` = the suggested value, `refs` = the original proposal's refs,
  `confidence` = the original's, `note` = reviewer + note. `suggest_kind: cosmetic` →
  `preserve_ref: true` and no refs. Discovery suggestions are out of scope (report them).
- Then the normal QC-SOP path, nothing new: `other_names.py --batch` when a Name cell is present
  → `build_workbook.py --mode fix` (**this is the re-gate**: fix mode drops every ref that does
  not contain the cell value) → `recalc.py` → `batch_digest.py` / `apply_batch.py`. A suggestion
  whose refs all fail surfaces there as an unsourced cell = "needs a source"; print that list.
- After reviewing, per touched batch: `python scripts/apply_batch.py --batch batches/<dir>` to
  regenerate the apply artifacts from the new decisions. The Session summary prints these lines.

### 5. Tests (`tests/test_review_data.py`, `tests/test_review_app.py`)

Fixture: a tiny backend CSV + one batch dir per mode, built in `tmp_path`.

- full values survive (a 300-char `Other names` proposal is not truncated in `review_data.json`);
- the same `id` in two batches yields two keys, each linked to the other with `overlaps_batch`;
- linked pairs are found from header names (`Name`/`Other names` across two batches,
  `Price`/`Price currency`, `Capacity`/`Capacity units`, `X`/`X [ref]`);
- `live_row` comes from `sheet_row_map`, not `row_id`;
- a decide call changes only the `decision` cells — byte-compare every other field, and a
  following `apply_batch.py` run keeps the new decisions and produces the expected patch;
- `suggest` → `reject` in `decisions.csv`, full record in `review_log.jsonl`; undo appends;
- bad key / bad enum → 400 and no file changes; a failed write leaves the original file intact;
- `suggestions.py`: value → refs carried; cosmetic → `preserve_ref` and no refs;
- the server refuses to bind anything but loopback.

### 6. Docs to update when phase 1 lands (same PR)

- `CLAUDE.md`: a "Review a batch's decisions" router entry (trigger phrases: "review app",
  "decide the holds", "open the review app"), a `review_app/` entry in Repository orientation pointing at
  `review_app/README.md` (the three entry points are documented there, not in the Scripts table).
- `docs/sops/apply.md`: step 2 ("edit the holds") gains the app as the recommended surface;
  `decisions.csv` by hand stays valid. Bump the AP rev and `docs/pointers.md`.
- The sep-17-pass worklist step 2 points at the app.

## Phase 1 milestones (each ends with passing tests and a commit)

1. `review_app/` skeleton (layout above) + `review_data.py` + tests; run it on the eleven un-applied sep-17-pass batches; check the
   totals against the worklist (2,125 / 1,596 / 528 / 1) and spot-check three long-text lines.
2. Server + Store + read-only UI (queue, card, filters, keyboard navigation).
3. Single decisions, undo, linked-pair prompts, write-back + tests.
4. Bulk with confirm; Items tab; session summary.
5. Suggest + `suggestions.py` + tests; run one real suggestion through a fix build.
6. Docs (section 6). Then Baird uses it on the 528 holds — that is the acceptance test.

## Phase 2 — Google Apps Script (do not start until phase 1 has been used for real)

**Every step that creates or changes a work Drive file needs Baird's explicit OK, each time**
(creating the spreadsheet, creating the script project, every publish). Reads use `gws-gem`;
writes use `gws-gem-write`. Never an anonymous export URL.

- **Store**: a new spreadsheet, separate from the backend, tabs `proposals` (one row per
  proposal, one column per field — *not* a JSON blob: a cell holds at most 50,000 characters),
  `vessels`, `items`, `decisions` (append-only log, same record as phase 1), `meta`.
  Calibri 10 pt, minimal formatting.
- **Script**: `doGet()` serves the bundled front end via `HtmlService`;
  `getData()` returns the dataset (chunk by batch if a single return is too large — measure it);
  `decide(records)` appends to `decisions` under `LockService.getScriptLock()`, stamping
  `Session.getActiveUser().getEmail()` as reviewer server-side (never trust the client's).
  Deploy as a web app restricted to the globalenergymonitor.org domain. **Verify** at build time
  which "execute as" setting both exposes the viewer's email and avoids giving reviewers edit
  access to the store sheet; this was not tested.
- **Bundle**: `python review_app/server.py --bundle review_app/gas/` inlines `app.js` / `style.css` into one
  `index.html` and swaps in the `google.script.run` Store adapter. Script source in
  `review_app/gas/Code.gs`; deployed by paste or `clasp` (both free).
- **Round trip**: `review_app/publish.py` (review_data → sheet; write, ask first) and
  `review_app/pull.py` (sheet `decisions` → the phase 1 write-back function, then
  `review_log.jsonl`; read-only). Everything after the pull is phase 1's path.
- Quotas are generous for this load (one load call per session, one tiny append per decision);
  a quota hit is a failed call shown in the UI, never a charge.
- Staleness: `meta` carries `built` and the backend pull time; the UI warns when the published
  set is older than the newest batch commit, and a publish over undecided-but-changed lines
  must not drop existing decisions (decisions are keyed, the log is append-only).

## Open items

- Ask the colleague for a look at her admin queue — nice to have, no longer blocking.
- Whether conflicts should become decidable proposals in the app (today: recorded, applied by
  hand per AP). Leave as is unless Baird asks.
- Second-ref question for IGU-2026-only cells is a worklist decision, not an app feature — but
  the filter "refs = IGU PDF only" would make that review easy; add it if cheap.

## Model guidance

The build is mechanical from this spec — run it on Opus (or Sonnet for the test-writing and CSS
passes). Come back to the top tier only for: an SOP conflict, a change to the decision /
suggestion semantics above, anything touching how `apply_batch.py` interprets `decisions.csv`,
and the phase 2 "execute as" / permissions call. Verification is the same regardless of model:
the tests in section 5, the milestone-1 totals check, and Baird's use on the real holds.
