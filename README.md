# LNG Carrier Tracker

A public, quarterly-updated dataset of conventional LNG carriers and FSRUs in global LNG trade. Built on top of the International Gas Union (IGU) World LNG Report and extended with industry news and public contract data.

This repository contains the **research scaffolding** for the tracker: the standard operating procedures, Python tooling, and per-batch outputs. The tracker dataset itself lives in a public Google Sheet (linked below).

First release: December 2025.

## What's in scope

The tracker covers conventional LNG carriers — vessels specifically involved in transporting or regasifying LNG, including Floating Storage and Regasification Units (FSRUs).

It **does not** include:

- Floating Storage Units (FSUs) — LNG carriers converted to permanent floating storage at terminals
- Small-scale and mid-scale LNG carriers (short-haul delivery)
- LNG bunkering vessels
- Domestic-only ships
- Vessels cancelled or decommissioned before December 2025

See [docs/inclusion_criteria.md](docs/inclusion_criteria.md) for the full criteria.

## Status categories

- **Proposed** — announced by a shipping company or charterer with public sources, but no binding shipyard contract signed. Included in the IGU orderbook; we research whether a contract exists.
- **On order** — binding shipbuilding contract signed between a ship owner and a shipyard. Typically has a delivery year and a hull number.
- **Active** — built, delivered, and operable. Includes idle and under-repair vessels; we don't distinguish among these substatuses.

## Repository layout

```
docs/sops/        Research SOPs (the rules)
docs/             Inclusion criteria, pointer index
refdata/          Reference markdown (yard URLs, owner names, source roster)
scripts/          Python tooling
tests/            Regression tests with cached fixtures
batches/          Per-batch outputs (xlsx + notes + Drive links)
CLAUDE.md         Workflow router for Claude Code
```

## How a batch works

Every batch is either a **[ref]-fill** (filling missing URL citations on existing backend rows) or a **discovery** run (finding LNG carriers not yet in the backend).

The full procedure lives in [docs/sops/ref_fill.md](docs/sops/ref_fill.md) and [docs/sops/discovery.md](docs/sops/discovery.md). The short version:

```bash
# [ref]-fill batch on rows 1148-1167
cd scripts/
python pull_backend.py                              # fresh backend CSV
python csb_fetch.py <yard>                          # for each yard in the cluster
python url_verifier.py <url> <expected-terms>...    # for each candidate URL
python build_workbook.py --mode ref_fill --rows 1148-1167 \
  --citations citations.json \
  --out ../batches/2026-05-27_rows_1148-1167/
python recalc.py ../batches/2026-05-27_rows_1148-1167/lng_carrier_backend_ref_fill.xlsx
```

Outputs land in `batches/<date>_rows_<range>/` and get committed alongside a `notes.md` recording any conflicts flagged, defects corrected, or escalations. See [batches/README.md](batches/README.md) for the per-batch directory layout and Drive link convention.

## Data sources

The tracker relies entirely on publicly-accessible sources:

- **Foundation:** [IGU World LNG Report](https://www.igu.org/) (annual)
- **Yard orderbooks:** [ChinaShipBuild](http://www.chinashipbuild.com/)
- **Regulatory filings:** DART (Korea), KIND (KRX English), Bursa Malaysia, HKEX, class societies (DNV, LR, ABS, KR, NK)
- **Trade press:** LNG Prime, Splash247, Riviera Maritime Media, Seatrade Maritime, TradeWinds, others — see [refdata/source_roster.md](refdata/source_roster.md) for the full tier list

GEM (Global Energy Monitor) and SFOC are **not** used as citation sources, though they contribute supplementary data to the tracker itself. The reasons are documented in the SOPs.

## Contributing

This is an open-data project. If you spot an error in the tracker:

1. Open an issue with the row(s), the proposed correction, and a public URL supporting it
2. Or, if you have a batch's worth of corrections, open a PR against `batches/` with the xlsx and notes

The [SOPs](docs/sops/) describe the rules a citation has to meet (confidence labels, cluster coherence, URL verification). Submissions that follow the SOPs are easier to merge.

## License

TBD — recommendation pending. Code is likely MIT; data + SOPs likely CC-BY-4.0.
