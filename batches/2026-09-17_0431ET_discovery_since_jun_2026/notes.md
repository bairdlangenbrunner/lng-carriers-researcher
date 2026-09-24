# Discovery batch — orders since June 2026 (built 2026-09-17, sep-17-pass)

Gap window: 2026-05-01 → 2026-09-17 (backend's latest contract date at pull: 08-Jun-2026; window
opened a month early for overlap). All-yards sweep: CSB (Ring A), Korean disclosures via English
proxies (Ring B), trade press (Ring C), plus a shipvault on-order enumeration as a completeness
cross-check. SOPs: Discovery + [ref]-Fill as of the 2026-09-17 pull.

## Candidates — 12 vessels in 5 clusters (one workbook row per vessel)

| id | vessels | cluster | conf |
|---|---|---|---|
| C1.1–C1.4 | 4 | Samsung HI × Dynagas, 200,000 cbm, contract 14-Sep-2026, delivery 2029 | Y |
| C2 | 1 | HD Hyundai HI × Tsakos (2nd LNGC, option), 01-Jul-2026, $254M, delivery 2029 | G |
| C3 | 1 | HD Hyundai HI × unidentified owner, FSRU, 30-Jun-2026, delivery 2029 | Y |
| C4.1–C4.4 | 4 | Jiangnan × ADNOC L&S, 175,000 cbm, 10-Jul-2026, delivery 2029, hulls H2706–H2709 | G |
| C5.1–C5.2 | 2 | Jiangnan × ADNOC L&S option pair, 175,000 cbm, 25-Aug-2026, hulls H2858/H2859 | G |

Decisions made for you (flip in `decisions.csv` if you disagree):
- **C1 demoted G → Y.** Samsung's disclosure names only an "Oceania-based" owner; Dynagas is
  market-sourced (Splash247 "linked"). Yard / count / date / capacity are solid; owner is not.
- **C2 owner written `Tsakos`** to match the existing row 1100 convention (source says Tsakos
  Energy Navigation / TEN).
- **C4/C5 carry IMO + hull number from shipvault** (each cited to its own shipvault unit page; all
  six IMOs pass the check digit). Name = `Hull H27xx`, the no-tag form the backend uses for
  Chinese yards. Press gives delivery 2029 for the C5 option pair; shipvault schedules them
  2030-01 / 2030-03 — left at the gated press value, worth a look.
- **>5-cluster escalation rule:** 5 clusters over a 3.5-month gap is normal leading-edge lag, not a
  systematic gap — no escalation. The shipvault cross-check below is the one thing that might be.

Every `[ref]` was re-gated centrally against its own cell value (§3.8c): 118/118 pass. No GEM /
abarrelfull / vesselfinder URLs.

## Backend flags (conflicts.csv — never auto-applied)

- **Rows 1168/1169 (BW LNG × HD Hyundai Samho):** Capacity 174,000 → **177,000** (PortNews citing
  BW's fleet list; new three-tank design).
- **Row 1162 (MISC FSRU × Samsung HI):** Price $330M vs Businesskorea's 484.8bn won ($353.59M) for
  the same date/yard/type. Flag only.
- **Rows 1182–1185 (COSCO × Jiangnan):** hulls now assigned H2954–H2957 (filled in tonight's
  data-fill batch from shipvault; ordinal↔hull mapping is arbitrary). Press names the owner
  "COSCO Shipping Energy Transportation".
- **Rows 1187–1203 (Mozambique LNG, proposed):** July press splits the 17 slots — HD Hyundai Samho
  9 (MOL 5 = rows 1187–1191, K Line 4 = 1192–1195), Samsung HI 8 (NYK 4 = 1196–1199, Maran Gas 4 =
  1200–1203). Backend has owner "MOL, NYK" on all 17 and HD Hyundai HI as builder on the first 9.
  Single source (imarinenews translating TradeWinds); TotalEnergies extended the slot deadline to
  September 2026. Still `proposed`.

## Proposed-bucket review (`proposed_review.json`)

No cell edits. Recommend **deleting Woodside placeholder rows 1204–1206**: that slot reservation
converted into the Seapeak × Samsung HI order already in rows 1165–1167. Mozambique LNG
(1187–1203) and Equinor 4 (1186) stay `proposed`.

## Shipvault orderbook cross-check (`shipvault_orderbook_unmatched.json`)

244 on-order LNG units enumerated; 167 match the backend by IMO; most of the rest match by hull or
are small-scale / out of scope. Unmatched large hulls after that:
- ADNOC H2706–H2709, H2858/H2859 → C4/C5 above.
- **MISC × Hudong-Zhonghua H2014A–H2023A = 10 hulls; backend has 5 rows** (1154–1156, 1177, 1178).
  Possible five missing vessels — being researched separately; see the sep-17-pass summary.
- Hanwha 2627/2628 (Knutsen) ↔ probably rows 1161/1172; SHI 2803 (J.P. Morgan) ↔ probably row
  1118; SHI 2808 (Purus) ↔ probably row 1173. Not written anywhere without press confirmation.
- Three CNOOC × Hudong-Zhonghua units with no hull/IMO ↔ rows 943, 1220–1222.

## Script changes riding with this batch

`scripts/url_verifier.py` `value_variants`: Status `on order` is corroborated by order wording
("has ordered", "shipbuilding contract", "carrier order" …), and untagged hull numbers
(`Hull H2706`) get the same variants as tagged ones. Tests added (193 pass).

## Shipvault companion refs (added 2026-09-17, RF rev 21 §6a.8)

Most `shipvault.com/ships/{id}` pages render blank in a browser (the site cannot parse its own
double-encoded API answer), so a reviewer cannot see the value the gate verified. Every ref citing
such a page now carries the unit-record URL
`https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}` as a second ref right after it:
**12 companions added, 0 skipped** (`shipvault_api_refs.json`). Source JSON patched with
`scripts/shipvault_api_refs.py`, workbook rebuilt + recalced (zero errors), apply artifacts
regenerated; decisions unchanged, and the only diff in `apply.json` / `apply_rows.csv` /
`apply_patch.csv` is the added URLs.

## Unsourced Vessel type removed (2026-09-23, Baird)

C1.1–C1.4 (`Samsung HI (Dynagas 1)`–`(Dynagas 4)`) and C2 (`HD Hyundai HI (HHI) Ulsan (Tsakos 2)`)
carried `Vessel type` = `conventional` with a blank `[ref]` — a class call no source made. No page
states it for these hulls (sedaily, Splash247 ×2, LNG Prime, new-ships, JoongAng, GlobeNewswire,
Riviera checked; Hellenic Shipping News "passes" only on a sidebar headline), and IGU 2026 predates
both orders. The cell is now blank on all five; workbook rebuilt + recalced (zero errors), apply
artifacts regenerated, decisions unchanged. `build_workbook.py --mode discovery` now refuses any
filled cell with a blank `[ref]` (except `unknown` and a placeholder Name).

## Applied — C4.1–C4.4 directed session write (2026-09-23, AP §2d)

Live rows 1226–1229 (Jiangnan H2706–H2709, ADNOC L&S) had only the A–E stub in the sheet. Baird
directed the write in-session ("go ahead and write those rows directly to the backend and make sure
it's all reflected in the living-workbook-for-update"). Fresh pull → 100-cell plan (25 per row, all
old values blank except the placeholder Name) → `directed_2026-09-23_revert.csv` → `gws-gem-write`
`values.batchUpdate` (RAW) → re-pull: **100/100 hold**. `push_log.jsonl` attributes each cell to
`claude session (directed)`; no `review_log.jsonl` entry was written.

Differences from the batch's proposal, all re-gated on the fresh pull:
- Name and Hull number yard-tagged, `Hull H2706 (Jiangnan)` (RF §4.17): a placeholder restyle, so
  the Name ref was kept and no former name went to `Other names`.
- Each hull's CSB `ship.aspx` page was added as a ref on Hull number, Shipowner, Shipbuilder,
  Capacity and Delivery year (RF §3.3b). For Shipowner it passes now that the gate reads
  `ADNOC L&S` = `ADNOC Logistics & Services` (`normalize._OWNER_ALIASES`, PR #72).
- The yard columns (country, lat/lon, plus code, accuracy, refs) were copied from the other
  Jiangnan rows (RF §4.8 / DC §6.7). The yard-country ref `jnshipyard.com.cn` timed out (000) on
  the gate; it is the ref all 20 Jiangnan rows already carry.

C1.1–C1.4 and C5.1–C5.2 were written separately (next section). C2 (Tsakos 2) is not in the sheet.
Rows 1226–1229 have a blank column-A `row_id`.

Script fix riding with this: `review_data.py` and `verify_apply.py` matched a new row only against
rows with a column-A `row_id` and only by Name / Hull number, so these stubs read as missing, and the
tag restyle would have hidden them anyway. They now search every row, match by IMO too, and count a
new row as present only when that row holds every column the candidate fills (a pasted stub stays
open). The living workbook's `processed` column now shows C4.1–C4.4 as incorporated.

## Applied — C1.1–C1.4, C5.1–C5.2 + row 1170 owner country (2026-09-23, AP §2d)

Baird directed: "go ahead and add in the rest of the data for rows 1230-1231 and for the dynagas 1–4
rows … and you can make a decision on the Bermuda/United States". Fresh pull → 140-cell plan →
`directed_2026-09-23b_revert.csv` → `gws-gem-write` `values.batchUpdate` (RAW) → re-pull:
**140/140 hold**. Recorded in `push_log.jsonl` as `claude session (directed)`.

- **C1.1–C1.4, rows 1220–1223 (Samsung HI, Dynagas):** Status, Shipowner `Dynagas`, Shipowner
  country `Greece`, Shipbuilder, Capacity 200000 cbm, Delivery year 2029, Contract date 14-Sep-2026,
  plus the Samsung yard columns copied from sibling rows. Splash247 is the owner-country ref; it
  calls Dynagas "the Greek shipowner". dynagas.com and dynagaspartners.com return 000 even through
  the fetch ladder. Name stays `Samsung HI (Dynagas N)` (no hull numbers or IMOs are public yet).
- **C5.1–C5.2, rows 1230–1231 (Jiangnan H2858/H2859, ADNOC L&S):** Name restyled and Hull number
  filled as `Hull H2858 (Jiangnan)` (the Name ref is kept, shipvault refs on the Hull number), then
  Status, Shipowner, owner country, Shipbuilder, Capacity 175000 cbm, Delivery 2029, Contract date
  25-Aug-2026, and the Jiangnan yard columns. Seatrade failed the gate on Contract date, so that
  cell carries only the aletihad ref.
- **Not written:** Vessel type (no ref for either order). Price, because the Dynagas order is
  reported as $1.01bn by sedaily and $1.05bn by splash, and ADNOC's $444m covers the pair; a
  DF §5a per-vessel derivation would be Y at most. CSB lists none of the six yet: the Jiangnan
  orderbook stops at H2857 and the Samsung orderbook has no Dynagas entry (`--all-pages`,
  2026-09-23).
- **Row 1170 (row_id 1227, Samsung 2808, Purus Marine), outside this batch:** Shipowner
  country/area changed from `Bermuda` to `United Kingdom`, with the ref replaced by
  `purus.com/our-services/gas` (London HQ, and the value on Purus's other four rows). The
  Bermuda ref (cyprusshippingnews, 2026-06-02) covers the May 27 "Bermuda-based" five-vessel
  order, which is CSB hulls 2803–2805, not Purus's June hull 2808. As a result the data-fill
  line `2026-09-17_0511ET_data_fill_on_order::1227|Shipowner country/area` is no longer marked
  incorporated in the living workbook. Its push_log key is `…::row1170|<column>`.
- The living workbook shows C1.1–C1.4 and C5.1–C5.2 as incorporated. verify_apply: only C2 is
  missing.

