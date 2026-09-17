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
- No credentials are needed; every source is public. (The Cloudflare clearance cookie in `work/` is IP-bound and gitignored — treat it like a token, never commit it.)

### The backend

The tracker lives in a Google Sheet published as CSV. The default export URL is in
`scripts/pull_backend.py` (`DEFAULT_BACKEND_CSV_URL`) and can be overridden with
`--url` or the `LNGCT_BACKEND_URL` env var — that URL is the one thing you must
repoint to run this pipeline against a different sheet. `pull_backend.py` writes
`work/backend.csv` plus `work/backend.colmap.json` (the column-index map,
re-derived from the header row on every pull because the schema drifts).

### Script CLI conventions

Every script: status/progress/warnings go to **stderr**; machine-readable payload
(tables, CSV, JSON) goes to **stdout**. Exit codes: `0` ok, `1` findings under
`--strict` or a hard failure, `2` usage error. All scripts take `--help`.

## Running the assistant

Open the repo in [Claude Code](https://docs.claude.com/en/docs/claude-code)
(`claude .`) and give it a trigger phrase, e.g. "fill refs for rows 1148–1167"
or "discovery run for the Q2 2026 gap". Claude reads `CLAUDE.md` automatically
and routes from there.

## Workflows

Seven workflows, one SOP each. `CLAUDE.md` is the router; `docs/sops/` holds the
authoritative procedures.

| Workflow | When to use | Output |
|---|---|---|
| **[ref]-fill** (`ref_fill.md`) | Backfill missing URL citations on existing backend rows | xlsx with verified `[ref]` citations |
| **Discovery** (`discovery.md`) | Find LNG carriers not yet in the backend | xlsx with new vessel candidates |
| **Data-fill** (`data_fill.md`) | Research blank (or `unknown`) data cells and propose a value + corroborating `[ref]` | xlsx with candidate value/`[ref]` pairs |
| **SFOC reconciliation** (`sfoc_reconciliation.md`) | Reconcile the backend against an updated SFOC dataset | xlsx with staged reconciliations |
| **FSRU reconciliation** (`fsru_reconciliation.md`) | Compare backend FSRUs against the GIIGNL Annual Report fleet table (name-keyed; GIIGNL is not citable) | 10-sheet comparison workbook |
| **Pre-release QC** (`qc_release.md`) | Whole-backend consistency/corruption sweep before a data release | QC report + `fix`-mode correction batch |
| **Apply & verify** (`apply.md`) | Get a reviewed batch's accepted proposals into the backend, offset-proof | decisions.csv + apply artifacts + verify report |

There is also a **corroborate** batch variant of data-fill
(`scripts/derive_corroborate.py`): it finds cells whose only `[ref]` is the IGU
World LNG Report and appends ≥2 independent corroborators per cell, reusing the
data-fill pipeline unchanged.

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
  sops/                    The seven workflow procedures (authoritative)
    ref_fill.md            [ref]-fill rules A–F, confidence labels, §3.8 verification gate
    discovery.md           Discovery workflow, four-ring source model, candidate workbook
    data_fill.md           Data-fill workflow, blank-vs-`unknown` preserve-ref contract, derivable autofill
    sfoc_reconciliation.md SFOC reconciliation workflow
    fsru_reconciliation.md FSRU reconciliation vs the GIIGNL fleet table (name-keyed join)
    qc_release.md          Pre-release QC sweep + fix-mode correction batches
    apply.md               Apply & verify round-trip — offset-proof batch incorporation + dedupe sweep
  inclusion_criteria.md    What's in scope vs out, status categories
  pointers.md              "Which SOP section governs X" cross-reference index

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
  GIIGNL-*.pdf             GIIGNL Annual Report archive — committed (~48 MB) so a clone is
                           self-contained; the FSRU workflow parses the fleet table from these

scripts/                   Python tools called by the workflows
  paths.py                 Shared path helpers (work/ location, LNGCT_WORK_DIR)
  fetch.py                 Shared curl wrapper — one UA, timeouts, friendly missing-curl error
  backend_io.py            Shared backend loading — CSV + colmap + date parsing + sheet-row map
  pull_backend.py          Fetch backend CSV, derive the column-index map (--url / LNGCT_BACKEND_URL)
  qc_backend.py            Backend QC sanity check — column-offset / misplaced-value / Name checks
  normalize.py             Canonical builder/owner names + owner→country (imported by others)
  lookups.py               Data loaders — controlled vocab + builder/owner facts tables
  seed_lookups.py          Seed/refresh the builder/owner facts CSVs from the live backend
  dedup_index.py           Build the matching indexes for candidate dedup
  csb_fetch.py             Fetch + parse ChinaShipBuild orderbook tables
  url_verifier.py          The §3.8 gate — HTTP 200 + content check + soft-error detection
  imo_tracker.py           §6a.8 IMO → marine-vessel-tracker fallback
  derive_fills.py          Data-fill: scope rows, compute derivable autofills, list research targets
  derive_corroborate.py    Corroborate batches: find IGU-only refs, queue independent corroboration
  merge_fills.py           Data-fill: merge per-cluster research + run the central §3.8 gate
  fsru_reconcile.py        FSRU reconciliation: GIIGNL fleet JSON ↔ backend, five buckets
  build_workbook.py        xlsx scaffolding — sheets, color fills, frozen panes (5 modes)
  recalc.py                Force recalc, return any formula errors (run before committing)
  batch_digest.py          Apply: triage a batch into auto-safe vs needs-a-decision
  apply_batch.py           Apply: reviewed batch → decisions.csv + offset-proof apply artifacts
  verify_apply.py          Apply: re-pull + diff backend vs apply.json, qc + dedupe the touched rows
  dedupe_check.py          Internal duplicate scan (tiered HIGH/MED/LOW; advisory)
  check_docs.py            Doc-drift checker — SOP revs vs pointers/CLAUDE.md, script inventory parity

tools/
  apply_patch.gs           Apps Script by-name applier (writes each cell by row_id + header)

tests/                     pytest suite — see tests/README.md
batches/                   Per-batch outputs (input JSON + xlsx + notes.md) — see batches/README.md

work/                      (gitignored scratch — not in the repo)
  backend.csv + backend.colmap.json   The live pull — inputs to everything else
  csb/<yard>.json                     Cached ChinaShipBuild pages
  data_fill.json / research_*.json    Data-fill pipeline state (clear research_*.json between batches)
  qc_report.csv / dedupe_report.csv   Sweep outputs
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
- **confidence colors** — green = high (2+ independent sources, or primary source with
  the value verbatim), yellow = medium (entity-level, or a detail contested), red = low.
  In workbooks additionally: **peach** = an existing backend `[ref]` preserved/overridden,
  **gray** = pre-existing backend value, untouched.
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
