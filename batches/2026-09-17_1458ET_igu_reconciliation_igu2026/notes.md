# IGU reconciliation — World LNG Report 2026 vs backend (2026-09-17, part of the sep-17-pass)

Governed by `docs/sops/igu_reconciliation.md` (IG rev 1, written with this batch). Comparison
only — **nothing here is applied**; actionable findings become follow-up fix / discovery batches.
All row numbers are **live sheet rows** (fresh pull 2026-09-17, 1,220 rows, identical to the
morning pull).

Why: IMO 9030814 `Puteri Delima` (row 25) is in the IGU 2025 fleet table and gone from the 2026
one. The backend was seeded from IGU 2025 (1,070 rows still `Original source = IGU`), so the new
edition is a whole-fleet check on the bulk load.

## Files

- `lng_carrier_igu_reconciliation.xlsx` — 11 sheets, zero formula errors.
- `igu_fleet_2026.json`, `igu_fleet_2025.json` — extracted Appendix 3 + 4 (`scripts/igu_fleet.py`).
- `igu_reconcile.json` — the buckets (`scripts/igu_reconcile.py`), incl. `leads`.
- `shipvault_leads.json` — raw shipvault answers for 49 review IMOs (48 with a record) (**leads, not refs**).

## Extraction

The 2026 PDF is not laid out like 2025: landscape spreads with **two tables per PDF page**, an Age
column added to the fleet table, a Vessel Type column added *last* in the orderbook, and 46
orderbook rows printed with an `Unknown` IMO. The extractor reads pdfplumber word coordinates and
takes the columns from each table's own header, so both editions go through the same code.

| | fleet | orderbook | no IMO | warnings |
|---|---|---|---|---|
| IGU 2026 (end-2025) | 804 | 301 | 46 | duplicate IMOs only (below) |
| IGU 2025 (end-2024) | 742 | 337 | 8 | none |

Checks: every IMO passes its check digit; per-page IMO-token counts agree; 742 − 18 dropped + 79
delivered + 1 added direct = 804; the 2025 extraction reproduces 1,068 of the backend's 1,070
IGU-sourced rows by IMO with zero capacity or cargo-type diffs (the other two have no IMO). The
old `igu-tanker-extraction` CSVs in `../old/` are the **2024** edition — not a regression check.

## Headline numbers

- 1,054 backend rows matched by IMO; 188 carry at least one field diff (179 `igu_changed`,
  2 `new_to_igu`, 43 `backend_differs`).
- 18 backend `active` rows dropped from IGU between editions.
- 47 Status disagreements, 24 already proposed by batch 1 (`0421ET_fix_delivery_rollforward`).
- 2 IGU-only vessels (1 candidate, 1 out of scope); 148 backend rows IGU does not list.
- 46 IGU no-IMO orderbook rows in 19 clusters — every cluster has backend rows; no gap found.

## Decisions / follow-ups (added to the sep-17-pass worklist §1b)

### 1. The 18 dropped vessels — all scrapped steam tonnage (shipvault lead)

| row | IMO | backend name | shipvault | fate date | inclusion rule |
|---|---|---|---|---|---|
| 64 | 9213416 | Trader III | scrapped | 2025-03-13 | before Dec 2025 → out |
| 84 | 9265500 | Dukhan | `UKHAN`, owner BREAKERS (status still "active") | 2025-06-17 | before Dec 2025 → out |
| 44 | 9155145 | Hyundai Technopia | scrapped (`TECHNO`) | 2025-07-10 | out |
| 46 | 9176008 | HL Ras Laffan | scrapped (`RASI`) | 2025-07-13 | out |
| 47 | 9176010 | HL Sur | scrapped (`SUR`) | 2025-07-15 | out |
| 48 | 9179581 | Hyundai Aquapia | scrapped (`APIA`) | 2025-07-20 | out |
| 49 | 9155157 | Hyundai Cosmopia | scrapped (`COSMO`) | 2025-08-22 | out |
| 16 | 9038440 | Al Khaznah | scrapped (`KHAZA`) | 2025-09-09 | out |
| 23 | 9038452 | Ghasha | scrapped (`SHAAN`) | 2025-09-10 | out |
| 63 | 9238038 | Trader II | scrapped (`RADE`) | 2025-09-21 | out |
| 54 | 9200316 | LNG Jamal | scrapped | 2025-10-17 | out |
| 77 | 9236420 | Seapeak Catalunya | scrapped (`K ASIA`) | 2026-01-04 | stays |
| 98 | 9259276 | Seapeak Madrid | scrapped (`TEAK`) | 2026-02-17 | stays |
| 26 | 9030826 | Puteri Nilam | scrapped (`NILA`) | 2026-02-21 | stays |
| 25 | 9030814 | Puteri Delima | scrapped (`LIMA`) | 2026-03-08 | stays |
| 94 | 9248502 | Puteri Firus Satu | scrapped | 2026-06-30 | stays |
| 95 | 9245031 | Puteri Zamrud Satu | scrapped (`ZAMRUD`) | 2026-06-30 | stays |
| 115 | 9261205 | Puteri Mutiara Satu | sold for scrap | — | stays (not yet broken up) |

`docs/inclusion_criteria.md` excludes vessels decommissioned before December 2025, so by the
shipvault dates **11 rows leave the tracker and 7 stay**. Two things to decide:
- the 7 that stay have no honest Status — the vocabulary is active / on order / proposed.
  Add a `scrapped` (or `decommissioned`) value, or leave them `active` with a note?
- the fate dates are single-source. Each removal / status change needs a verified ref (§3.8)
  before it goes into a fix batch — not done here.

IGU itself is a second signal only in the negative (absence from the 2026 table); note that it
dropped the six scrapped in Jan–Jun 2026 too, so its "end-2025" cut-off is not strict.

### 2. 22 rows `active` in the backend that IGU still had on order at end-2025

21 of them carry backend Delivery year **2025**, which cannot be right if IGU is.

- **Delivered in 2026 per shipvault → Delivery year 2025 → 2026** (13): rows 787 BW Nivalis
  (2026-02-03), 790 Clean Sirocco (01-02), 752 Danuta Siedzikowna-Inka (04-14), 768 Dana (01-16),
  774 Al Fat'h (02-10), 753 Rotmistrz Witold Pilecki (04-24), 754 Maran Gas Antiparos (01-30),
  771 Celsius Greenland (01-07), 786 BW Borealis (03-03), 769 Al Na'amah (04-22), 770 Umm Al Zubar
  (05-18), 815 Sea Navigator (01-31), 813 Sea Creation (06-03); row 907 Celsius Georgetown
  (04-24) already says 2026 — no change.
- **Still on order per shipvault → Status is wrong, not just the year**: row 814 Sea Energy
  (IGU 2026), and the six Arctic LNG 2 hulls, IGU 2027 — rows 797 Ilya Mechnikov, 799 Lev Landau,
  805 Nikolay Basov, 812 Pyotr Kapitsa, 823 Zhores Alferov, 806 Nikolay Semenov. (Sanctioned
  Zvezda / Samsung hulls — same family as the manual-review rows in batch 1.)
- Row 800 LNG Ping Hu (IMO 1040447): shipvault has no record — ties to the stream 0 item that
  its Status ref no longer says "Delivered".
- Row 752 also ties to the stream 0 item (its marinetraffic.org page).

### 3. Row 929 Alexey Kosygin (IMO 9904546)
Backend on order / 2026 / Zvezda / DFDE; IGU 2026 lists it in the **fleet**, delivered 2025,
builder `Samsung`, TFDE. Shipvault: `SANCTIONED`, delivered 2025-12-24. Not in any pending batch
(batch 1 left the sanctioned hulls' Status untouched).

### 4. Load corruption IGU exposes — rows 451, 499, 500, 501, 509
Energy Liberty / Glory / Innovator / Universe and LNG Jia Xing: Cargo type `self-supporting
prismatic` (correct), but Vessel type `Supporting` and Propulsion `prismatic conventional DFDE`
(509: `prismatic small-scale DFDE`) — the wrapped "Self-Supporting Prismatic" cell bled into the
next two columns in the original load. IGU: Conventional / DFDE for 451, 499, 500, 501;
**Small-scale** / DFDE for 509 (45,000 cbm → out of scope?). Fix = Vessel type `conventional`
(509 `small-scale`), Propulsion `DFDE`.

`qc_backend.py` cannot catch this because the three bogus strings were seeded **into the
controlled vocabulary** (`scripts/lookups.py`, `data/controlled_vocab.md`: `Supporting`,
`prismatic conventional DFDE`, `prismatic small-scale DFDE`). Follow-up: remove them from the
vocab with the fix batch, and add a vocab-membership check on Cargo / Vessel / Propulsion type.

### 5. Vessel-type changes
- Row 81: `conventional` → IGU **FSU** (changed this edition) — FSUs are out of scope.
- Row 270: `conventional` vs IGU FSRU in both editions.
- Row 61 Puteri Delima Satu (IMO 9211872): in neither IGU edition; shipvault active. (The FSU
  conversion question from the Rule-F batch is separate and still open.)

### 6. Renames / sales IGU picked up this edition (each needs a ref)
Row 190 Alto Acrux → LNGT Karadeniz · 124 CCH LNG → LNG Soars (owner: backend Pacific Gas, IGU
TMS Cardiff Gas) · 57 East Energy → Arctic Vostok · 69 Energy Frontier → Arunika Jaya · 70 Golar
Arctic → SC Serenity (owner → Soechi Lines) · 364 Golar Tundra → Italis LNG · 365 Kool Baltic →
Cool Baltic · 91 LNG River Orashi → Gas Garuda · 73 Metagas Everest → Arctic Metagas · 167 Methane
Heather Sally → Shandong Redwood · 742 North Mountain → Voskhod · 114 Pioneer Spirit → Arctic
Pioneer · 21 Puteri Intan → American Energy · 563 SCF La Perouse → La Perouse · 62 Seapeak
Hispania → Seapeak Jupiter · 144 Stena Blue Sky → Blue Dragon I · 29 / 39 / 20 / 11 Karadeniz
powership restylings · 818 / 819 owner BW → Venture Global.

Backend name defects (IGU unchanged, backend truncated or mis-spelt): row 461 `Hoegh` (Hoegh
Esperanza), 88 `Hongkong` (Hongkong Energy), 294 `BW ENN Crystal` (… Sky), 446 `Cesi` (Cesi
Lianyungang), 790 `Clean Srocco` (Sirocco), 624 `Vivirt City LNG` (IGU now Vivit), 584 / 531
spelling. Rows 780 / 781 / 915 / 916: IGU says **Greenergy**, agreeing with shipvault + AIS
against the backend's `Greenenergy` (existing worklist item — now three sources).

Pending batch 1 spellings to check against IGU: row 910 `Mihzem` vs IGU `Mizhem`; row 873
`Minerva Eleonora` vs IGU `Minerva Eleonara`. New name not in any batch: row 909 Hull H1799A →
`Fath Al Khair`.

### 7. Other value changes
- Row 844 capacity 200,000 → IGU 174,000 (Venture Iberia); propulsion ME-GI → ME-GA (also 843).
- Row 503 cargo type spherical → IGU Membrane (changed this edition).
- Builder: row 268 Samsung → HD Hyundai, 567 Hanwha → HD Hyundai, 941 HD Hyundai Samho → Samsung.
- Propulsion ME-GA ↔ X-DF flips: rows 785, 789, 792, 788, 761, 765, 936, 941 (IGU correcting
  itself; verify before touching).
- Delivery year: 120 `igu_changed` — 38 agree with batch 1, 21 are the active rows in item 2, and
  **61 on-order diffs are not in any batch** (IGU earlier by 1–3 years on 37, later by 1–2 on 24;
  one of them `backend_differs`).
  IGU's schedule is nine months old; batch 1's shipvault-based roll-forward is the better source,
  so these are a reading list, not corrections.

### 8. Candidates and non-candidates
- **Add:** IMO 9627497 `Maran Gas Efessos` — Maran Gas Maritime, Hanwha Ocean (DSME), 159,800 cbm,
  conventional, delivered 2014-06-12; in both IGU editions, never in the backend. Discovery-style
  row for the next batch.
- Out of scope: 9696266 Hai Yang Shi You 301 (bunkering vessel).
- 9315379 `Athlos` left the IGU orderbook undelivered — shipvault shows that IMO as a 2006 MSC
  container ship, i.e. an IGU IMO typo in 2025. Not in the backend; ignore.
- Backend `active` rows IGU has never listed (all Clarkson-sourced, all active on shipvault):
  rows 6 Bering Energy, 7 Gulf Energy (both 1970s), 61 Puteri Delima Satu, 487 SK Serenity,
  488 SK Spica. No action.

### 9. IGU prints three IMOs twice
9961518 (row 912), 9961520 (row 913), 1023633 (row 914): once as MOL `H1884A`–`H1886A` and once as
CNOOC `Greenergy Wind` / `Cloud` / `River`. Same ships; the backend owner on rows 915 / 916 / 919
(MOL vs IGU CNOOC/CMES/NYK JV) is the related question.

### 10. IGU rows without an IMO
19 clusters / 46 rows; all have backend counterparts (14 strong, 5 weak — ADNOC × Hanwha rows
1025–1028, Evalend 1054 / 1059, Hanwha Shipping, Hyundai Glovis, MOL 1084). BW Hulls 8340 / 8341
(rows 1089 / 1090) already carry IMOs IGU lacks. No new vessels here.

## Tooling added with this batch

`scripts/igu_fleet.py`, `scripts/igu_reconcile.py` (`--pending`, `--fetch-leads`),
`build_workbook.py --mode igu`, `docs/sops/igu_reconciliation.md`, tests. Dedupe sweep
(`dedupe_check.py`): unchanged — no HIGH, the known Knutsen × Hanwha / Hanwha Philly MED pairs.
