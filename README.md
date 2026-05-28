# LNG carriers researcher

Operational repository for an LLM research assistant that helps maintain the
**LNG Carrier Tracker** — a public, quarterly-updated dataset of conventional
LNG carriers and FSRUs in global LNG trade. The tracker dataset itself lives in
a public Google Sheet; this repo is the research scaffolding behind it.

This repo is designed to be used with [Claude Code](https://docs.claude.com/en/docs/claude-code).
The assistant produces staged xlsx files for human review; it never edits the
live tracker directly. What lives here is the *how* — the standard operating
procedures, the Python tooling, the reference data, and the per-batch outputs —
not the dataset.

## Quick start

1. Install dependencies: `pip install -e .` (or `pip install -e ".[dev]"` for the test/lint extras)
2. Open the repo in Claude Code: `claude .`
3. Claude reads `CLAUDE.md` automatically and routes from there
4. Give it a trigger phrase, e.g. "fill refs for rows 1148–1167" or "discovery run for the Q2 2026 gap"

No credentials or `.env` are required — every source the assistant uses is
publicly accessible.

## Workflows

The assistant runs one of three workflows per batch. `CLAUDE.md` is the router;
`docs/sops/` holds the authoritative procedures.

| Workflow | When to use | Output |
|---|---|---|
| **[ref]-fill** | Backfill missing URL citations on existing backend rows | xlsx with verified `[ref]` citations |
| **Discovery** | Find LNG carriers not yet in the backend | xlsx with new vessel candidates |
| **SFOC reconciliation** | Reconcile the backend against an updated SFOC dataset | xlsx with staged reconciliations |

Every batch follows the same shape: pull a fresh backend CSV, re-derive the
column map, gather and verify sources, build a workbook, recalc it to confirm
zero formula errors, and commit the batch directory with a `notes.md`.

## Repository layout

```
CLAUDE.md                  Entry point for Claude Code — workflow router + hard rules
README.md                  This file
MIGRATION.md               Notes on repo restructuring / migration history
LICENSE                    MIT
pyproject.toml             Python deps and tooling config (ruff, pytest)

docs/
  sops/                    The three workflow procedures (authoritative)
    ref_fill.md            [ref]-fill rules A–F, confidence labels, §3.8 verification gate
    discovery.md           Discovery workflow, four-ring source model, candidate workbook
    sfoc_reconciliation.md SFOC reconciliation workflow
  inclusion_criteria.md    What's in scope vs out, status categories
  pointers.md              "Which SOP section governs X" cross-reference index

refdata/                   Reference markdown (read on demand)
  csb_yard_urls.md         Stable ChinaShipBuild yard URLs + slugs
  owner_charterer_map.md   Canonical owner names and variants
  source_roster.md         Source tier list for picking corroboration URLs

scripts/                   Python tools called by the workflows
  pull_backend.py          curl + parse backend CSV, derive the column-index map
  normalize.py             Canonical builder/owner names (imported by others)
  dedup_index.py           Build the matching indexes for candidate dedup
  csb_fetch.py             Fetch + parse ChinaShipBuild orderbook tables
  url_verifier.py          The §3.8 gate — HTTP 200 + content check + soft-error detection
  imo_tracker.py           §6a.8 IMO → marine-vessel-tracker fallback
  build_workbook.py        xlsx scaffolding — sheets, color fills, frozen panes, headers
  recalc.py                Force recalc, return any formula errors (run before committing)
  paths.py                 Shared path helpers

tests/                     Regression tests with cached fixtures
batches/                   Per-batch outputs (xlsx + notes + Drive links)
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

Each batch produces a directory under `batches/<YYYY-MM-DD>_<mode>_<scope>/`
containing the citation/candidate JSON input, the output workbook, and a
`notes.md` recording conflicts flagged, defects corrected, and escalations.
Published batches get a row in the batch index with a Google Drive share link.
See [batches/README.md](batches/README.md) for the directory layout and Drive
link convention.

## Methodology

The tracker is built on the [IGU World LNG Report](https://www.igu.org/)
(annual) and extended with public contract data and trade-press reporting. The
IGU methodology is the foundation; the SOPs in this repo encode how the
assistant applies it operationally — confidence labels, cluster coherence, URL
verification, and conflict handling.

The assistant draws only on publicly-accessible sources: the IGU report, yard
orderbooks ([ChinaShipBuild](http://www.chinashipbuild.com/)), regulatory
filings (DART, KIND, Bursa Malaysia, HKEX, class societies), and trade press
(see [refdata/source_roster.md](refdata/source_roster.md) for the tier list).
GEM and SFOC contribute supplementary data to the tracker but are **not** used
as citation sources; the reasons are documented in the SOPs.

Scope (which vessels qualify, the proposed / on-order / active status
categories) is defined in [docs/inclusion_criteria.md](docs/inclusion_criteria.md).

## Contributing

This is an open project. If you spot an error in the tracker:

1. Open an issue with the row(s), the proposed correction, and a public URL supporting it, or
2. If you have a batch's worth of corrections, open a PR against `batches/` with the xlsx and notes.

The [SOPs](docs/sops/) describe the rules a citation has to meet. Submissions
that follow the SOPs are easier to merge.

## License

Code is [MIT](LICENSE). Data and SOPs are intended for reuse under CC-BY-4.0
(formal data license pending).
