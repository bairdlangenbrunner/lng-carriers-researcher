# sep-17-pass — summary (2026-09-17)

Fresh pull 2026-09-17 ~01:15 ET: 1,220 rows (822 active / 364 on order / 34 proposed).
Nothing was written to the Google Sheet. Everything below is a reviewed-candidate batch with
`digest.md`, `decisions.csv` and offset-proof apply artifacts already generated — work through
them with the Apply SOP (`docs/sops/apply.md`): edit the `hold` rows in `decisions.csv`,
re-run `python scripts/apply_batch.py --batch <dir>`, apply, then
`python scripts/verify_apply.py --batch <dir> --pull`.

**What to do next, in order: the "Do next" section at the top of
`docs/plans/2026-09-17_sep-17-pass_worklist.md`** — that file is the tick-off version of
everything still open (sheet prep, decisions, apply, stream 0, remaining research) and is kept
current; this one is the narrative. Re-pull 2026-09-17 18:00 ET: 1,217 rows (822 active / 364 on
order / 31 proposed) — no batch applied; Baird deleted the three Woodside duplicate rows by hand
and three rows moved, so live rows ≥ 1130 shifted (row numbers below are the new ones).

## Batches, in the order to apply them

| # | batch | what | proposals |
|---|---|---|---|
| 1 | `2026-09-17_0421ET_fix_delivery_rollforward` | on-order rows vs shipvault (AIS cross-check: vesselfinder, then marinetraffic.org): 63 → `active`, 26 delivery years corrected, 19 rolled forward, 116 names | 224 cells / 151 rows — 186 accept, 38 hold |
| 2 | `2026-09-17_0458ET_fix_delivery_confirmed` | press-confirmed deliveries shipvault lags on: live rows 887 (→ active, `Al Nigyan`) and 924 (→ active) | 3 cells, all hold (Y) |
| 3 | `2026-09-17_0431ET_discovery_since_jun_2026` | new orders since Jun 2026: 12 vessels / 5 clusters | 7 accept, 5 hold, 10 backend flags |
| 4 | `2026-09-17_0511ET_data_fill_on_order` | blanks on on-order rows + whole-backend derivables | 1,003 cells / 483 rows — 589 accept, 414 hold (the 48 order-total Prices, DF §5a, accepted 2026-09-17) |
| 5 | `2026-09-17_0505ET_ref_fill_rule_f` | Rule-F orphan `[ref]`s | 8 refs (hold), 11 negatives |
| 6 | `2026-09-17_1114ET_shipvault_companion_refs` | existing shipvault `[ref]`s that render blank: unit-record URL appended as a second ref (values untouched) | 175 cells / 27 rows — all accept |
| 7 | `2026-09-17_1458ET_igu_reconciliation_igu2026` | whole backend vs the IGU World LNG Report 2026 (fleet at end-2025; 2025 edition as the baseline the backend was loaded from) — IMO-keyed, IG rev 1 | comparison only, never applied: 1,054 matched, 188 with a field diff, 18 dropped, 47 Status disagreements (24 already in batch 1), 1 candidate |
| 8 | `2026-09-17_1654ET_fix_igu2026_sourced` | follow-up to 7: what IGU 2026 prints, as proposals citing the report PDF as sole ref (interim rule, IG §5.4) — blank Vessel / Cargo type, renames, delivery years, propulsion, load corruption on rows 451 / 499–501 / 509 | 468 cells / 328 rows — 443 accept, 24 hold, 1 reject (row 61 Vessel type ref — batch 9 proposes `FSU`); 8 manual-review values (the 24 `QC-max` ones became batch 11) |
| 9 | `2026-09-17_1702ET_fix_scrapped_status` | follow-up to 7: the 18 dropped rows → Status `scrapped` (new vocab value; rows are never deleted), live row 61 Puteri Delima Satu → Vessel type `FSU` | 19 cells / 19 rows — all accept (G) |
| 10 | `2026-09-17_1737ET_fix_other_names_former` | new rule (RF §4.16): the former Name of every proposed rename in 1, 2 and 8 appended to `Other names` (hull placeholders included; spelling / truncation fixes and row 942's wrong-vessel name excluded) | 131 cells / 131 rows — 95 accept, 36 hold (29 with no ref for the former name, 7 whose Name line is itself held) |
| 11 | `2026-09-17_1809ET_fix_qcmax_vessel_type` | `qc-max` joined the Vessel type vocabulary (Baird 2026-09-17): the 24 × 271,000 cbm QatarEnergy ships, IGU 2026 PDF as ref | 24 cells / 24 rows — all accept (G) |
| 12 | `2026-09-17_1810ET_fix_price_full_usd` | Price is always full US dollars (Baird 2026-09-17): the 29 legacy `$m` rows × 1,000,000, currency → `USD`, refs kept (`preserve_ref`) | 58 cells / 29 rows — all accept |

Order: 1, 2, 3, 4, 5, 6, 8, 9, 11, 12, then 10 last (it rides on the Name lines of 1, 2 and 8, and
each of its lines is decided with its Name line). **Apply every batch by `apply_patch.csv`**: the
batches share hundreds of rows, and `apply_rows.csv` full rows are a snapshot that would revert
the batch applied before (AP §2a; applier settings per batch in the worklist §2). Before batch 9,
add `scrapped` to the sheet's Status dropdown; before batch 12, give the Price column a plain
number format. After 3 and 9, re-export the map fleet
(`../lng-carriers-map/tools/export_fleet.py`) — C3 is an FSRU, row 61 becomes an FSU.

Discovery candidates: Samsung HI × Dynagas 4 × 200,000 cbm (14-Sep-2026, Y); HD Hyundai HI ×
Tsakos (01-Jul-2026, $254M, G); HD Hyundai HI FSRU, owner undisclosed (30-Jun-2026, Y);
Jiangnan × ADNOC L&S H2706–H2709 (10-Jul-2026, G); Jiangnan H2858/H2859 (25-Aug-2026, G;
press says delivery 2029, shipvault 2030).

## Decisions waiting for you

1. **Proposed bucket** (`…discovery…/proposed_review.json`): the three Woodside placeholders
   that duplicated the Seapeak on-order rows are **done** — Baird deleted them 2026-09-17 and moved
   the names to `Other names` on the Seapeak rows (now live 1162–1164); the other Woodside
   rows (1204–1216), Equinor 4 (1183) and all 17 Mozambique LNG slots (1184–1200) stay `proposed`
   (Mozambique confirmation deadline was pushed to Sep 2026 — re-check next month). Also the
   Mozambique owner/yard split flagged in the discovery batch.
2. **Likely duplicates** (dedupe + agent): Hanwha Philly live rows 1083 ↔ 1085 and 1203 ↔ 1086
   (1203 was 1132 before the 2026-09-17 evening sheet edit).
3. **Vessel type / Cargo type rule — decided 2026-09-17: cite the IGU 2026 report** (IG §5.4;
   batch 8). Still open, and you asked to be reminded: should IGU-2026-only cells get a second
   ref at the ref-validation step?
4. **Price convention — decided 2026-09-17: always full US dollars + `USD`**; batch 12
   (`1810ET_fix_price_full_usd`) converts the 29 `$m` rows. Shipvault carries contract prices too — unused tonight (single-source, unverifiable).
5. **`Greenenergy …` names** look wrong against both shipvault and AIS (`Greenergy`).
6. **Manual-review rows**: `…rollforward/manual_review.json` (54) and
   `…delivery_confirmed/manual_review.json` (24 still unconfirmed) — mostly ships AIS-live while
   shipvault says on order; plus the sanctioned Zvezda / Arctic LNG 2 hulls (status untouched).
7. **Backend flags from discovery**: BW LNG live rows 1165/1166 capacity (177,000), row 1159
   price, COSCO hulls.
8. **Possible mis-citations / value conflicts** found by the data-fill agents — full list in
   `…data_fill_on_order/notes.md` (live rows 1179–1182, row_ids 1162/1163, 1212/1213, 1218,
   1207/1208, 197, 375, 255/256, 318/319, 515/516; Samsung × CMES and Jiangnan × Taiping capacity).
9. **MISC hulls H2019A–H2023A** on shipvault have no citable press — next discovery run.
10. **IGU 2026 intercomparison (batch 7)** — full list in the worklist §1b and the batch
    `notes.md`. The ones that need you:
    - **A `scrapped` Status value — decided 2026-09-17, batch 9.** `scrapped` is now a Status
      value and **rows are never deleted**: all 18 rows IGU dropped (scrapped steam tonnage)
      move to `scrapped`, including the 11 scrapped before Dec 2025 that the inclusion rule
      would have removed. Row 25 is IMO 9030814 Puteri Delima, renamed `Lima` for the scrap
      voyage — the vessel that prompted this pass. Row 61 Puteri Delima Satu → `FSU`, same batch.
    - **13 `active` rows with Delivery year 2025 that delivered in 2026** (787, 790, 752, 768,
      774, 753, 754, 771, 786, 769, 770, 815, 813); **7 `active` rows still on order**
      (814 + Arctic LNG 2 hulls 797, 799, 805, 812, 823, 806); row 929 Alexey Kosygin
      delivered 2025-12-24 (sanctioned) but on order in the backend.
    - **Load corruption** on rows 451, 499, 500, 501, 509 (Vessel type `Supporting`) — and the
      same bogus strings sit in the controlled vocab, which is why QC never flagged them.
    - Vessel type row 81 → FSU (out of scope), row 270 → FSRU; ~20 renames; `Greenergy`
      confirmed by a third source; batch 1 spellings on rows 910 / 873 to check before
      applying; candidate `Maran Gas Efessos` (IMO 9627497).
    Most of it is now proposed: batch 8 carries what IGU 2026 prints (report PDF as sole ref),
    batch 9 the scrapped rows, batch 11 `qc-max`. Left: batch 8's 24 holds and 8 owner / builder
    names, rows 873 / 910 spellings, and `Maran Gas Efessos` (next discovery batch).

## Paused / not done

- **Stream 0 (citation rot-sweep fix batch, `citation_qc.py --corroborate`)** is paused as
  asked; `work/citation_qc.csv` state is untouched and resumable.
- Data-fill research covered on-order rows only; active-row blanks were not researched.
- Coverage is thinner than a normal run: the session WebSearch budget was exhausted mid-way
  (later clusters used site searches via `scripts/fetch.py`), vesselfinder firewalled this IP
  part-way (cited nowhere), TradeWinds/Upstream paywalls block many contract dates/prices.
- **AIS cross-check gap.** vesselfinder never answered for 176 on-order IMOs (live rows 973–1181).
  All 176 were re-checked on marinetraffic.org via `scripts/sweep.py` in two paced runs (176/176
  answered) and folded into batch 1: 37 names Y → G with a second ref, 6 Status / Delivery-year
  cells Y → G (cross-check only), 10 new names (Y, marinetraffic.org only), 9 more manual-review
  rows. The second run (81 placeholders due 2028+) was expected to be empty but found the
  QatarEnergy series already named: live rows 1017–1024, 1031–1037, 1043, 1057, 1058 (Y → G), 1039
  `Libsayer` (new, hold), and 1017 / 1033 showing an MMSI early (manual review, low priority).

## Tooling changes (all with tests; 194 pass that morning, 291 by evening, 324 with the IGU tooling, 327 with `scrapped`)

- `scripts/apply_batch.py` / `batch_digest.py`: **fix-mode** batches now get digests and apply
  artifacts (fix refs *replace* the paired `[ref]`; `preserve_ref` cells touch the value only).
- `scripts/url_verifier.py` `value_variants`: `DD-Mon-YYYY` dates; Status `active` ↔ past-tense
  delivery wording; Status `on order` ↔ order wording; hull yard tag optional, untagged
  Chinese-yard hulls (`Hull H2706`); `_title_hit` no longer reads "$500 million" as HTTP 500.
- Added later the same day: `scripts/sweep.py` (paced, circuit-broken bulk fetch — after the
  vesselfinder IP ban), `scripts/ais_static.py` (aisstream cross-check, lead only),
  `scripts/shipvault_api_refs.py` (companion refs, RF rev 21), order-total Prices in
  `merge_fills.py` (DF rev 3 §5a, RF rev 22).
- IGU reconciliation (IG rev 1): `scripts/igu_fleet.py` (word-coordinate extractor — the 2026
  edition prints two tables per landscape spread and adds Age / Vessel Type columns, so the
  2025 column positions do not carry over), `scripts/igu_reconcile.py` (IMO join, edition
  diff, paced shipvault leads) and `build_workbook.py --mode igu`.
- `scrapped` Status (batch 9): `CONTROLLED_VOCAB["Status"]` in `lookups.py`, a Status shape
  check in `qc_backend.py`, and `value_variants("scrapped")` ↔ demolition wording ("sold for
  recycling", "cash buyers", "beached" …) in `url_verifier.py`; the IGU dropped bucket now
  suggests Status → `scrapped`, never removal (IG rev 2).
- Follow-ups not done: controlled vocab carries three strings seeded from corrupted rows, and
  `qc_backend.py` has no vocab-membership check on Cargo / Vessel / Propulsion type; Status `active` still passes on a bare boilerplate "active";
  shipvault data quality (IMO typos failing the check digit, wrong owner tags) — treat
  shipvault as Y/single-source, never for owners.

## Final checks

`qc_backend.py`: 7 LOW only (6 name-builder-drift, 1 name-ordinal-gap), no HIGH/MED.
`dedupe_check.py`: no HIGH; MED groups are placeholder↔identified pairs — the Knutsen × Hanwha
ones (live 1142/1143 vs 1158/1169) are different orders (Dec-2025 vs May-2026) and get
distinct hull numbers from batch 4; the Hanwha Philly ones are item 2 above.
