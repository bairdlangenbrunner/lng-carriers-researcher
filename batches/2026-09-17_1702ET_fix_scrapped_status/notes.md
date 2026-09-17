# Fix batch — Status `scrapped` for the 18 rows IGU 2026 dropped + Puteri Delima Satu → FSU (2026-09-17, sep-17-pass 9)

Follow-up to the IGU reconciliation (`2026-09-17_1458ET_igu_reconciliation_igu2026`, decisions 1
and 2). `fix` mode, QC §4 / Apply SOP. All row numbers are **live sheet rows** (fresh pull
2026-09-17, 1,220 rows); `fix.json` and `apply_patch.csv` key on the column-A `row_id`.

## The rule change (Baird, 2026-09-17)

- **`scrapped` is a new Status value** (`active` / `on order` / `proposed` / `scrapped`).
- **Rows are never deleted from the backend.** Every scrapped vessel moves to `scrapped`,
  whichever side of the December 2025 first release the scrapping falls. This replaces the IG
  rev 1 rule ("decommissioned before Dec 2025 → remove the row") under which 11 of these 18 rows
  would have left. The inclusion cut-off now only governs what is *added*.

## What is proposed — 19 cells, 19 rows, all `G`, all accept

| row | IMO | name | change | press refs | shipvault |
|---|---|---|---|---|---|
| 16 | 9038440 | Al Khaznah | Status → `scrapped` | splash247 (Adnoc pair sold for recycling) | yes |
| 23 | 9038452 | Ghasha | Status → `scrapped` | same splash247 piece | yes |
| 25 | 9030814 | Puteri Delima | Status → `scrapped` | TradeWinds (MISC 1995-built duo) | yes |
| 26 | 9030826 | Puteri Nilam | Status → `scrapped` | same TradeWinds piece | yes |
| 44 | 9155145 | Hyundai Technopia | Status → `scrapped` | lngprime + marineinsight | yes |
| 46 | 9176008 | HL Ras Laffan | Status → `scrapped` | gcaptain + hellenicshippingnews (as `Rasi`, at the Bangladesh yard) | yes |
| 47 | 9176010 | HL Sur | Status → `scrapped` | marineinsight + shipandbunker week 21 | yes |
| 48 | 9179581 | Hyundai Aquapia | Status → `scrapped` | marineinsight + shipandbunker week 21 | yes |
| 49 | 9155157 | Hyundai Cosmopia | Status → `scrapped` | Lloyd's List LL1154206 | yes |
| 54 | 9200316 | LNG Jamal | Status → `scrapped` | Lloyd's List LL1154822 | yes |
| 63 | 9238038 | Trader II | Status → `scrapped` | shippingherald + TradeWinds | yes |
| 64 | 9213416 | Trader III | Status → `scrapped` | TradeWinds + NGO Shipbreaking Platform | yes |
| 77 | 9236420 | Seapeak Catalunya | Status → `scrapped` | TradeWinds (sold as `Seapeak Asia`) | yes |
| 84 | 9265500 | Dukhan | Status → `scrapped` | Lloyd's List LL1153032 + splash247 | **no** (below) |
| 94 | 9248502 | Puteri Firus Satu | Status → `scrapped` | TradeWinds (MISC trio) | yes |
| 95 | 9245031 | Puteri Zamrud Satu | Status → `scrapped` | same TradeWinds piece | yes |
| 98 | 9259276 | Seapeak Madrid | Status → `scrapped` | TradeWinds + splash247 (sold as `Seapeak Mars`) | yes |
| 115 | 9261205 | Puteri Mutiara Satu | Status → `scrapped` | same MISC-trio TradeWinds piece | yes |
| 61 | 9211872 | Puteri Delima Satu | Vessel type `conventional` → `FSU` | MISC media release + MISC Annual Report 2025 | — |

Every ref passed the §3.8c gate at build time (0 dropped by the gate in the final build; zero
formula errors). The gated refs **replace** the paired `Status [ref]` — the IGU 2025 landing page
supported `active`, not `scrapped`. "shipvault = yes" means the `shipvault.com/ships/{id}` page
plus its unit-record companion (RF §6a.8 rev 21; `shipvault_api_refs.json`).

**Row 61 (FSU).** MISC's release: "conversion of MISC's LNG Carrier, Puteri Delima Satu, into an
FSU" for Pengerang LNG (Two); MISC Annual Report 2025 (Bursa filing 2026-04-14): "FSU Puteri
Delima Satu delivered to PETRONAS LNG Regasification Terminal Pengerang". Both are MISC primary
documents, re-verified by hand. FSUs are out of scope for *additions* (`docs/inclusion_criteria.md`),
but the row stays — rows are never deleted. Only Vessel type is proposed; Status stays `active`.
`../lng-carriers-map` `fleet.json` should be re-exported after this is applied.

## Things the reviewer should know

- **Dukhan (row 84) carries no shipvault ref.** Its record still says ACTIVE (owner "BREAKERS",
  name `UKHAN`) — shipvault lags. Two press refs carry it on their own.
- **Press dates lead shipvault fate dates** by weeks to months — press reports the demolition
  *sale*, shipvault's fate date is the beaching. Not a conflict. Puteri Mutiara Satu's record says
  scrapped with no fate date yet.
- **marineinsight misattributes the seller** of HL Sur / HL Ras Laffan to Hyundai LNG Shipping
  (they were H-Line's). The scrapping itself is stated correctly and corroborated by the second ref;
  no owner value is proposed from it.
- **Scrap-voyage renames are not proposed.** The ships were renamed for the last voyage (`Khaza`,
  `Shaan`, `Lima`, `Nila`, `Techno`, `Rasi`, `Apia`, `Cosmo`, `Rade`, `Seapeak Asia` / `K Asia`,
  `Ukhan`, `Zamrud`, `Seapeak Mars` / `Teak`). Name and Other names are left as they are; an
  optional follow-up if the tracker wants them.
- **No scrapping date column exists**, so none is proposed; the dates are in each cell's note.

## Refs dropped before the build (`scrapped_dropped_refs.json`)

- nauticalvoice (rows 16, 23) — a syndicated rewrite of the splash247 piece, not an independent source.
- lngprime Cosmopia article (row 49) — body paywalled; the vessel is named only in an image caption.
- shipandbunker week-36 report (row 54) — HTTP 404 at build time; the research agent's PASS did not reproduce.

## Checks

- Overlap with the other pending sep-17-pass batches (by `apply_patch.csv` `key` + `column`):
  **no cell is proposed twice.** Same-row, different-cell overlaps only — batch 4 proposes Shipowner
  country/area on 10 of these rows, batch 6 appends companion refs on row 61's `[ref]` cells
  (incl. `Status [ref]` — this batch touches row 61's Vessel type only). Apply order is free.
- `dedupe_check.py` (whole backend): no group involves any of the 19 rows.
- `qc_backend.py` on the live backend with the new Status check: unchanged (7 LOW).

## Script / doc changes committed with this batch

- `scripts/lookups.py` — `CONTROLLED_VOCAB["Status"]` (incl. `scrapped`); `scripts/qc_backend.py`
  — Status is now shape-checked (MED `bad-shape` on anything outside the vocab).
- `scripts/url_verifier.py` — `value_variants("scrapped")` renders demolition wording ("sold for
  recycling", "sold for demolition", "cash buyers", "beached" …) so the §3.8c gate can corroborate
  a `scrapped` cell.
- `scripts/igu_reconcile.py`, `scripts/build_workbook.py` (igu mode) — the dropped bucket now
  suggests Status → `scrapped`, never removal.
- Tests: 327 pass (new: scrapped gate wording, Status vocab QC).
- Docs: IG SOP rev 2 (§1, §5.2), `CLAUDE.md` (new hard requirement "never propose deleting a
  backend row"), `docs/inclusion_criteria.md` (Scrapped category; cut-off governs additions only),
  `data/controlled_vocab.md` (Status section), `docs/pointers.md`.

## Files

- `lng_carrier_fix.xlsx` — README / fix / QA_review, zero formula errors.
- `fix.json` — the batch source (with shipvault companions patched in).
- `shipvault_api_refs.json` — companion-ref log.
- `scrapres_A.json`, `scrapres_B.json`, `scrapres_C.json`, `scrapres_FSU.json` — per-group research
  (subagent output; every ref was re-gated centrally, never pre-trusted).
- `scrapped_dropped_refs.json` — refs dropped on judgment / 404.
- `digest.md`, `decisions.csv`, `apply.json`, `apply_rows.csv`, `apply_patch.csv`, `conflicts.csv`
  — apply artifacts: 19 auto-safe, 19 accept, 0 conflicts.

## Apply

Apply SOP unchanged (`apply_rows.csv` paste or `tools/apply_patch.gs` on `apply_patch.csv`, DRY_RUN
first), then `python scripts/verify_apply.py --batch batches/2026-09-17_1702ET_fix_scrapped_status --pull`.
If the sheet's Status column has a data-validation dropdown, add `scrapped` to it first.

## Applied 2026-09-17 19:00 ET

Written to the backend sheet by Claude at Baird's request ("go ahead and add the scrapped yourself
from the batch"), through the Sheets API (`values.batchUpdate`, `RAW`, 38 single-cell ranges built
from `apply.json` — row_id → live row resolved from column A of the sheet at write time; every
target cell was read first and held the expected old value: `active` / the IGU 2025 landing-page
ref, `conventional` / blank on row 61). The Status dropdown already listed `scrapped`.
`python scripts/verify_apply.py --batch … --pull`: **38 landed, 0 mismatch, 0 missing**
(`verify_report.csv`). `qc_backend.py` after: 8 LOW (name checks), no HIGH / MED. Map fleet
re-exported in `../lng-carriers-map` (row 61 → FSU adds Puteri Delima Satu, 59 vessels).
