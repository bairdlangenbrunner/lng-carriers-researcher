# Data-fill — on-order core facts + whole-backend derivables (2026-09-17, sep-17-pass)

Fresh pull 2026-09-17 (1,220 rows). Scope: `derive_fills.py --since 2000-01-01` (whole backend)
for the derivable autofills; research fan-out limited to **on-order rows** and the core facts
(Operator/charterer, Contract date, Price, Hull number, IMO number, Capacity, Propulsion /
Cargo / Vessel type). Additive to blank / `unknown` cells only — a pre-merge filter dropped
4 research fills whose target cell was already filled (logged as findings).

## What is in the workbook — 1,003 proposals on 483 rows

| field | accept (G / derivable) | hold (Y) |
|---|---|---|
| Shipowner country/area | 329 | 0 |
| Price (+ companion Price currency = USD) | 24 | 124 |
| Operator/charterer | 44 | 71 |
| Contract date | 22 | 68 |
| Hull number | 30 | 19 |
| Cargo type | 6 | 32 |
| IMO number | 1 | 20 |
| Capacity (+ companion Capacity units = cbm) | 0 | 16 |
| Propulsion type | 3 | 10 |
| Vessel type | 0 | 9 |
| Yard location (5 cols) | 2 rows | 0 |
| Shipowner | 0 | 1 |

`decisions.csv` is pre-filled accept = G/derivable, hold = Y. The companion currency/units
cells carry **the same decision as their parent Price/Capacity fill** (aligned by hand after
the first apply_batch run) — flip them together. Prices are written as full USD
(`250000000` + `USD`); the backend mixes that with the older `250` + `$m` form, which is a
QC-release normalization question, not touched here.

Sources of the research fills:
- `research_of1..8.json` — eight sonnet subagents, one slice of on-order clusters each
  (trade press first: LNG Prime, Offshore Energy, Splash247, Riviera, yard/owner releases).
- `research_sv.json` — central shipvault pass: Hull number / IMO number / Capacity from the
  unit record matched on the row's IMO (or yard + hull). All Y unless press-corroborated.
- `research_leads.json` — shipvault orderbook leads matched to placeholder rows by yard +
  order month + delivery date (row_ids 1218, 1227, 1219, 1205), plus Price for row_ids 67/68.

## Central §3.8 gate (merge_fills.py) — hard block, no soft flags

1,027 (fill, url) checks over 162 distinct URLs. **131 refs dropped** for not carrying the
cell value (56 Price, 73 Shipowner country/area sibling-copied refs, 2 Hull number), 15
blocked; **28 research fills demoted** to documented blanks for losing every ref (26 Price,
2 Hull number). Most demoted Prices were "package total ÷ N" derivations — the page states
the total, not the per-ship figure. **Superseded the same day — see "Order-total prices"
below: those are now proposed, with refs.** IMOs were additionally
validated by check digit (one shipvault IMO, 1184679 for row_id 1205, fails it and was not
proposed). 26 companion currency/units fills whose parent was demoted were removed.

## Order-total prices (DF rev 3 §5a, added 2026-09-17 afternoon)

The research prompt told agents to divide a reported order total by the ship count; the gate
then dropped the total-stating URL (the per-ship figure is not on the page). 26 such Prices
were demoted to blanks, and 21 more kept their value with **no ref and a default `accept`**
because the agents had set `derivable: true` on them (live row 918 was the one Baird caught).
Rule agreed with Baird and written into the SOP as DF §5a: total ÷ N is a real data point —
Yellow at most, `derived_from: {total, n}`, the note states the division, and the gate
corroborates the **total**, so the URL stays in `Price [ref]`.

All of them re-gated under §5a: **48 Price cells across 15 orders, every one with a passing
ref, all Y / `hold`** (with their `Price currency` companions):

| live rows | order | total ÷ N | per vessel | ref |
|---|---|---|---|---|
| 917, 918, 943, 1220–1222 | Hudong-Zhonghua × CNOOC/CMES/NYK | $1.26bn ÷ 6 | 210,000,000 | Splash247 |
| 890–896 | HD Hyundai Heavy × MISC / NYK / K Line / China LNG septet | $1.5bn ÷ 7 | 214,285,714 | Seatrade |
| 955–959 | Samsung × Seapeak | $1.08bn ÷ 5 | 216,000,000 | Offshore Energy |
| 1149–1151 | Hudong-Zhonghua × Bonny Gas | $744m ÷ 3 | 248,000,000 | Baird Maritime |
| 1091, 1092 | Samsung × Seapeak | $499m ÷ 2 | 249,500,000 | Splash247 |
| 1095, 1135 | Samsung × Purus | $503m ÷ 2 | 251,500,000 | Splash247, Global Flow Control |
| 1139, 1140 | Hanwha × Alpha Gas | $503m ÷ 2 | 251,500,000 | Splash247 |
| 1141, 1142 | Hanwha × Maran Gas | $505m ÷ 2 | 252,500,000 | Splash247 |
| 1157–1160 | HD Hyundai Heavy × NYK / Ocean Yield (second four) | $1.02bn ÷ 4 | 255,000,000 | LNG Prime |
| 1147, 1148 | HD Hyundai Samho × Sonangol | $511m ÷ 2 | 255,500,000 | Splash247 |
| 951, 952 | Hanwha × Maran Gas | $511.6m ÷ 2 | 255,800,000 | PortNews |
| 1115, 1152, 1153 | HD Hyundai Samho × Capital Clean Energy | $769.5m ÷ 3 | 256,500,000 | CCEC release |
| 1103, 1104 | Samsung × Celsius Tankers | $514m ÷ 2 | 257,000,000 | Splash247 |
| 1093, 1094, 1133, 1134 | HD Hyundai Heavy × NYK / Ocean Yield (first four) | $1.04bn ÷ 4 | 260,000,000 | LNG Prime |
| 1055, 1056 | HD Hyundai Heavy × Evalend | $530m ÷ 2 | 265,000,000 | Splash247 |

- Live rows 890–893 are **new to the batch**: the agent priced three of the septet's seven
  rows; the article covers all seven (hulls 3395–3401), so the other four got the same fill.
- The total has to be the yard contract value. Seapeak's releases give a "total fully
  built-up cost" ($1.1bn for the five, $511.6m for the pair) — not used; the yard-side
  figures above are. Where two outlets convert the same won figure differently (Alpha Gas
  $503m / $501m; Purus $503m / Riviera's $502.8m) one is cited and the other named in the note.
- **Still blank: live rows 928, 930, 1003 (Capital Gas).** The only figure found is the
  $3.13bn CPLP paid Capital Maritime for an 11-ship fleet — an acquisition price between
  affiliates, not a newbuilding price. Documented blank with that note.
- Documented blanks 830 → 807; stale "dropped by §3.8" Price findings removed for these rows.

## Findings that need a human eye (also in `conflicts.csv` / `candidate_findings`)

Likely duplicates
- **Hanwha Philly**: live rows 1083 (`Hanwha Philly 1`, row_id 666) ↔ 1085 (`…Philadelphia
  2608`, row_id 1144), and 1132 (row_id 667) ↔ 1086 (row_id 1145): same owner, yard and
  contract date (21-Jul-2025 / 26-Aug-2025). The placeholder rows look like the same two
  ships. Shipvault's record for IMO 1132941 (row_id 666) is a different hull (`HL-B95K-3`),
  so that IMO is suspect too.

Possible mis-citations on existing refs
- live rows 1182–1185 (Hudong-Zhonghua × TMS Cardiff): the splash247 ref describes a Samsung order.
- row_ids 1162/1163: lngprime …/180833 is a single-vessel Purus order.
- row_ids 1212/1213: unrelated Hayfin refs; Price stored as `2.54E+08`.
- row_id 1218: Price 252000000 does not match its source ($726M five-ship package) — possibly
  cross-contaminated from row_id 1227.
- row_ids 1207/1208: a ref looks like a VLGC article.

Value conflicts (not proposed — backend cell is filled)
- row_id 197 (Hull 3441): Delivery year 2026 vs NYK / shipvault 2027.
- Samsung × CMES batch: backend 180,000 cbm vs 174,000 in the sourcing articles; Jiangnan ×
  Taiping duo: 170,000 vs 175,000.
- row_id 375: Shipowner Smart LNG vs SCF direct.
- row_ids 255/256: 16-month order-date gap between shipvault and CSB.
- row_ids 318/319 (Yangzijiang): original contract terminated, hulls built speculatively.
- row_ids 515/516 (DSIC × CMES): Sinochem charter covers "3 of 4" — which hulls is unclear.
- live rows 933/934: AIS/shipvault names differ (Sea Argosy / Sea Harmony vs Dachuan Haishang / Hai Xie).

Shipvault owner tags that were wrong (why shipvault-only owner data is never proposed)
- Sinokor ↔ TMS Cardiff; Hanwha ↔ Glovis/Oryx; Shandong Marine tagged as Nakilat 180k;
  row_ids 280/281 (Petronas Carigali), 273/274 (MOL LNG Transport), 290/293 (Nakilat vs China
  LNG Shipping). row_id 1218: shipvault alone says owner `J.P. Morgan` — left `unknown`.

Structure
- The `hudong-zhonghua|mol` cluster is really four unrelated programs (CNOOC-chartered sextet,
  QatarEnergy first batch of four, QC-Max 271k class, a CNOOC-direct sub-batch with no
  source) — don't assume a shared contract date/price across its 16 rows.
- MISC × Hudong-Zhonghua (Petronas) is exactly five ships = row_ids 1196–1200; shipvault's
  extra hulls H2019A–H2023A have no citable press — watch in the next discovery run.

## Coverage caveats

- The session's WebSearch budget ran out part-way; later clusters were researched through
  `scripts/fetch.py` against site searches only, so their documented blanks (830 in total)
  are thinner than usual — "not found tonight", not "not findable".
- vesselfinder throttled this IP all night and is cited nowhere.
- Paywalled (TradeWinds / Upstream) contract dates and prices were not recoverable.

## Script change riding with this batch

`scripts/url_verifier.py` `_title_hit`: a digit status code in a page title is no longer a
soft-error when it is a quantity — "$500 million order" was being graded dead (HTTP 500).
That bug had cost row_ids 67/68 their Price ref; re-gated and restored here. Test:
`test_dollar_figure_in_title_is_not_a_status_code` (194 pass).

`scripts/merge_fills.py` (DF rev 3): `derivable: true` is honoured only on the DF §5 autofill
columns (`DERIVABLE_FIELDS`) and cleared with a warning anywhere else; a `derived_from` Price
is arithmetic-checked, gated on its total and capped at Y; a research fill left with no URL
is always demoted. `scripts/citation_qc.py --corroborate` recognises an order-total Price
cell instead of grading it `uncorroborated`. Tests: `tests/test_merge_fills.py`.

Known gap, not fixed: Status = `active` passes the gate on any page containing the bare word
"active" (boilerplate). Needs URL-/context-aware matching in `value_variants`.

Recalc: zero formula errors.

## Shipvault companion refs (added 2026-09-17, RF rev 21 §6a.8)

Most `shipvault.com/ships/{id}` pages render blank in a browser (the site cannot parse its own
double-encoded API answer), so a reviewer cannot see the value the gate verified. Every ref citing
such a page now carries the unit-record URL
`https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}` as a second ref right after it:
**119 companions added, 0 skipped** (`shipvault_api_refs.json`). Source JSON patched with
`scripts/shipvault_api_refs.py`, workbook rebuilt + recalced (zero errors), apply artifacts
regenerated; decisions unchanged, and the only diff in `apply.json` / `apply_rows.csv` /
`apply_patch.csv` is the added URLs.

## Shipowner country/area lines applied — 2026-09-21 20:40 ET

Baird's directive ("yes push them now"), following the shipowner-country ref batch
`2026-09-21_2003ET_fix_shipowner_country_refs`. **Only the
`Shipowner country/area` (+ `[ref]`) lines of this batch were written** — every
other column is untouched and still pending.

**Written:** 584 cells / 292 rows through the Sheets API (`gws-gem-write`,
`values.batchUpdate` RAW), addressed by row_id + header against a fresh pull —
292 country values into blank/`unknown` cells and their 292 `[ref]`s. 74 further
cells (37 rows) were already in the sheet and skipped as no-ops. **0 conflicts**:
no country line contradicted a non-blank backend value.

**verify:** all **658** `Shipowner country/area` lines read `landed` in
`verify_report.csv`. The report's 69 MISMATCH (all `Price`) and 26 MISSING
(`Price`, `Yard location*`, `Operator/charterer`) are this batch's *other*
columns, never applied — they are not from this push, and the batch stays open.
QC: 0 HIGH/MED. Dedupe: 0 HIGH, 71 MED / 29 LOW over the batch's rows — the
unidentified-slot pairs of the on-order fleet, unchanged by this push (the dedupe
key is builder|owner|capacity, which a country write cannot move).

### Two corrections made before writing (this is why it wasn't a straight push)

1. **The apply artifacts were a stale snapshot** (AP §2a). `apply_patch.csv`
   predated the ref batch, so 36 of its `[ref]` cells would have written the
   shipvault URL back over refs corrected 20 minutes earlier. Re-ran
   `apply_batch.py` against the fresh pull (decisions preserved, byte-identical).
2. **`data_fill.json` itself was stale against `data/shipowner_facts.csv`.** The
   2026-09-21 pass re-sourced the table but only rewrote the 63 *ref-less* fills;
   61 more still carried the old shipvault URLs. All 329 country fills were
   re-pointed at the table's current row for their owner tag (values all still
   agree with the table; no `AMBIGUOUS` tag in this set). Recorded in DF §5 rev 4.

Then every distinct (url, country) pair was re-run through the §3.8c gate
(`igu_refs.corroborates_cell`): **30 of 32 pass**. The two failures were dropped
from the 17 fills citing them, each of which keeps a passing ref (Rule F intact):

- `hls.co.kr/en/contact/location.do` (Hyundai LNG Shipping → South Korea, 15 rows)
  — 403, Wayback snapshots lack the content. Those rows keep the EMIS profile.
- `dnb.com/…united_liquefied_gas_shipping_(hong_kong)…` (→ Hong Kong, 2 rows) —
  the page does not contain "Hong Kong". Those rows keep the HKEXnews filing.

Countries written: Greece 88, Japan 83, Norway 49, South Korea 25, Denmark 23,
China 8, UAE 8, UK 3, Hong Kong 2, United States 2, Russia 1.
