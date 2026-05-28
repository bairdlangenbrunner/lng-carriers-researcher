# Migration checklist

A one-time checklist for moving from the claude.ai Project to this repository. Delete this file once the migration is complete.

**Good news: the scaffold is already fully assembled.** Every file from the claude.ai Project has been migrated, renamed, and path-edited into this directory. You don't need to copy anything out of the Project yourself — just get this directory into a Git repo. The table below is a record of what landed where, in case you want to audit it.

## On your machine

- [ ] Create an empty public repo on GitHub (suggested name: `lng-carrier-tracker`)
- [ ] Clone it locally: `git clone https://github.com/<user>/lng-carrier-tracker.git`
- [ ] Unzip the scaffold and copy its contents into the repo root

## What was migrated (record of where everything landed)

The `scripts/` directory contains **pre-edited versions** of all your scripts, `docs/sops/` + `docs/pointers.md` contain the **pre-edited SOPs**, and `refdata/` contains the three reference files. Every file from the claude.ai Project has been migrated and path-edited. The scaffold is complete and migration-ready as-is.

For reference, here's where everything landed:

| From project knowledge | To repo | Status |
|---|---|---|
| `SKILL.md` | _replaced by `CLAUDE.md`_ — don't copy | new |
| `lng_carrier_backend_ref_fill_sop.md` | `docs/sops/ref_fill.md` | done — pre-edited (now rev 16) |
| `lng_carrier_discovery_sop.md` | `docs/sops/discovery.md` | done — pre-edited (now rev 6) |
| `lng_carrier_sfoc_reconciliation_sop.md` | `docs/sops/sfoc_reconciliation.md` | done — pre-edited (now rev 4) |
| `sop_pointers.md` | `docs/pointers.md` | done — pre-edited |
| `csb_yard_urls.md` | `refdata/csb_yard_urls.md` | done — clean, no edits needed |
| `owner_charterer_map.md` | `refdata/owner_charterer_map.md` | done — clean, no edits needed |
| `source_roster.md` | `refdata/source_roster.md` | done — clean, no edits needed |
| `pull_backend.py` | `scripts/pull_backend.py` | done — pre-edited |
| `normalize.py` | `scripts/normalize.py` | done (no path changes needed) |
| `dedup_index.py` | `scripts/dedup_index.py` | done — pre-edited |
| `csb_fetch.py` | `scripts/csb_fetch.py` | done — pre-edited |
| `url_verifier.py` | `scripts/url_verifier.py` | done — pre-edited |
| `imo_tracker.py` | `scripts/imo_tracker.py` | done — pre-edited |
| `build_workbook.py` | `scripts/build_workbook.py` | done — pre-edited (--out semantics changed; see below) |
| `recalc.py` | `scripts/recalc.py` | done — pre-edited |

A new `scripts/paths.py` was added — it resolves the work directory and the backend CSV location consistently across the other scripts.

The SOPs each gained a migration changelog entry (RF rev 16, DC rev 6, SR rev 4) documenting exactly what paths changed and confirming no research rules were altered.

## Path edits applied to scripts

For reference, here's what was changed (in case you want to audit or roll back):

- All `/home/claude/...` scratch paths → resolved via `paths.work_dir()` (defaults to `<repo_root>/work/`, override with `$LNGCT_WORK_DIR`)
- `/tmp/verify_page.html` and `/tmp/imo_tracker.html` → per-process scratch files under `tempfile.gettempdir()` (avoids collisions if you run multiple verifier instances in parallel)
- `build_workbook.py`'s `--out` semantics changed: it's now a directory (the canonical xlsx filename is appended by mode), or an explicit `.xlsx` path for backward compatibility. Passing nothing falls back to `batches/_latest/` with a warning. The canonical pattern is `--out batches/<date>_<mode>_<scope>/`.
- All docstring examples updated to reference repo-relative paths.
- `recalc.py` had a stray `present_files` reference in its docstring — replaced with "committing the batch".

## Path edits — what's already done vs. what to check

The SOPs (`docs/sops/*.md`) and `docs/pointers.md` are **already edited** — output paths point to `batches/`, scratch paths reference the `work/` directory, and `present_files` mentions are gone. Each SOP's changelog documents exactly what changed. You don't need to touch them.

When you copy the three `refdata/` files in, give them a quick check (they likely need no edits):

- `refdata/csb_yard_urls.md` — mentions `scripts/csb_fetch.py` (already correct path, no change expected).
- `refdata/source_roster.md` — mentions `scripts/imo_tracker.py` (already correct).
- `refdata/owner_charterer_map.md` — mentions `scripts/normalize.py` (already correct).

If any of them happen to reference `/mnt/project/`, `/home/claude/`, or `/mnt/user-data/outputs/`, swap to `refdata/`, `work/`, and `batches/<batch-dir>/` respectively.

## First-time setup

- [ ] `pip install -e .` to install the project's runtime dependencies (openpyxl, requests, beautifulsoup4, lxml)
- [ ] Optional: `pip install -e ".[dev]"` if you want `pytest` and `ruff` available locally
- [ ] `mkdir -p work batches` (work/ is gitignored; batches/ exists already)
- [ ] Smoke test: `cd scripts && python pull_backend.py` should fetch the live backend CSV and print the column map
- [ ] The `.claude/settings.json` permission config ships with the repo — Claude Code picks it up automatically. See `.claude/README.md` for what it allows/asks/denies. No setup needed; adjust later via `/permissions` if a prompt annoys you twice.

## Verify the workflow works end-to-end

- [ ] Open Claude Code in the repo root
- [ ] Confirm Claude Code picks up `CLAUDE.md` automatically at session start (it should reference the SOPs and the workflow)
- [ ] Ask for a small [ref]-fill batch (e.g. 5 rows) and confirm:
  - Fresh backend CSV is pulled to `work/backend.csv`
  - Scripts run without the "materialize to disk" dance
  - Output lands in `batches/<date>_ref_fill_rows_X-Y/`
  - `notes.md` is populated
- [ ] Upload the xlsx to your Drive folder, paste the Sheets link into `batches/README.md` and the per-batch `notes.md`

## Initial commit

- [ ] `git add -A`
- [ ] `git commit -m "Initial scaffold for LNG Carrier Tracker"`
- [ ] `git push origin main`

## Decisions still pending

- [ ] **Repo name** — `lng-carrier-tracker` is the obvious default; change `pyproject.toml` if you pick something else.
- [ ] **Authors** in `pyproject.toml` — fill in your name + contact.
- [ ] **License for the data/SOPs** — code is MIT (already set). For the SOPs and any data files committed, CC-BY-4.0 is the typical open-data choice. Add a `docs/LICENSE-CC-BY-4.0.md` if you want to differentiate.
- [ ] **Drive folder for batch xlsx files** — pick one folder, share-permission "Anyone with the link, viewer," and use that consistently. The link goes in `batches/README.md`.
- [ ] **GEM/SFOC sourcing note in README** — the README says GEM and SFOC aren't citation sources, "documented in the SOPs." This is confirmed: `docs/sops/ref_fill.md` §4.1 (never cite SFOC as a `[ref]`) and §4.2 (never cite GEM). No action needed unless you want to link those sections directly from the README.

## Once everything is verified

- [ ] Delete this `MIGRATION.md` file
- [ ] Delete the claude.ai Project (or archive it — you may want it as a reference for a while)
