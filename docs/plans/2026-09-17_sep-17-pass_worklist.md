# sep-17-pass — worklist (written 2026-09-17 evening; last updated 2026-09-21 17:10 ET)

Working checklist for getting the sep-17-pass into the backend and closing out the
research pass. Tick items as you go. Detail behind every item is in
`docs/plans/2026-09-17_sep-17-pass_summary.md` (apply order + decisions) and
`docs/plans/2026-09-16_full_research_pass.md` (plan of record, stream 0 results).

## Do next — in order

The short version; every step points at the section with the detail. Steps 1–3 are yours, in the
sheet or in a `decisions.csv`; nothing here needs new research before the apply.

1. **Prep the sheet** (three settings, before any apply):
   - [x] Status dropdown: `scrapped` added (Baird, 2026-09-17 ~18:45 ET).
   - [ ] Price column: set a plain number format, no decimals. It displays `2.53E+08`, and a
         pull of that display loses digits — batch 12 writes full-dollar values into it.
   - [ ] Vessel type dropdown: it offers `supporting` (load corruption, §5) and lacks
         `small-scale` / `mid-scale`, which the vocabulary and the backend use. Remove the first
         once batch 8 has fixed rows 451 / 499–501 / 509; add the other two.
2. **Decide the 538 holds** (§1, §1c) in the review app (`review_app/README.md`; Apply SOP rev 6):
   `python scripts/pull_backend.py`, then
   `python review_app/server.py --batches $(python -c "import json; print(' '.join('batches/'+d for d in json.load(open('batches/2026-09-17_1017ET_sep-17-pass_combined/review_batches.json'))))")`
   (the queue opens on the holds; the manifest lists all thirteen reviewable batches (14 added 2026-09-21), 9 and 12 marked
   applied — grayed, still undoable). The dataset was rebuilt over all twelve and the server restarted
   2026-09-21 16:34 ET; press `↻ sync backend` after any batch rebuild or sheet edit. Then re-run
   `python scripts/apply_batch.py --batch batches/<dir>` for each batch the session summary lists.
   Editing `decisions.csv` by hand, or the combined workbook's `all_proposals` tab, still works. By batch:
   1 → 40, 2 → 3, 3 → 5, **4 → 414**, 5 → 6, 6 → 1, 8 → 35, 10 → 34; batches 9, 11, 12, 13 have none.
   **Log ↔ csv mismatches (2026-09-21 audit):** batch 8 `Name` on row_ids 721 and 811 (live 11 and 20; and their batch 10
   `Other names` lines) read `accept` in `decisions.csv` (set by later session commits at Baird's request)
   while the latest `review_log.jsonl` record is Baird's `hold` — the app shows them undecided; the csv is
   what applies. Re-clicking accept in the app aligns the log. **Linked pairs out of step:** 12 batch 10
   `Other names` lines are held while the partner Name line is accepted — row_ids 6, 136, 138, 140, 142,
   509, 510, 517 (batch 1 names; live 827, 1031, 1032, 1034, 1035, 1080, 1008, 935), 1062 (live 144),
   924 (live 742) are G after the 2026-09-21 ref pass and only hold from the pre-fill; 263 (live 909) and
   686 (live 88) are still Y. Batch 5's three Hull number refs (row_ids 121, 226, 230; live 771, 775, 776)
   were G since 2026-09-21 and held only from the pre-fill — **pushed 2026-09-21 18:29 ET** with the
   other held ref-only lines (Baird: push every "value unchanged; adds N refs" hold).
   Batch 4's 414 are all Y (single-source): 76 Price + 76 Price currency, 71 Operator/charterer,
   68 Contract date, 32 Cargo type, 20 IMO, 19 Hull number, 16 Capacity + 16 units, 10 Propulsion,
   9 Vessel type, 1 Shipowner. A blanket call ("accept Y contract dates", "leave Y prices") is
   fine — say it and the flips get scripted. Leaving a hold as a hold is also a decision: it just
   does not get applied.
3. **Decisions that are not a hold line** (§1, §1b, §1c): Hanwha Philly duplicates 1083 ↔ 1085 and
   1203 ↔ 1086 (delete by hand if you agree — duplicates are yours to remove); the proposed
   bucket; batch 8's 8 owner / builder names; and the manual-review lists of batches 1 and 2.
4. **Apply + verify, in this order** (§2): 1, 2, 3, 4, 5, 6, 8, **9 (done)**, 11, 12, then **10 last**. **Every
   batch goes in by `apply_patch.csv`** (`tools/apply_patch.gs`, DRY_RUN first) — the batches
   share hundreds of rows and a full-row paste would revert the batch before it (AP §2a). Set
   `OVERWRITE_NONBLANK` per batch (table in §2) or a fix batch lands nothing. After each:
   `python scripts/verify_apply.py --batch batches/<dir> --pull`.
5. **Close out** (§2 end): review HIGH / MED in each `dedupe_report.csv`; final re-pull +
   `qc_backend.py` + `dedupe_check.py`; re-export the map fleet (batch 3 adds an FSRU, batch 9
   makes row 61 an FSU); drop `$m` and the seeded-corruption strings from the vocabulary (§5);
   republish Rob's report (version 4 predates batches 7–12) — ask for it.
6. **Then, not before**: stream 0 rot sweep (§3, paused) and the open research (§4).

## Where things stand

- **Bulk push 2026-09-21 17:04 ET (Claude, at Baird's directive "for anything with *batch suggests
  accept* and ref(s) verified, accept and make the changes directly in the sheet"):** every undecided
  line whose pre-fill was `accept` and whose every source read `✓ verified` in the app was clicked
  accept through the running server (`via: bulk:batch-suggests-accept+refs-verified`, 1,268 lines:
  1,173 verified + 95 companion `Price currency` / `Delivery delayed` / `Capacity units` lines decided
  with their primary; a line whose linked partner is held was left undecided, both-or-neither), then
  **push accepted** wrote **2,268 cells / 440 rows** and verified all of them (`push_log.jsonl` in
  batches 1, 4, 6, 8, 10, 11, 13; 0 mismatches). Written: batch 8 871 cells, 4 486, 1 410, 10 256,
  6 171, 11 48, 13 26. QC after: 8 LOW only; dedupe: the two pre-existing MED pairs (live 779 vs 943 /
  1217). Left undecided on purpose: row 942 `Puteri Sarawak → Puteri Perlis` (batch 1; a real rename
  with no `Other names` companion — RF §4.16, decide by hand), the 15 Names / 9 Vessel types whose
  partner line is held, 4 Prices with an unchecked ref, and every line with no source, a `read by
  hand` or `not checked` source (292 `Shipowner country/area` facts-table fills, batch 13's 28
  `preserve_ref` hull restylings, yard-location cells). Discovery new rows stay by hand.
- **Reconciliation 2026-09-21 21:05 ET (Claude, at Baird's directive):** every batch re-finalised
  (`apply_batch.py` on the fresh pull — seven had `apply.json` older than their `decisions.csv`;
  no decision changed) and verified (`verify_apply.py`, which now compares numerically — the
  sheet renders a Price as `165000000.00`, which had read as 98 false mismatches). Fully in the
  backend, `applied: true` in `review_batches.json`: **1, 2, 5, 6, 9, 10, 11, 12, 15**. Still open
  (accepted lines not in the backend, all `not checked` / `read by hand` sources the bulk push
  skipped, or hand work): **3** (7 new rows), **4** (20 cells: Price + currency on 4 rows,
  yard-location cells on live 1116/1117, Operator/charterer on 2 rows), **8** (12 cells: 9 Vessel
  types, Cargo type / Capacity / units on live 929 / 1004 — the "batch 4 proposes the same value"
  duplicates; plus live 915/916 `Name [ref]`: the spelling fix landed but the IGU PDF ref did not —
  the cells still carry shipvault + companion), **13** (28 `preserve_ref` hull restylings), **14**
  (live 1080 `Other names` append). Batch 6's two companion lines that later pushes superseded were
  set to `reject` (live 61 `Shipowner country/area [ref]` — shipvault is never a country ref; live
  814 `Status [ref]` — batch 8 moved Status to `on order` with the IGU PDF as sole ref). Review app
  restarted on all 14 batches: 1,797 lines `in the backend`, incl. all 329 batch-4 and 53 batch-15
  `Shipowner country/area` lines; the 2 batch-15 holds (live 953/954) read `value_in_backend` because
  Baird's hand-entered ref differs from the proposal — reject or accept them in the app to close.
  Dedupe reports on the re-verified batches are the known sister-ship MED groups (placeholder ↔
  identified on builder+owner+capacity+delivery), no HIGH.
- **The shipowner-country ref batch is applied** (`2026-09-21_2003ET_fix_shipowner_country_refs`,
  2026-09-21 20:18 ET, by Claude at Baird's directive, through the Sheets API): 53 cells / 53 rows,
  every one a `Shipowner country/area [ref]` replacing a shipvault URL that never stated the
  country; the values already matched, so none was rewritten. `verify_apply.py`: 106 landed,
  0 mismatch; QC clean, dedupe 10 LOW sister-ship pairs. Its two holds (live 953/954, Hanwha) were
  settled by Baird in the sheet: Shipowner `Hanwha Ocean`, South Korea, hanwha.com ref. The **292**
  `Shipowner country/area` fills in batch 4 followed at 20:40 ET on Baird's "yes push them now"
  (584 cells, after re-pointing the batch's stale table refs and re-gating; all landed).
- **Batch 9 is applied** (2026-09-17 19:00 ET, by Claude at Baird's request, through the Sheets
  API — 38 cells / 19 rows, `verify_apply.py`: 38 landed, 0 mismatch; QC after: 8 LOW, no
  HIGH/MED). **Batch 12 is applied** (2026-09-18, 58 cells; verify shows `.00` display-format
  mismatches only). **Batch 5 is partly applied**: its 2 accepted Capacity refs (row_ids 415, 663)
  landed 2026-09-18 (`verify_report.csv`, 2 landed) — the other 6 are still held, so the manifest marks
  it `applied: false`. Batch 6 row_id 6's IMO ref and the five `Greenergy` names (live 780, 781, 912,
  914, 915) are also in the sheet by hand edit. Nothing else has been applied. Baird edited the sheet by hand on 2026-09-17
  evening (~18:00 ET): the three Woodside duplicates were deleted (their names moved to
  `Other names` on the Seapeak rows) and `Hull H1955A` / `Hull H1957A` / `Hanwha Philly 2` moved
  from rows 1130–1132 to 1201–1203. Now 1,217 rows (822 active / 364 on order / 31 proposed).
  **Live rows ≥ 1130 shifted** (old 1133–1203 and old 1207+ are each −3); this file is
  renumbered to the new pull, the per-batch `digest.md` / `notes.md` are not — apply artifacts
  are keyed by row_id, so nothing about the apply changes.
- The research is done. Twelve batches are merged to main (PRs #11–#25); every one that gets
  applied (all but 7) has `digest.md`, `decisions.csv` and offset-proof apply artifacts.
- Combined workbook (name = build date + ET time; newest file in the dir is current):
  `batches/2026-09-17_1017ET_sep-17-pass_combined/lng_carrier_sep-17-pass_results_2026-09-17_1810ET.xlsx`
  — 23 sheets, 2,125 proposals (1,596 accept / 528 hold / 1 reject), keyed by live sheet row; the
  `igu_findings` tab carries the batch 7 comparison (291 lines, leads not proposals).
- Report shared with Rob is at version 4 and **predates batches 7–12** (no IGU section, no
  scrapped rows, no former names; not republished): https://claude.ai/artifact/C1eEJt5CKeqauvfGGg8Ph3
- A seventh batch was added in the afternoon: the **IGU World LNG Report 2026
  intercomparison** (`1458ET_igu_reconciliation_igu2026`). It is a comparison artifact — it
  proposes nothing and is never applied — but it opens the decisions in §1b.
- Two fix batches followed from it. **Batch 8** (`1654ET_fix_igu2026_sourced`, §1c): what IGU
  2026 prints, promoted to proposals citing the report PDF. **Batch 9**
  (`1702ET_fix_scrapped_status`): the new Status value `scrapped` on the 18 rows IGU dropped,
  and row 61 → Vessel type `FSU`. Rule set with it: **a vessel that leaves service is never
  deleted from the backend** (duplicates are a different matter — see §1).
- **Batch 10** (`1737ET_fix_other_names_former`) applies the evening's new rule (RF §4.16): **a
  proposed Name change also proposes the former Name as an addition to `Other names`.** 131 of
  the 150 Name changes in batches 1, 2 and 8 get one (95 accept / 36 hold); 19 do not — spelling /
  truncation fixes and row 942's wrong-vessel name (list in the batch `notes.md`; overrule with
  `other_names.py --include`). Future fix batches run `other_names.py --batch` before the build.
  Row 1080's line is rejected there and replaced by **batch 14** (`2026-09-21_1740ET_fix_review_suggestions`):
  `Dalian No 1 G175K-12; Youyi Yongshi`, the AIS-transmitted name added per Baird's review-app suggestion (RF §4.16 rev 27).
- **Batches 11 and 12** come from Baird's evening rulings: `qc-max` is a Vessel type value
  (batch 11, the 24 QatarEnergy 271,000 cbm ships) and **Price is always full US dollars + `USD`**
  (batch 12 converts the 29 `$m` rows). The 48 order-total Prices in batch 4 are accepted.
- All row numbers below are **live sheet rows** unless marked `row_id`.

## The batches (all under `batches/2026-09-17_…`)

| # | Batch dir | Contents | Accept / hold |
|---|---|---|---|
| 1 | `0421ET_fix_delivery_rollforward` | 63 rows → `active`, 26 delivery years corrected, 19 rolled forward (12 with the IGU 2026 PDF as second source, RF §4.18; each with its `Previous delivery year(s)` + `Delivery delayed` lines, RF §4.19), 116 names (262 cells / 151 rows) | 222 / 40 |
| 2 | `0458ET_fix_delivery_confirmed` | rows 887 (→ active, `Al Nigyan`) and 924 (→ active) | 0 / 3 |
| 3 | `0431ET_discovery_since_jun_2026` | 12 new vessels in 5 clusters | 7 / 5, plus 10 backend flags |
| 4 | `0511ET_data_fill_on_order` | 1,003 cells / 483 rows, incl. 48 order-total Prices (accepted 2026-09-17) | 589 / 414 |
| 5 | `0505ET_ref_fill_rule_f` | 8 refs, 11 documented negatives; 3 hull refs Y→G with IGU PDFs 2026-09-21; **2 refs applied 2026-09-18, the other 6 pushed 2026-09-21** — batch fully in, `verify_report.csv` clean | 8 / 0 |
| 6 | `1114ET_shipvault_companion_refs` | unit-record URL appended as second ref on 175 cells / 27 rows (values untouched); 172 pushed 2026-09-21 17:04 ET, the held row 6 Status ref 18:29 ET; row_id 995 (live 814) Status ref is an un-clicked pre-fill accept, not yet in the sheet | 174 / 0, 1 reject |
| 7 | `1458ET_igu_reconciliation_igu2026` | whole backend vs IGU 2026 (fleet at end-2025), IGU 2025 as the previous edition: 1,054 rows matched by IMO, 188 with a field diff, 18 dropped, 47 Status disagreements (24 already in batch 1), 1 candidate | n/a — comparison only (IG rev 2) |
| 8 | `1654ET_fix_igu2026_sourced` | IGU 2026 findings promoted to proposals, the report PDF as sole ref (IG §5.4): 468 cells / 328 rows — 284 Vessel type + 78 Cargo type blanks, 33 names, 22 delivery years, 16 propulsion, load corruption on rows 451 / 499–501 / 509, 10 Vessel type Rule-F refs; + 42 delivery-history lines for the 21 years that move later (RF §4.19, 2026-09-21); the 10 Vessel type Rule-F refs **withdrawn** 2026-09-21 — IGU 2026 does not print those vessels (live rows 61, 487, 488, 994, 1118, 1169, 1179–1182; now manual-review) — 497 proposals | 462 / 35, plus 18 manual-review |
| 9 | `1702ET_fix_scrapped_status` | **APPLIED 2026-09-17** — 18 rows IGU dropped → Status `scrapped` (press + shipvault refs replace the IGU-2025 `Status [ref]`); row 61 Puteri Delima Satu → Vessel type `FSU` (two MISC documents) | 19 / 0 |
| 10 | `1737ET_fix_other_names_former` | RF §4.16: former Name of each proposed rename in 1, 2 and 8 appended to `Other names`; **rebuilt 2026-09-18** with every IGU 2026 `(ex-…)` name (RF §4.17) and yard-tagged hulls — 162 cells / 162 rows; 23 lines got IGU PDF refs 2026-09-21 (Y→G) | 128 / 34 |
| 11 | `1809ET_fix_qcmax_vessel_type` | Vessel type blank → `qc-max` on the 24 × 271,000 cbm QatarEnergy ships, IGU 2026 PDF as sole ref | 24 / 0 |
| 12 | `1810ET_fix_price_full_usd` | **APPLIED 2026-09-18** — Price `$m` → full US dollars + `USD` on 29 rows (58 cells, `preserve_ref`); `$m` dropped from the vocab. 8 Prices still cite the bare word `clarkson` (live rows 965, 1049–1053, 1083, 1203) — to re-source | 58 / 0 |
| 13 | `2005ET_fix_igu2026_hulls` | RF §4.17: IGU `Name (hull)` → 13 blank Hull numbers filled + 28 untagged hulls yard-tagged; placeholder-name matches all already in batches 1 / 8; 6 yard conflicts flagged (Samho vs Ulsan ×4, row 941 SHI vs Samho) | 41 / 0 |
| 14 | `2026-09-21_1740ET_fix_review_suggestions` | review-app suggestion hand-built into a fix batch: row 1080 `Other names` = `Dalian No 1 G175K-12; Youyi Yongshi` — the former Name plus the AIS-transmitted name (vesselfinder + the IGU PDFs; RF §4.16 rev 27). Replaces batch 10's rejected `509|Other names` line; decided with batch 1's `Friendship Venture` Name line. Added to the review manifest 2026-09-21 | 1 / 0 |

Discovery candidates in batch 3: Samsung HI × Dynagas 4 × 200,000 cbm (14-Sep-2026, Y);
HD Hyundai HI × Tsakos (01-Jul-2026, $254M, G); HD Hyundai HI FSRU, owner undisclosed
(30-Jun-2026, Y); Jiangnan × ADNOC L&S H2706–H2709 (10-Jul-2026, G); Jiangnan H2858/H2859
(25-Aug-2026, G; press says delivery 2029, shipvault 2030).

## 1. Decide the holds

Edit the `hold` rows in each batch's `decisions.csv`, then re-run
`python scripts/apply_batch.py --batch batches/<dir>`.

- [x] **Woodside duplicates — done by Baird in the sheet, 2026-09-17**: `Woodside Energy 01`–`03`
      (row_ids 1115–1117) deleted as duplicates of the Seapeak on-order rows 1162–1164, each name
      moved to that row's `Other names` with the TradeWinds ref. Ruling with it: the never-delete
      rule covers vessels that leave service (→ `scrapped`), **not duplicates** — a true duplicate
      row is removed, by hand.
- [ ] **Proposed bucket** (`…discovery…/proposed_review.json`): the other Woodside rows
      (1204–1216), Equinor (1183) and Mozambique LNG slots (1184–1200) stay `proposed`. Also the
      Mozambique owner/yard split flagged in the discovery batch.
- [ ] **Likely duplicates**: Hanwha Philly 1083 ↔ 1085 and 1203 ↔ 1086.
- [x] **Vessel type / Cargo type rule — decided 2026-09-17: cite the IGU 2026 report** (IG §5.4).
      Batch 8 does it: IGU's Vessel Type column for listed vessels, the report's size-class scheme
      for the 10 Rule-F orphans IGU does not list (rows 61, 994, 1118 on hold — open FSU question /
      no Capacity). Batch 4's Y type fills on IGU-listed rows are re-proposed there as G.
- [x] **Price convention — decided 2026-09-17: always full US dollars + `USD`.** Batch 12 converts
      the 29 `$m` rows. (Shipvault contract prices were left unused — single-source.)
- [x] **`Greenenergy …` names** — Baird fixed them in the sheet by hand (`Greenergy`, live rows 780,
      781, 912, 914, 915; confirmed in the 2026-09-21 pull).
- [ ] **Manual-review rows**: `…rollforward/manual_review.json` (54) and
      `…delivery_confirmed/manual_review.json` (24 unconfirmed). Mostly ships AIS-live while
      shipvault says on order; plus the sanctioned Zvezda / Arctic LNG 2 hulls (status
      untouched); rows 1017 / 1033 show an MMSI early (low priority).
- [ ] **Marinetraffic.org-only names on hold** in batch 1 (10, incl. row 1039 `Libsayer`).
- [ ] **Backend flags from discovery**: BW LNG rows 1165/1166 capacity (177,000), row 1159
      price, COSCO hulls.
- [ ] **Possible mis-citations / value conflicts** from the data-fill agents — full list in
      `…data_fill_on_order/notes.md` (rows 1179–1182; row_ids 1162/1163, 1212/1213, 1218,
      1207/1208, 197, 375, 255/256, 318/319, 515/516; Samsung × CMES and Jiangnan × Taiping
      capacity).
- [ ] **Batch 4 companion cells**: 92 `Price currency` / `Capacity units` cells are
      derivable but sit on `hold` because they follow their parent Price / Capacity fill —
      flip each with its parent. (`digest.md` still shows the first-run triage, 633 auto-safe;
      `decisions.csv` carries 589 accept / 414 hold.)
- [x] **48 order-total Prices** in batch 4 (total ÷ N, Y max) — **accepted 2026-09-17**, with their
      48 `Price currency` cells; `apply_batch.py` re-run.
- [x] **Batch 5**: all 8 Rule-F refs in the sheet (2 applied 2026-09-18, 6 pushed 2026-09-21 18:29 ET
      at Baird's directive — held ref-only lines, value unchanged); `verify_apply` 8 / 8 landed.

## 1b. IGU 2026 intercomparison — decisions it opens

Detail, per-row tables and shipvault leads: `batches/2026-09-17_1458ET_igu_reconciliation_igu2026/notes.md`
and the workbook beside it (11 sheets, live sheet row first). Nothing here is a proposal yet:
the IGU landing page cannot pass the §3.8c gate and the shipvault dates are single-source
leads, so each accepted item needs a verified ref and goes into a follow-up `fix` batch.

- [x] **`scrapped` Status value — decided 2026-09-17: yes, and rows are never deleted.** IGU
      dropped 18 backend `active` rows between editions; all are scrapped steam tonnage. All 18
      move to Status `scrapped`, whichever side of Dec 2025 the scrapping falls (the earlier
      "11 leave / 7 stay" split is void) — **batch 9** (`1702ET_fix_scrapped_status`), press +
      shipvault refs, all G / accept: rows 16, 23, 25, 26, 44, 46, 47, 48, 49, 54, 63, 64, 77,
      84, 94, 95, 98, 115. The scrap-voyage renames (`Lima`, `Khaza`, `Seapeak Mars` …) are not
      proposed as Name / Other names — optional follow-up. IG SOP is rev 2.
- [ ] **Delivery year 2025 → 2026 on 13 `active` rows** IGU still had on order at end-2025 and
      shipvault shows delivered Jan–Jun 2026: rows 787, 790, 752, 768, 774, 753, 754, 771,
      786, 769, 770, 815, 813. (Row 907 already says 2026.)
- [ ] **`active` but still on order per IGU and shipvault — Status is wrong**: row 814 Sea
      Energy, and the six Arctic LNG 2 hulls 797, 799, 805, 812, 823, 806 (sanctioned — same
      family as the batch 1 manual-review rows). Row 800 LNG Ping Hu: no shipvault record;
      ties to its stream 0 Status-ref item (§3). Row 752 ties to its stream 0 item too.
- [ ] **Row 929 Alexey Kosygin**: backend on order / 2026 / Zvezda / DFDE; IGU 2026 has it in
      the fleet (delivered 2025, builder Samsung, TFDE); shipvault `SANCTIONED`, delivered
      2025-12-24. In no pending batch.
- [ ] **Load corruption on rows 451, 499, 500, 501, 509**: Vessel type `Supporting`,
      Propulsion `prismatic conventional DFDE` (the wrapped "Self-Supporting Prismatic" cell
      bled right in the original load). Fix → `conventional` / `DFDE`; row 509 LNG Jia Xing is
      `small-scale` (45,000 cbm) — out of scope? See the tooling item in §5.
- [ ] **Vessel type**: row 81 → IGU **FSU** this edition (FSUs are out of scope); row 270
      `conventional` vs IGU FSRU in both editions. Row 61 Puteri Delima Satu (in neither
      IGU edition): **done — batch 9 proposes `FSU`** on MISC's release + Annual Report 2025
      (batch 8's held `conventional` ref on row 61 is **rejected**, Baird 2026-09-17).
- [ ] **~20 renames / sales IGU picked up** (rows 190, 124, 57, 69, 70, 364, 365, 91, 73, 167,
      742, 114, 21, 563, 62, 144; Karadeniz restylings 29 / 39 / 20 / 11; owner BW → Venture
      Global on 818 / 819) — each needs a ref. **Backend name defects**: rows 461 `Hoegh`,
      88 `Hongkong`, 294, 446 `Cesi`, 790 `Clean Srocco`, 624, 584, 531.
- [ ] **`Greenergy`** (item in §1): IGU agrees with shipvault and AIS — three sources now, rows
      780, 781, 915, 916.
- [ ] **Batch 1 spellings to check before applying**: row 910 `Mihzem` (IGU `Mizhem`), row 873
      `Minerva Eleonora` (IGU `Eleonara`). New name in no batch: row 909 → `Fath Al Khair`.
- [ ] **Other values**: row 844 capacity 200,000 → IGU 174,000 (propulsion ME-GI → ME-GA, also
      843); row 503 cargo type spherical → Membrane; builder on rows 268, 567, 941; ME-GA ↔
      X-DF flips on 785, 789, 792, 788, 761, 765, 936, 941 (IGU correcting itself — verify
      before touching).
- [ ] **Candidate to add**: IMO 9627497 `Maran Gas Efessos` (Maran Gas Maritime, Hanwha Ocean /
      DSME, 159,800 cbm, delivered 2014) — in both IGU editions, never in the backend. Next
      discovery batch.
- [ ] **IGU prints IMOs 9961518 / 9961520 / 1023633 twice** (MOL `H1884A`–`H1886A` and CNOOC
      `Greenergy Wind` / `Cloud` / `River`; rows 912–914) — settles into the owner question
      on rows 915 / 916 / 919.
- Reading list only, no action: 61 on-order Delivery-year diffs in no batch (IGU's schedule is
  nine months old; batch 1's shipvault roll-forward is the better source); 43
  `backend_differs` fields; 46 IGU no-IMO orderbook rows (19 clusters, all with backend
  counterparts — no gap); five `active` rows IGU never listed (6, 7, 61, 487, 488 — all
  active on shipvault).

## 1c. Batch 8 — IGU-2026-sourced fix (`1654ET_fix_igu2026_sourced`)

Decided 2026-09-17: **what IGU 2026 prints is a sufficient sole source** — no second ref is
chased (settled 2026-09-21: none needed unless Baird explicitly says otherwise). Batch 8 turns the §1b findings IGU actually prints into proposals citing the report PDF.
Covered there (so no separate research is owed): the 13 delivery years + rows 800 / 929, the load
corruption rows, the renames and backend name defects, `Greenergy` (780 / 781 / 915 / 916), row 909,
rows 843 / 844, row 503, the ME-GA ↔ X-DF flips. **Not** covered: the 18 scrapped rows (IGU's
silence is not a statement — batch 9, with demolition refs), rows 873 / 910 spellings,
`Maran Gas Efessos` (discovery).

- [ ] **24 holds** in `decisions.csv`: Status → `on order` + delivery year on row 814 and the six
      Arctic LNG 2 hulls (797, 799, 805, 806, 812, 823); Vessel type row 81 → FSU and row 270 →
      FSRU; Karadeniz restylings (11, 20, 29, 39); row 785 `Al Kheesah`; row 929 `TFDE`; rows
      994 / 1118 Vessel type refs. (Row 61 Vessel type ref: rejected 2026-09-17 — batch 9 proposes
      `FSU` there.)
- [x] **`QC-max` — decided 2026-09-17: `qc-max` is a Vessel type value** (in the sheet dropdown and
      the vocabulary). **Batch 11** proposes it on the 24 × 271,000 cbm QatarEnergy ships (rows
      1070–1074, 1119–1129, 1171–1173, 1176–1178, 1201–1202), IGU 2026 PDF as ref.
- [ ] **8 owner / builder changes** in `manual_review.json` (rows 70, 818, 819 owner; 11, 268, 567,
      929, 941 builder) — IGU prints short labels; pick the canonical name (a builder change
      cascades into the yard-location columns).

## 2. Apply and verify (Apply SOP, `docs/sops/apply.md`)

Apply 1–2 before 4 (they rename rows 4 also touches). Artifacts are keyed by row_id, so a
shifted sheet is safe — but **`apply_rows.csv` full rows are a snapshot of the backend at build
time**: with twelve batches sharing rows (8 shares 138 with batch 1 and 193 with batch 4), pasting
one batch's full rows reverts the batch applied before it. **Use `apply_patch.csv` for every
batch** (AP §2a). If you do want a full-row paste, re-pull and re-run `apply_batch.py --batch
<dir>` immediately before it.

`tools/apply_patch.gs` settings: `BACKEND_SHEET_NAME = "data - backend"`; `OVERWRITE_NONBLANK` as
below (counts against the 18:00 ET pull, current accepts only — they grow as holds are released):

| Batch | `set` cells | onto a non-blank cell | `OVERWRITE_NONBLANK` |
|---|---|---|---|
| 1 | 372 | 372 | `true` |
| 2, 5 | 0 — all on hold | | 2 `true`, 5 `false` |
| 3 | 174 `append` cells (7 new rows) | n/a | either |
| 4 | 1,033 | 0 | `false` (additive to blanks) |
| 6 | 175 | 175 (ref appended to the existing ref) | `true` |
| 8 | 884 | 132 (+7 already equal) | `true` |
| 9 | 38 | 37 | `true` |
| 11 | 48 | 0 | `false` |
| 12 | 58 | 58 | `true` |
| 10 | 190 | 2 | `true` |

In the DRY_RUN log, `would set` must equal the `set` count and there should be no
`SKIP set (non-blank)` line on a `true` batch.

- [ ] Batch 1 — apply, then `python scripts/verify_apply.py --batch batches/<dir> --pull`
- [ ] Batch 2 — apply + verify
- [ ] Batch 3 — apply + verify
- [ ] Batch 4 — apply + verify
- [ ] Batch 5 — 2 of 8 cells applied 2026-09-18 (`verify_report.csv`: 2 landed); the rest wait on the holds.
- [ ] Batch 6 — apply via `apply_patch.csv` (not full rows) + verify
- [ ] Batch 8 — apply via `apply_patch.csv` (its 328 rows overlap batches 1 and 4; shared cells
      agree in value) + verify. After batch 6: both touch row 814's Status `[ref]`.
- [x] Batch 9 — **applied 2026-09-17 19:00 ET** (Sheets API `values.batchUpdate`, RAW, 38 cells;
      `verify_report.csv` in the batch dir: 38 landed / 0 mismatch / 0 missing). The 18 rows are
      `scrapped` and row 61 is an FSU. Map fleet re-exported (`../lng-carriers-map` branch
      `fleet-row61-fsu`, 59 vessels — not pushed; `data/imo_mmsi.csv` still lacks IMO 9211872
      because `fetch_mmsi.py` scrapes vesselfinder and the IP ban is still in force at 19:00 ET).
- [x] Batch 11 — **pushed 2026-09-21 17:04 ET** (48 cells, review-app push; `push_log.jsonl`). Run `verify_apply.py --pull` to close.
- [x] Batch 12 — **applied 2026-09-18** (58 cells; `verify_report.csv`: 29 landed / 29 MISMATCH that
      are `.00` display format only). `$m` dropped from the vocabulary.
- [ ] Batch 13 (`2026-09-18_2005ET_fix_igu2026_hulls`, 41 accept) — 13 sourced hull fills **pushed 2026-09-21**
      (26 cells); the 28 `preserve_ref` restylings (no source line) still need a click. Added to the review manifest 2026-09-21.
- [ ] Batch 10 — apply **last, via `apply_patch.csv` only** (its full rows are built from the
      live backend and would revert the Names of 1, 2 and 8) + verify. Decide each `Other names`
      line with its Name line: a rejected rename takes its former-name line with it; a released
      Name hold releases rows 881 / 944 / 945 / 948 / 961 / 969 / 970 too. Re-run
      `apply_batch.py` after editing `decisions.csv`.
- [ ] Review any HIGH/MED group in each `dedupe_report.csv` (apply.md §5a). Known MED
      pairs: Knutsen × Hanwha 1142/1143 vs 1158/1169 are different orders (Dec-2025 vs
      May-2026) and get distinct hull numbers from batch 4; Hanwha Philly is the duplicate
      decision above.
- [ ] Batch 3 adds an FSRU → re-export the map fleet
      (`../lng-carriers-map/tools/export_fleet.py`).
- [ ] Final gate: re-pull, `python scripts/qc_backend.py` (was 7 LOW only, no HIGH/MED),
      `python scripts/dedupe_check.py`.

## 3. Stream 0 — citation rot sweep (paused at your request)

State is resumable from `work/citation_qc.csv`. Would become a follow-up batch (fix mode).

- [ ] Fix batch for the 21 dead URLs / 27 cells:
  - 15 TradeWinds Status refs on the Woodside rows (hand-entered sequential guesses
    `2-1-1875729` … `2-1-1875743`) → point all at the real article `2-1-1875728`.
    (Row numbers in the plan doc predate today's pull — re-derive.)
  - new-ships.com shipyard pages (rows 347, 351, 362, 365, 367, 509, 540; yard
    country/area + one lat/lon): HTTP 422, truly dead → re-source from the yard's site or CSB.
  - indiashippingnews row 1118 (Name; Shipowner) redirects to site root → SHI DART filing
    or Korean press.
  - investors.seatrium.com row 11: real browser gets a genuine 404 → dead.
  - Row 751 Hull number ref: marinevesseltraffic slug page gone (IMO 9961398 now
    `Maran Gas Syros`) → re-cite.
  - Row 752: marinetraffic.org page now titled `Danuta Siedzikowna-Inka`; no longer
    corroborates the hull number.
  - Row 800 Status ref: marinetraffic.org page doesn't say "Delivered" → needs another ref.
- [ ] Scoped `citation_qc.py --corroborate` run (recommended: on-order/proposed block via
      `--sheet-rows`, plus any row a batch touched). Never run.
- [ ] 46 existing shipvault refs the unit record does not corroborate (listed in batch 6
      `notes.md`).
- [ ] Still blocked, keep as "environment-blocked" (7 URLs / 40 cells): jnshipyard.com.cn,
      hls.co.kr, chantiers-atlantique.com, businesstoday.com.my (retry once by hand),
      dnv.com, bloomberg.com.

## 4. Research not yet done

- [ ] Active-row blanks: ~80 Cargo type and ~74 Vessel type (derivable), 6 Propulsion.
      (Price / Operator / Contract date on the 983 Dec-2024 bulk-loaded rows: left alone by
      decision.)
- [ ] MISC hulls H2019A–H2023A on shipvault — no citable press yet; next discovery run.
- [ ] Mozambique LNG confirmation — deadline was pushed to Sep 2026; re-check next month.
- [ ] Re-test vesselfinder with a **single** request (IP ban still in force at last probe,
      2026-09-17 23:00 UTC — the map repo's `fetch_mmsi.py --only-missing` hung). Do not loop.

- [ ] **Refs for former names (batch 10 holds).** 29 `Other names` lines have no ref that prints
      the former name. Worth a search: the real renames — rows 57 East Energy, 124 CCH LNG,
      144 Stena Blue Sky, 190 Alto Acrux, 742 North Mountain — and the Karadeniz restylings
      (11, 20, 29, 39). The hull / `Dalian No 1 G175K-N` placeholders (827, 887, 909, 935,
      988–991, 1000, 1007, 1008, 1012, 1014, 1031, 1032, 1034, 1035, 1039, 1079, 1080) may never
      get one — decide whether a blank `Other names [ref]` is acceptable for a placeholder.
- [ ] **IGU 2026 `(ex-…)` names as an `Other names` data-fill.** IGU prints 55 ex-names; several
      are not in the backend (e.g. `Northwest Stormpetrel`, row 20). Lead only so far.

## 5. Tooling follow-ups

- [ ] **Controlled vocab carries seeded corruption**: `Supporting` (Vessel type) and
      `prismatic conventional DFDE` / `prismatic small-scale DFDE` (Propulsion) are in
      `scripts/lookups.py` / `data/controlled_vocab.md` because they were seeded from rows
      451 / 499–501 / 509. Remove them with the fix batch, and add a vocab-membership check on
      Cargo / Vessel / Propulsion type to `qc_backend.py` (Status has one since batch 9; the
      other three do not).
- [ ] Verifier: Status `active` still passes on a bare boilerplate "active".
- [ ] Shipvault data quality (IMO typos failing the check digit, wrong owner tags) — treat
      as Y / single-source, never for owners. Already the working rule; not yet enforced in code.
- [ ] Optional: write the delivery roll-forward up as an SOP section (plan doc decision 4 —
      suggested as data_fill.md §11).

## What went wrong this pass (for reference)

- **vesselfinder IP ban.** A bare 1 req/s loop over 323 IMOs got this machine's IP dropped
  at the network level after ~150 requests. The fetch ladder can't clear a TCP drop. Fix:
  `scripts/sweep.py` (paced, circuit breaker) and a marinetraffic.org re-check of all 176
  missed IMOs (176/176 answered). Cost: batch 1 temporarily lost its second source.
- **Tracker sweep pre-filtered on the backend name.** The "unnamed 2028+ hulls" included
  QatarEnergy ships already named (rows 1017–1024, 1031–1037, 1043, 1057, 1058), hence the
  second marinetraffic run. A hull placeholder in the backend doesn't mean the ship is unnamed.
- **Shipvault pages render blank in a browser** (double-encoded API answer) → batch 6 and
  the companion-ref rule (RF §6a.8 rev 21).
- **Thinner coverage than a normal run.** WebSearch budget ran out mid-run (later clusters
  used site searches via `scripts/fetch.py`); TradeWinds / Upstream paywalls blocked many
  contract dates and prices; the 48 per-vessel prices come from order totals (accepted 2026-09-17).
- **Verifier false reads fixed along the way**: "IMO 1162403" read as a 403, "$500 million"
  as HTTP 500, CSS `font-size:16px` matching a bare "16", Wayback 429s read as "no snapshot".
