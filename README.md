# LNG carriers researcher

Operational repository for an LLM research assistant that helps maintain the
**LNG Carrier Tracker** — a public, quarterly-updated dataset of conventional
LNG carriers and FSRUs in global LNG trade. The tracker dataset itself lives in
a Google Sheet; this repo is the research scaffolding behind it.

This repo is designed to be used with [Claude Code](https://docs.claude.com/en/docs/claude-code).
The assistant produces staged xlsx files for human review; it never edits the
live tracker directly. What lives here is the *how* — the standard operating
procedures, the Python tooling, the reference data, and the per-batch outputs —
not the dataset.

## Running the assistant

There are two ways to drive the assistant, depending on whether you need the
full batch pipeline or just the research and reasoning.

### With Claude Code (full pipeline)

This is the intended path — it can run the Python tooling, pull the backend CSV,
build the xlsx, and commit a batch.

1. Open the repo in Claude Code: `claude .`
2. Claude reads `CLAUDE.md` automatically and routes from there
3. Give it a trigger phrase, e.g. "fill refs for rows 1148–1167" or "discovery run for the Q2 2026 gap"

Claude Code installs the Python dependencies the first time a script needs them,
so there's normally nothing to set up by hand. If you'd rather run a script
yourself (e.g. `python recalc.py …`), install them once with `pip install -e .`
(add `".[dev]"` for `pytest` / `ruff`). No credentials or `.env` are required —
every source the assistant uses is publicly accessible.

### With the Claude desktop app or claude.ai

You can also point a regular Claude chat at this repository, no local setup
required. This is good for the research-and-reasoning half of a batch and for
reviewing work against the SOPs.

1. **Give Claude the repo.** Either enable the GitHub connector and point the chat at this repository, or create a [Project](https://www.anthropic.com/news/projects) and add the repo (at minimum `CLAUDE.md`, `docs/sops/`, and `refdata/`) as project knowledge.
2. **Tell it to follow the procedures.** Ask Claude to read `CLAUDE.md` and the relevant SOP end-to-end before doing anything — `CLAUDE.md` is the router and `docs/sops/` holds the authoritative rules.
3. **Give it a research task.** Use the same trigger phrases ("fill refs for rows 1148–1167", "discovery run for the Q2 2026 gap"). With web search enabled, Claude can cluster the rows, search the public sources, apply the confidence labels, sanity-check URLs, and draft the citation or candidate set as JSON or a table.

**What's different from Claude Code:** the desktop app does the reasoning, not
the plumbing. It can't run the Python tooling, pull the backend CSV via
`pull_backend.py`, build the workbook with `build_workbook.py`, run the
`url_verifier.py` / `recalc.py` gates, or commit a batch directory — those need
a local checkout. So use it to (a) do the source research and hand you a draft
citation/candidate set you then feed into `build_workbook.py` in Claude Code, or
(b) review and QA an existing batch against the SOPs. Anything destined for the
tracker still has to clear the script-driven verification gates before it ships.

## Workflows

The assistant runs one of four workflows per batch. `CLAUDE.md` is the router;
`docs/sops/` holds the authoritative procedures.

| Workflow | When to use | Output |
|---|---|---|
| **[ref]-fill** | Backfill missing URL citations on existing backend rows | xlsx with verified `[ref]` citations |
| **Discovery** | Find LNG carriers not yet in the backend | xlsx with new vessel candidates |
| **Data-fill** | Research blank (or `unknown`) data cells and propose a value + corroborating `[ref]` | xlsx with candidate value/`[ref]` pairs |
| **SFOC reconciliation** | Reconcile the backend against an updated SFOC dataset | xlsx with staged reconciliations |

Every batch follows the same shape: pull a fresh backend CSV, re-derive the
column map, gather and verify sources, build a workbook, recalc it to confirm
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
LICENSE                    MIT
pyproject.toml             Python deps and tooling config (ruff, pytest)

docs/
  sops/                    The four workflow procedures (authoritative)
    ref_fill.md            [ref]-fill rules A–F, confidence labels, §3.8 verification gate
    discovery.md           Discovery workflow, four-ring source model, candidate workbook
    data_fill.md           Data-fill workflow, blank-vs-`unknown` preserve-ref contract, derivable autofill
    sfoc_reconciliation.md SFOC reconciliation workflow
    apply.md               Apply & verify round-trip — offset-proof batch incorporation + dedupe sweep
  inclusion_criteria.md    What's in scope vs out, status categories
  pointers.md              "Which SOP section governs X" cross-reference index

refdata/                   Reference markdown (read on demand)
  csb_yard_urls.md         Stable ChinaShipBuild yard URLs + slugs
  owner_charterer_map.md   Canonical owner names, variants, and owner→country map
  source_roster.md         Source tier list for picking corroboration URLs
  controlled_vocab.md      Exact value sets for the type columns (cargo / vessel / propulsion)

scripts/                   Python tools called by the workflows
  pull_backend.py          curl + parse backend CSV, derive the column-index map
  qc_backend.py            Backend QC sanity check — column-offset / misplaced-value detection
  normalize.py             Canonical builder/owner names + owner→country (imported by others)
  lookups.py               refdata loaders — controlled vocab + builder/owner facts tables
  seed_lookups.py          Seed/refresh the builder/owner facts CSVs from the live backend
  dedup_index.py           Build the matching indexes for candidate dedup
  csb_fetch.py             Fetch + parse ChinaShipBuild orderbook tables
  url_verifier.py          The §3.8 gate — HTTP 200 + content check + soft-error detection
  imo_tracker.py           §6a.8 IMO → marine-vessel-tracker fallback
  derive_fills.py          Data-fill: scope rows, compute derivable autofills, list research targets
  merge_fills.py           Data-fill: merge per-cluster research + run the central §3.8 gate
  build_workbook.py        xlsx scaffolding — sheets, color fills, frozen panes, headers (4 modes)
  recalc.py                Force recalc, return any formula errors (run before committing)
  batch_digest.py          Apply: triage a batch into auto-safe vs needs-a-decision
  apply_batch.py           Apply: reviewed batch → decisions.csv + offset-proof apply artifacts
  verify_apply.py          Apply: re-pull + diff backend vs apply.json, qc + dedupe the touched rows
  dedupe_check.py          Internal duplicate scan (tiered HIGH/MED/LOW; advisory)
  paths.py                 Shared path helpers

tools/
  apply_patch.gs           Apps Script by-name applier (writes each cell by row_id + header)

tests/                     pytest suite (normalize + url_verifier covered; fetcher fixtures planned)
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
