# Comprehensive discovery pass — 2026-09-23

Plan: `docs/plans/2026-09-23_comprehensive-discovery.md`. Scope confirmed with Baird
(Discovery SOP §2): all four completeness streams, IGU reconciled into stream 3,
7 main + 14 secondary yards at **full pagination**, **expanded** proposed-bucket
threshold (named charterer/owner + named program + approximate delivery window, no
ship count required), no active-fleet re-audit.

**This is a completeness pass, not a gap-window catch-up.** Every prior discovery run
picked a contract-date window and swept CSB page 1. That finds the leading edge and
nothing else: a hull that slipped off page 1, or an order whose contract date we never
knew, is invisible to it at any window width. Here each source's *whole* orderbook and
fleet table was put next to the *whole* backend (1,172 IMO-bearing rows, 305 `on order`)
and made to balance yard by yard.

## Result: 1 candidate

| | |
|---|---|
| Candidate vessels | **1** (Maran Gas Efessos, IMO 9627497) |
| Backend status flags | 31 (hull fills, status/IMO disagreements, count deltas) |
| New rows implied by CSB | **0** |
| dedupe_check | 0 HIGH (50 MED / 23 LOW are the pre-existing placeholder background) |

### C1.1 — Maran Gas Efessos, IMO 9627497

A **seeding gap**, not a new vessel. IMO 9627497 is printed in both IGU World LNG
Report 2025 and 2026 Appendix 3 (fleet) and appears in no backend row, by IMO or by
name. Its four sister ships are all present — Maran Gas Delphi (sheet 343), Lindos
(376), Mystras (377), Troy (379) — all 159,800 cbm / DFDE / membrane / Hanwha Ocean,
all citing the IGU 2025 landing page. Efessos's IMO is adjacent to Lindos's (9627502).

Every value cites what IGU 2026 prints for that IMO (`igu_refs.corroborates_cell`,
IMO-keyed, IG SOP §1), corroborated by shipvault's unit record where it agrees.
Per the 2026-09-21 Name rule the database was checked first: shipvault reads
`Maran Gas Efessos` too, so IGU's name is not in dispute and nothing goes to
`Other names`.

Three cells cite IGU **alone**, deliberately: shipvault's page says `Daewoo` / `Okpo`
(the pre-2023 yard name) and cannot corroborate the controlled value `Hanwha Ocean`,
and it states no cargo type, vessel type or propulsion. `Hull number` (2291) is from
shipvault only — IGU prints no hull column, and the four sister rows leave that cell
blank, so it is the one value here that goes beyond the sibling pattern.
`Contract date` is omitted: no source states one.

## Completeness statement, stream by stream

**S1 — whole-orderbook reconciliation (`scripts/orderbook_reconcile.py`).**
286 CSB LNG/FSRU hulls across 21 yards, all pages; IGU 2026 Appendix 3 (804) +
Appendix 4 (301) with 2025 (742 + 337) layered on; 305 backend `on order` rows.
Residue after reconciliation: **2** CSB hulls with no backend row, **0** IGU
orderbook IMOs with no backend row, 32 CSB slots the yard has not indexed a hull
for (cluster-level only), 20 backend-only `on order` rows.

Both surviving CSB hulls are near-miss **fills**, not new vessels, and are **not**
proposed as rows:

- `Samsung 2797` (IMO 1180364, MISC Berhad FSRU, contract 2026-04, delivery 2029-02)
  ↔ sheet **1159** `Samsung HI (MISC FSRU)` (MISC, contract 04-May-2026, delivery
  2029). CSB says **300,000 cbm**; the backend says 170,000. 300,000 cbm is not a
  plausible FSRU — treat CSB's figure as suspect, propose the IMO and hull only.
- `Hudong Zhonghua H2015A` (IMO 1168914, MISC Berhad, contract 2026-01, delivery
  2029-08) ↔ sheet **1175** `Hudong-Zhonghua (MISC 5)` by elimination: CSB lists five
  MISC hulls at Hudong (H2014A, H2015A, H2016A, H2017A, H2018A) and the backend holds
  exactly five MISC rows there (1151, 1152, 1153, 1174, 1175); the other four are
  already matched. Delivery year disagrees (CSB 2029 vs backend 2030), which is why
  the automatic pass would not claim it.

**A defect was found and fixed mid-pass.** `csb_fetch.py` parses the yard *orderbook
list*, which carries **no IMO column**, so the reconciler could only key on the hull
number — and every vessel the backend holds under a **name** with a blank hull cell
read as a missing vessel. The first artifact claimed 9 such vessels. All nine were in
the backend:

| CSB hull | ship-page IMO | backend |
|---|---|---|
| Hanwha Ocean 2593 | 1069950 | sheet 1031 `Al Ghafat` |
| Hanwha Ocean 2594 | 1069962 | sheet 1032 `Al Sidriya` |
| Hanwha Ocean 2595 | 1069974 | sheet 1034 `Ain Snan` |
| Hanwha Ocean 2596 | 1069986 | sheet 1035 `Al Wasmi` |
| Qatar 9 | 9981439 | sheet 888 `Hull 3393 (HDHHI)` |
| Qatar 10 | 9981441 | sheet 889 `Hull 3394 (HDHHI)` |
| Dalian G175K-5 | 1013494 | sheet 814 `Sea Energy` |

The CSB **ship-detail** page does print the IMO. `orderbook_reconcile.py` gained a
fourth pass (`--resolve-imo`, `resolve_ship_imos()`) that fetches each unmatched
hull's detail page — through `sweep.py`, per-host paced and cached in
`work/csb_ship_imo.json` — and re-keys on the IMO before anything is called absent.
`csb_unmatched` fell 9 → 2 and `csb_hull_to_add` rose 8 → 15. Four new tests pin it.
**Never call a CSB hull absent without that pass.**

**S1 — shipvault re-enumeration.** Complete, null result. 6,501 distinct unnamed
newbuilding units; 378 `LNG CARRIER`; 331 `ON ORDER`; 278 at ≥100,000 GT (the
conventional-carrier proxy — `docs/inclusion_criteria.md` sets no numeric cutoff).
198 matched a backend hull on the bare digit run; the 80-unit residue resolved
entirely by inspection — most are shipvault's own per-owner ordinals (`HULL 1`,
`HULL 2`, default gt 120000); ADNOC 2708/2858/2859 are stub rows 1228/1230/1231;
BW LNG `HULL 9341` is sheet 1090 `Hull H8341` (8341/9341 — a lead, not a finding);
HAMMONIA `HULL 1476` is sheet 925 (`Hull YZJ2022-1476`, whose first digit run is
`2022`, an extractor artifact, not a gap). **Zero new vessels.**

The MISC question from the prior pass is **settled**: shipvault's H2014A–H2023A is
5 firm + 5 optional (S4/S5 confirmed the optional five via imarinenews). CSB's five
hulls and the backend's five rows are the firm slots.

**S1 — GTT count cross-check.** 25 LNG-carrier tank-design announcements on
`gtt.fr/news`, Feb–Sep 2026 = 56 designs: Jiangnan 14, Samsung HI 13,
Hudong-Zhonghua 13, HD KSOE 11, Hanwha Ocean 4, 1 unattributed (including one
18,700 m³ small-scale on 23 Sep 2026, out of scope). Backend contracts 2025-06 →
today = 86 (HD KSOE 26, Samsung 23, Hanwha 15, Hudong 12, Jiangnan 6, Hanwha Philly 4).
Jiangnan's apparent 14-vs-6 shortfall is explained by the six Jiangnan/ADNOC stub
rows (sheets 1226–1231), which carry no contract date. No unexplained per-yard
shortfall. **Count evidence only — a GTT tank-design count is never a per-vessel
`[ref]`.**

**S2 — 2026 delivery cohort.** 28 vessels enumerated, 25 matched, **0 candidates**,
3 status findings (sheets 814, 914, 928).

**S3 — FSRU completeness + terminals cross-check (incl. GIIGNL).** **0 candidates.**
One Name defect: sheet **20** reads `KLNGTP Americas`; GIIGNL prints
`KARMOL LNGT Powership Americas` (IMO 9045132). Four small-scale vessels raised as
scope questions rather than candidates.

**S4/S5 — proposed-bucket sweep, expanded threshold.** 1 candidate (the Maran Gas
Efessos row above) and 4 backend findings.

## Reverse flags (the backend, not the sources)

- **20 backend `on order` rows** that no source's orderbook carries — a phantom, a
  duplicate, or (most often) a vessel already delivered and not yet re-Statused.
  Listed in `orderbook_reconcile.json` → `backend_only`. Not acted on here.
- **58 IGU status findings** — IGU 2026 carries the hull on the orderbook while the
  backend row is not `on order`.
- **9 IGU no-IMO count disagreements** (of 17 clusters). IGU prints 46 orderbook rows
  with no IMO, so these are answerable as *counts* and never vessel by vessel. Largest:
  Knutsen × Hanwha 2029 (IGU 7 / backend 5), NYK × Hyundai Ulsan 2028 200,000 cbm
  (IGU 4 / backend 2), BW × Hyundai Samho 2028 177,000 (IGU 2 / backend 0),
  Glovis × Hyundai Samho 2029 (IGU 2 / backend 0), Hanwha Shipping × Hanwha Ocean
  2027 (IGU 2 / backend 0).
- **Sheet 1004 `Athlos` — IMO disagreement.** IGU 2025 Appendix 4 prints IMO
  **9315379**; the backend carries **9999981**. IGU 2026 drops the row. Verify against
  a registry before changing either side; not proposed here.
- **IMO 9696266 `Hai Yang Shi You 301`** (Jiangnan, CNOOC, 30,000 cbm, del 2015) is in
  both IGU fleet tables and absent from the backend. **Out of scope** — small-scale per
  `docs/inclusion_criteria.md`. Recorded so the next pass does not re-open it.

## Routed to a fix batch (not proposed here)

31 `backend_status_flags` in the workbook's QA_review sheet. The substantive groups:

- **15 hull-number fills** for rows whose Hull number is blank (`csb_hull_to_add`),
  each with the CSB ship page that states it — including the seven IMO-matched rows
  in the table above.
- **3 CSB status findings**: Jiangnan H2705 → sheet 939 `Al Taweelah`;
  Hudong H1894A/H1895A → sheets 920/921 `Puteri Johor` / `Puteri Kedah`. CSB lags
  delivery; informational.
- **2 near-miss IMO+hull fills** (Samsung 2797 → sheet 1159, Hudong H2015A → sheet
  1175), each with one field in conflict — resolve the conflict before filling.
- The `Athlos` IMO disagreement and the sheet 20 GIIGNL Name defect.

## Coverage gaps in this pass (stated, not papered over)

- **S4/S5**: WebSearch quota was exhausted before Bursa Malaysia, HKEX, DART/KIND,
  Riviera, Seatrade and TradeWinds could be swept for the six-day leading edge
  (2026-09-17 → 2026-09-23). The completeness streams (S1–S3) are unaffected — they
  are source-enumerations, not searches.
- **S5**: NextDecade/Rio Grande, Commonwealth LNG and Argent LNG (zero backend rows
  each) remain unswept for charterer-program vessels.

## Sibling-repo bug report (read-only — reported, not patched)

`../lng-terminals-researcher/scripts/fsru_sync_check.py`, found by S3:

1. `load_carrier_vessels()` recognises only the headers `VesselName` / `Vessel Name` /
   `vessel_name`. This repo's backend column is `Name`, so the function reads **zero**
   records and the check silently passes on an empty set.
2. `gather_gem_fsrus()` does not filter `facility_type`, so it mixes import FSRUs with
   export/FLNG units.

Not this repo — for the owner to fix.

## Tooling changed with this batch

- `scripts/orderbook_reconcile.py` — new (S1). `--resolve-imo` / `resolve_ship_imos()`
  / `_parse_ship_imo()` added mid-pass after the 9-false-positive finding above.
- `scripts/normalize.py` — `hull_core()` added: the sources write one hull three ways
  (`Samsung 2808` / `Hull 2316 (SHI)` / `Jiangnan H2709`), and `normalize_hull()` only
  canonicalizes the CSB shape, so keying on it matched nothing.
- `scripts/dedup_index.py` — `_base_key` → `base_key` (now imported by the reconciler);
  `stubs` + `match_pending()` so a batch pasted as columns A–E only is not re-reported
  as missing.
- `scripts/csb_fetch.py` — all-yards / all-pages sweep.
- Tests: `tests/test_orderbook_reconcile.py` (32), `tests/test_dedup_index.py`,
  `tests/test_csb_fetch.py`.

## Artifacts in this directory

`candidates.json`, `orderbook_reconcile.json`, `csb_ship_imo.json`,
`shipvault_orderbook_crosscheck.json`, `gtt_orders.json`, `discovery_s2.json`,
`discovery_s3.json`, `discovery_s45.json`, `dedupe_report.csv`,
`lng_carrier_candidate_vessels.xlsx`.

Not applied. Nothing here was written to the backend.
