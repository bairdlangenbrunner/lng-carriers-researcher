# Data-fill — on-order core facts + whole-backend derivables (2026-09-17, sep-17-pass)

Fresh pull 2026-09-17 (1,220 rows). Scope: `derive_fills.py --since 2000-01-01` (whole backend)
for the derivable autofills; research fan-out limited to **on-order rows** and the core facts
(Operator/charterer, Contract date, Price, Hull number, IMO number, Capacity, Propulsion /
Cargo / Vessel type). Additive to blank / `unknown` cells only — a pre-merge filter dropped
4 research fills whose target cell was already filled (logged as findings).

## What is in the workbook — 949 proposals on 477 rows

| field | accept (G / derivable) | hold (Y) |
|---|---|---|
| Shipowner country/area | 329 | 0 |
| Price (+ companion Price currency = USD) | 45 | 76 |
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
the total, not the per-ship figure, so the gate (correctly) refuses them. They are listed in
`conflicts.csv` with the source URL if you want to enter them by hand. IMOs were additionally
validated by check digit (one shipvault IMO, 1184679 for row_id 1205, fails it and was not
proposed). 26 companion currency/units fills whose parent was demoted were removed.

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

Known gap, not fixed: Status = `active` passes the gate on any page containing the bare word
"active" (boilerplate). Needs URL-/context-aware matching in `value_variants`.

Recalc: zero formula errors.
