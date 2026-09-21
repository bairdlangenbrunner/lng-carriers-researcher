# Handoff — build phase 2 of the review app (Apps Script)

Written 2026-09-21 for a fresh session. Repo: `~/Dropbox/_git_ALL/_github-repos-gem/lng-carriers-researcher`
(work profile `~/.claude-gem`). Run everything from the repo root.

## Read first, in this order

1. `CLAUDE.md` (auto-loaded) — hard rules, the "Review a batch's decisions" router entry.
2. `docs/plans/2026-09-18_review-app.md` — the build spec. **Phase 2 was rewritten 2026-09-21**;
   it is the design and the milestone list. Phase 1 sections describe what exists.
3. `review_app/README.md` — how the local app behaves today (sync, push, Items, suggest, routing).
4. `review_app/web/app.js` lines 1–45 (the `Store` adapter) and 1236–1300 (hash routing);
   `review_app/store.py` (`decide`, `record_items`, `overlay`, `reviewed`); `review_app/server.py`
   (the API the adapter talks to); `review_app/push.py` (stays local — do not port).
5. `tests/test_review_app.py`, `tests/test_review_data.py`, `tests/review_fixture.py` — the test
   style to match. `python -m pytest tests/ -q` must stay green.

## The job

Serve the review app from Google Apps Script so GEM researchers (Rob first) can decide holds from
a browser with their GEM login. The local pipeline stays the source of truth and Baird's machine
stays the only thing that writes the backend. Follow the phase 2 milestones 0 → 5 in the spec.

## Decisions already made — do not reopen

- Apps Script web app, **execute as Baird**, access **domain only** (globalenergymonitor.org).
  Free tier; nothing may cost money; no billing account exists.
- Dataset = **Drive JSON files** (one per batch + `meta.json`) written by `review_app/publish.py`.
- Decisions / items = an append-only **spreadsheet** (`decisions`, `items`, `meta` tabs), rows
  appended under `LockService`, reviewer email stamped **server-side** from `Session.getActiveUser()`.
- **No reviewer allowlist.** Everyone with a globalenergymonitor.org login has access and can
  decide (Baird, 2026-09-21). The domain restriction on the deployment is the only gate; `decide`
  still rejects an empty reviewer email.
- **No backend write path in the shared app.** Push accepted and sync backend are hidden by
  adapter capability flags (`{refresh:false, push:false}`), not forked code.
- Reviewers see each other's decisions live (`getDecisionsSince`, poll 30–60 s, "decided by").
- `review_app/pull.py` feeds store rows through `store.decide()` / `store.record_items()` so
  `decisions.csv` + `review_log.jsonl` get the same records the local app writes; `via` prefixed `gas:`.
- One `Store` object and one `Router` object in the front end, each with a local and a GAS
  implementation; the bundle (`gas/index.html`) is generated and committed.

## Milestone 0 gates everything

Before writing app code: deploy an empty web app with those settings, have a colleague open the
`/dev` URL, and confirm `Session.getActiveUser().getEmail()` returns their address. Time a 1 MB
string returned through `google.script.run`. If the email is empty, switch to execute-as-user
per the spec's fallback and tell Baird before continuing. Report both results to Baird.

## Rules that bite here

- **Every Drive-side create/write is asked about individually, each time**: the data folder, the
  store spreadsheet, the Apps Script project, every `publish.py` run, every deployment. Reads go
  through `gws-gem`, writes through `gws-gem-write` (env: `GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws-gem-write`,
  `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file`). Never an anonymous export URL.
- Never call `/api/push`, `push.write_sheet` or `App.push` against the live sheet from a session
  or a test. Never modify the backend sheet.
- `Code.gs` may `openById` only the store sheet and the data folder; no `UrlFetchApp`.
- `work/` is gitignored and stays so; `review_data.json` holds backend data.
- New sheets/tabs: Calibri 10 pt, minimal formatting.
- `clasp` is not installed. Either `npm install -g @google/clasp` + enable the Apps Script API on
  Baird's work account (ask; the login is interactive — have Baird run it with `!`), or paste-deploy
  the committed bundle. Either is fine; prefer clasp so `review_app/gas/` in git is the source.
- Git: branch → commit → push → PR → merge to `main` is pre-authorized in this repo, no asking.
  Scope commits to the task; leave unrelated uncommitted work alone (the tree currently has
  uncommitted review-log / decisions.csv / app.js changes from the 2026-09-21 review session —
  do not sweep them into a phase 2 commit). Commit messages all lowercase, succinct, no Claude
  attribution.
- Keep docs current as you go: `review_app/README.md` (publish / pull / deploy), `CLAUDE.md`
  router entry, `docs/sops/apply.md` step 2, the sep-17-pass worklist. Bump the AP rev if
  `apply.md` changes.

## Come back to Baird (or a top-tier session) for

- The milestone 0 result and any change to the deployment mode.
- Anything that changes how `apply_batch.py` reads `decisions.csv`, or the decision / suggestion
  semantics in the spec.
- Anything that would give a reviewer a path to the backend sheet.
- Who tests `/exec` first.

## Acceptance

Rob decides ~20 real holds on the `/exec` URL; Baird runs `pull.py`; `apply_batch.py --batch`
shows those decisions; `python -m pytest tests/ -q` green; docs updated; each milestone committed.
