# LNG carriers researcher

Operational repository for an LLM research assistant that helps maintain the
**LNG Carrier Tracker** — a public, quarterly-updated dataset of conventional
LNG carriers and FSRUs in global LNG trade. The tracker dataset itself lives in
a Google Sheet (the "backend"); this repo is the research scaffolding behind it.

This repo is designed to be used with [Claude Code](https://docs.claude.com/en/docs/claude-code).
The assistant produces staged xlsx files for human review; it never edits the
live tracker directly. What lives here is the *how* — the standard operating
procedures, the Python tooling, the reference data, and the per-batch outputs —
not the dataset.

## Setup

Requirements: **Python ≥ 3.11** and the **`curl` binary** on PATH. All network
fetching shells out to system curl (a deliberate anti-bot choice — pip can't
declare it; macOS ships it, on Linux `apt install curl`). Bot-walled hosts
(the vessel trackers behind Cloudflare, seatrium behind AWS WAF): `curl_cffi`
(pip, declared) passes TLS-fingerprint firewalls, and **Google Chrome**
(installed separately) is driven once per host by `scripts/cf_clearance.py` to
clear JS challenges — the cookies it earns are kept in `work/cf_clearance.json`
and replayed through curl (about a year for Cloudflare, days for AWS WAF).

```bash
git clone <this repo> && cd lng-carriers-researcher
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # openpyxl + pytest/ruff
pytest                           # smoke check — should be all green
python scripts/pull_backend.py   # fetch the backend CSV -> work/
```

- Scratch artifacts live in `work/` (gitignored). Override its location with the
  `LNGCT_WORK_DIR` env var.
- The **FSRU reconciliation** workflow additionally expects the sibling repo
  `../lng-terminals-researcher` checked out next to this one (its
  `scripts/giignl_fsru_fleet.py` parses the GIIGNL PDF fleet table — reused, not
  duplicated).
- The **IGU reconciliation** workflow reads the IGU World LNG Report PDF from the same
  sibling repo (`../lng-terminals-researcher/data/IGU-World-LNG-Report-<year>.pdf`) and
  needs `pdfplumber`; the previous edition's PDF is passed by path.
- Most sources are public and need no credentials, with three exceptions:
  `pull_backend.py` reads the backend through the authenticated `gws` CLI
  (read-only `gws-gem` profile, config at `~/.config/gws-gem`); `wayback_save.py`
  needs an archive.org S3 key (`$IA_S3_AUTH` or the keychain item
  `archive-org-s3`); and `ais_static.py` needs an aisstream.io key
  (`$AISSTREAM_API_KEY` or the keychain item `aisstream-api-key`). (The
  Cloudflare clearance cookie in `work/` is IP-bound and gitignored — treat it
  like a token, never commit it.)

### The backend

The tracker lives in a Google Sheet, read via the authenticated `gws` CLI
(read-only work profile) — anonymous CSV export URLs (gviz, `/export`, `/pub`,
`/htmlview`) were deliberately disabled org-wide 2026-07-29 and now 401, so
there is no public export URL to point at. `pull_backend.py` resolves the tab
title from its gid via the Sheets API, pulls the tab's values, and writes
`work/backend.csv` (padded to a uniform grid) plus `work/backend.colmap.json`
(the column-index map, re-derived from the header row on every pull because
the schema drifts). The spreadsheet ID and tab gid default to this project's
sheet (`DEFAULT_SPREADSHEET_ID` / `DEFAULT_GID` in `pull_backend.py`) and can
be overridden with `--spreadsheet-id` / `--gid` or the
`LNGCT_BACKEND_SHEET_ID` / `LNGCT_BACKEND_GID` env vars.

### Script CLI conventions

Every script: status/progress/warnings go to **stderr**; machine-readable payload
(tables, CSV, JSON) goes to **stdout**. Exit codes: `0` ok, `1` findings under
`--strict` or a hard failure, `2` usage error. Nearly every script takes
`--help`. Exceptions: `merge_fills.py` has no CLI at all — it takes its input
from `work/` and starts the live research-merge pipeline the moment it's run,
`--help` included, so only invoke it when you mean to run the full pass.
`backend_io.py`, `confidence.py`, `igu_refs.py`, `lookups.py`, `normalize.py`,
and `paths.py` are shared library modules, not standalone CLI entry points.

## Running the assistant

Open the repo in [Claude Code](https://docs.claude.com/en/docs/claude-code)
(`claude .`) and give it a trigger phrase, e.g. "fill refs for rows 1148–1167"
or "discovery run for the Q2 2026 gap". Claude reads `CLAUDE.md` automatically
and routes from there.

## Workflows

Nine workflows. Most map to one SOP each in `docs/sops/`; Review and Apply &
verify both live in `apply.md`. `CLAUDE.md` is the router.

| Workflow | When to use | Output |
|---|---|---|
| **[ref]-fill** (`ref_fill.md`) | Backfill missing URL citations on existing backend rows | xlsx with verified `[ref]` citations |
| **Discovery** (`discovery.md`) | Find LNG carriers not yet in the backend | xlsx with new vessel candidates |
| **Data-fill** (`data_fill.md`) | Research blank (or `unknown`) data cells and propose a value + corroborating `[ref]` | xlsx with candidate value/`[ref]` pairs |
| **SFOC reconciliation** (`sfoc_reconciliation.md`) | Reconcile the backend against an updated SFOC dataset | xlsx with staged reconciliations |
| **FSRU reconciliation** (`fsru_reconciliation.md`) | Compare backend FSRUs against the GIIGNL Annual Report fleet table (name-keyed; GIIGNL is not citable) | 10-sheet comparison workbook |
| **IGU reconciliation** (`igu_reconciliation.md`) | Intercompare the whole backend against the IGU World LNG Report fleet + orderbook tables (IMO-keyed, edition-to-edition) | 11-sheet comparison workbook + decisions list |
| **Pre-release QC** (`qc_release.md`) | Whole-backend consistency/corruption sweep before a data release | QC report + `fix`-mode correction batch |
| **Review a batch's decisions** (`apply.md` step 2 / §3 / §2b) | Decide a batch's holds in the review app before applying | `decisions.csv` + `review_log.jsonl`; "push changes" is the app's one path to writing the backend, confirmed by the user in the browser |
| **Apply & verify** (`apply.md`) | Get a reviewed batch's accepted proposals into the backend, offset-proof | decisions.csv + apply artifacts + verify report |

A **corroborate** batch mode once appended ≥2 independent corroborators to
cells whose only `[ref]` was the IGU World LNG Report
(`scripts/derive_corroborate.py`, reusing the data-fill pipeline unchanged).
It is superseded by the 2026-09-21 ruling that the IGU report PDF is a
sufficient sole source on its own — the script still exists but this mode is
no longer run.

Every research batch follows the same shape: pull a fresh backend CSV, re-derive
the column map, gather and verify sources, build a workbook, recalc it to confirm
zero formula errors, and commit the batch directory with a `notes.md`.

Once a candidate workbook has been reviewed, the **apply & verify** round-trip
(`docs/sops/apply.md`) gets the accepted proposals back into the backend
offset-proof — triage (`batch_digest.py`) → decisions + apply artifacts
(`apply_batch.py`) → paste or by-name apply → re-pull and confirm
(`verify_apply.py`, which also runs the QC and dedupe sweeps). It exists because
a manual column-misaligned paste once corrupted two rows; this loop makes that
class of bug impossible.

## Repository layout

```
CLAUDE.md                  Entry point for Claude Code — workflow router + hard rules
README.md                  This file
pyproject.toml             Python deps and tooling config (ruff, pytest)

docs/
  sops/                    The eight workflow procedures (authoritative)
    ref_fill.md            [ref]-fill rules A–F, confidence labels, §3.8 verification gate
    discovery.md           Discovery workflow, four-ring source model, candidate workbook
    data_fill.md           Data-fill workflow, blank-vs-`unknown` preserve-ref contract, derivable autofill
    sfoc_reconciliation.md SFOC reconciliation workflow
    fsru_reconciliation.md FSRU reconciliation vs the GIIGNL fleet table (name-keyed join)
    igu_reconciliation.md  IGU World LNG Report intercomparison (IMO-keyed, edition-to-edition)
    qc_release.md          Pre-release QC sweep + fix-mode correction batches
    apply.md               Apply & verify round-trip — offset-proof batch incorporation + dedupe sweep
  inclusion_criteria.md    What's in scope vs out, status categories
  pointers.md              "Which SOP section governs X" cross-reference index
  scripts.md               Per-script reference — what each script does and when to read its source
  plans/                   Dated plans and state files for multi-batch passes (e.g. the sep-17-pass
                           summary + worklist) — working notes, not authoritative rules

data/                      Reference data (committed)
  csb_yard_urls.md         Stable ChinaShipBuild yard URLs + slugs
  owner_charterer_map.md   Canonical owner names, variants, and owner→country map
  source_roster.md         Source tier list for picking corroboration URLs
  controlled_vocab.md      Exact value sets for the type columns (cargo / vessel / propulsion)
  shipbuilder_facts.csv    Curated yard-location facts (seeded by seed_lookups.py)
  shipowner_facts.csv      Curated owner-country facts (seeded by seed_lookups.py)
  qc_allowlist.csv         Known-legit oddities silenced in qc_backend.py
  gem_export_*.csv         Snapshot of GEM's LNG-terminals export (FSRU-reconciliation
                           comparison input — internal only, never a citation source)
  living_workbook.json     review_app living-workbook state (AP §2c) — Drive doc id + the
                           per-line `processed` map; written by review_app/living.py
  GIIGNL Annual Report PDFs (7 files, 2020–2026, ~48 MB, filenames vary by edition) — committed
                           so a clone is self-contained; the FSRU workflow parses the fleet
                           table from these; see data/README.md for the per-edition manifest

scripts/                   Python tools called by the workflows
  paths.py                 Shared path helpers (work/ location, LNGCT_WORK_DIR)
  fetch.py                 Shared curl layer — fetch_page() + the bot-wall ladder (curl → curl_cffi → Chrome clearance cookie)
  cf_clearance.py          Earns / stores bot-wall cookies by driving real Chrome (work/cf_clearance.json)
  sweep.py                 Polite bulk fetch — per-host pacing + circuit breaker; the only way to sweep one host
  backend_io.py            Shared backend loading — CSV + colmap + date parsing + sheet-row map
  pull_backend.py          Fetch backend CSV via the gws CLI, derive the column-index map
                           (--spreadsheet-id / --gid, or LNGCT_BACKEND_SHEET_ID / LNGCT_BACKEND_GID)
  qc_backend.py            Backend QC sanity check — column-offset / misplaced-value / Name checks
  normalize.py             Canonical builder/owner names + owner→country (imported by others)
  lookups.py               Data loaders — controlled vocab + builder/owner facts tables
  seed_lookups.py          Seed/refresh the builder/owner facts CSVs from the live backend
  dedup_index.py           Build the matching indexes for candidate dedup
  csb_fetch.py             Fetch + parse ChinaShipBuild orderbook tables
  orderbook_reconcile.py   Whole-orderbook completeness reconciliation — CSB || backend || IGU
                           Appendix 4 || shipvault, not date-bounded (unlike a gap-window discovery run)
  url_verifier.py          The §3.8 gate — graded verdicts (ok / banned / dead / blocked / uncorroborated), value↔ref corroboration
  confidence.py            The §5 confidence grade (RF rev 28) — turns the gate's own verdicts
                           into G/Y/R + why; a researcher's label can only argue a line down
  igu_refs.py              IMO-keyed check of what an IGU report PDF actually prints for one
                           vessel — the gate behind every IGU report-PDF ref (IG §1)
  citation_qc.py           §3.8a rot sweep — grades every existing backend [ref] URL (work/citation_qc.csv)
  wayback_save.py          Archive [ref] URLs to the Wayback Machine (authenticated Save Page Now; resumable)
  imo_tracker.py           §6a.8 IMO → vessel-tracker fallback (shipvault API first, marinetraffic.org second)
  shipvault_api_refs.py    Adds the shipvault unit-record URL as a companion ref where the page renders blank
  other_names.py           Former Names → `Other names` companion cells (RF §4.16)
  delivery_history.py      A later Delivery year → `Previous delivery year(s)` + `Delivery
                           delayed` companion cells (RF §4.19)
  igu_hulls.py             IGU `Name (hull)` entries → backend: fill/restyle Hull number cells,
                           name hull-placeholder rows (RF §4.17)
  ais_static.py            aisstream static-data cross-check for on-order IMOs — a lead, never a [ref]
  derive_fills.py          Data-fill: scope rows, compute derivable autofills, list research targets
  derive_corroborate.py    Corroborate batches (superseded — see Workflows above): find IGU-only
                           refs, queue independent corroboration
  merge_fills.py           Data-fill: merge per-cluster research + run the central §3.8 gate
                           (no CLI — running it starts the live pipeline immediately, --help included)
  fsru_reconcile.py        FSRU reconciliation: GIIGNL fleet JSON ↔ backend, five buckets
  igu_fleet.py             IGU World LNG Report extractor — fleet + orderbook tables from word coordinates
  igu_reconcile.py         IGU reconciliation: IGU fleet/orderbook JSON ↔ whole backend, edition diff, shipvault leads
  build_workbook.py        xlsx scaffolding — sheets, color fills, frozen panes (6 modes)
  recalc.py                Force recalc, return any formula errors (run before committing)
  batch_digest.py          Apply: triage a batch into auto-safe vs needs-a-decision
  apply_batch.py           Apply: reviewed batch → decisions.csv + offset-proof apply artifacts
  regrade_confidence.py    Retroactive §5 re-grade of a batch's held lines (RF rev 28);
                           promote-only, hold → accept on a Green, never demotes
  verify_apply.py          Apply: re-pull + diff backend vs apply.json, qc + dedupe the touched rows
  dedupe_check.py          Internal duplicate scan (tiered HIGH/MED/LOW; advisory)

tools/
  apply_patch.gs           Apps Script by-name applier (writes each cell by row_id + header)

review_app/                Local, loopback-only app for deciding a batch's holds (replaces the
                           combined xlsx); entry points documented in review_app/README.md,
                           not this table — imports from scripts/, never the reverse

tests/                     pytest suite — see tests/README.md
batches/                   Per-batch outputs (input JSON + xlsx + notes.md) — see batches/README.md

work/                      (gitignored scratch — not in the repo)
  backend.csv + backend.colmap.json   The live pull — inputs to everything else
  csb/<yard>.json                     Cached ChinaShipBuild pages
  data_fill.json / research_*.json    Data-fill pipeline state (clear research_*.json between batches)
  qc_report.csv / dedupe_report.csv   Sweep outputs
  citation_qc.csv / wayback_save.jsonl  Rot-sweep grades and Wayback archive log (both resumable)
  cf_clearance.json                   Bot-wall cookies (IP-bound)
```

## Hard rules

A non-exhaustive list of things the assistant should never do (full list and
section references in `CLAUDE.md`):

- **Never edit the backend directly.** All outputs are staged candidate xlsx for human review. The backend lives in Google Sheets and is human-edited.
- **Pull a fresh backend CSV at the start of every batch** and re-derive the column-index map — schema and data drift between batches.
- **Verify every URL before staging it.** HTTP 200 alone isn't enough; check for soft-error pages and content references. URLs that worked in prior batches are re-verified — URLs decay.
- **Rule F always applies** — no orphan `[ref]` cells without a paired data value, and vice versa.
- **Never `git push` without explicit user approval.** Local commits are fine; pushing to a public repo is irreversible.
- **Never commit** credentials, API keys, or anything in `work/` (gitignored scratch).

## Batches

Each batch produces a directory under `batches/<YYYY-MM-DD>_<HHMMET>_<mode>_<scope>/`
containing the JSON input that drove it, the output workbook, and a `notes.md`
following `batches/_template_notes.md`. The committed xlsx is the artifact of
record. See [batches/README.md](batches/README.md) for the naming convention,
the contents contract, and the batch index.

## Glossary

- **backend** — the live tracker Google Sheet. Pulled as CSV, never edited by tooling.
- **`[ref]` cell** — a citation column paired with a data column (e.g. `Capacity [ref]`
  holds the URL(s) backing `Capacity`). Multiple URLs join with `", "`.
- **row_id** — column A, "original order in sheet": a static stamp that drifts from the
  live row as rows are deleted. Humans are always given the **live sheet row**; scripts
  key on row_id.
- **§3.8 gate** — the URL verification gate (`url_verifier.py`): HTTP 200 + soft-error
  detection + the value↔ref corroboration check (a URL may only be cited on a cell whose
  value its page actually contains).
- **rings (A–D)** — the discovery source model: A = yard orderbooks (ChinaShipBuild),
  B = regulatory filings (DART/KIND/Bursa/HKEX), C = trade press, D = charterer programs.
- **buckets** — the reconciliation outcome classes (e.g. FSRU: matched / reclassify /
  manual pairing / candidates to add / backend only).
- **confidence colors** — computed from what the §3.8c gate actually did (RF rev 28), not
  declared by the researcher: green = a ref survived the gate on a **live** page that
  genuinely states the value for this vessel (one source is enough), yellow = only an
  archived snapshot carries the value, the value is too generic for a bare text match to
  mean anything alone, or a carve-out caps the cell, red = nothing survived the gate. A
  researcher may argue a line down with a `cap_reason`, never up. In workbooks
  additionally: **peach** = an existing backend `[ref]` preserved/overridden, **gray** =
  pre-existing backend value, untouched.
- **cluster** — rows grouped by (builder, owner, contract month); research and dedup
  operate per-cluster.
- **derivable fill** — a data-fill proposal computed from the backend itself (yard-location
  block, owner country from siblings, capacity units) rather than researched.

## Methodology

The tracker is built on the [IGU World LNG Report](https://www.igu.org/)
(annual) and extended with public contract data and trade-press reporting. The
IGU methodology is the foundation; the SOPs in this repo encode how the
assistant applies it operationally — confidence labels, cluster coherence, URL
verification, and conflict handling.

The assistant draws only on publicly-accessible sources: the IGU report, yard
orderbooks ([ChinaShipBuild](http://www.chinashipbuild.com/)), regulatory
filings (DART, KIND, Bursa Malaysia, HKEX, class societies), and trade press
(see [data/source_roster.md](data/source_roster.md) for the tier list).
GEM (Global Energy Monitor, including `gem.wiki`) and SFOC contribute
supplementary data to the tracker but are **never** used as citation or
corroboration sources — GEM is downstream of this tracker, so citing it would be
circular. GIIGNL is likewise a comparison artifact only, not citable. The
reasons are documented in the SOPs.

Scope (which vessels qualify, the proposed / on-order / active status
categories) is defined in [docs/inclusion_criteria.md](docs/inclusion_criteria.md).
