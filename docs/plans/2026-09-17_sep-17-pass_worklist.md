# sep-17-pass — worklist (written 2026-09-17 evening)

Working checklist for getting the sep-17-pass into the backend and closing out the
research pass. Tick items as you go. Detail behind every item is in
`docs/plans/2026-09-17_sep-17-pass_summary.md` (apply order + decisions) and
`docs/plans/2026-09-16_full_research_pass.md` (plan of record, stream 0 results).

## Where things stand

- **Nothing has been written to the backend sheet.** Re-pull on 2026-09-17 evening is
  identical to the morning pull: 1,220 rows (822 active / 364 on order / 34 proposed).
- The research is done. Six batches are merged to main (PRs #11–#18), each with
  `digest.md`, `decisions.csv` and offset-proof apply artifacts.
- Combined workbook (name = build date + ET time; newest file in the dir is current):
  `batches/2026-09-17_1017ET_sep-17-pass_combined/lng_carrier_sep-17-pass_results_2026-09-17_1709ET.xlsx`
  — 18 sheets, 1,444 proposals (880 accept / 564 hold), keyed by live sheet row; the
  `igu_findings` tab carries the batch 7 comparison (291 lines, leads not proposals).
- Report shared with Rob is at version 4 and **predates batches 7 and 8** (no IGU section, no
  scrapped rows; not republished): https://claude.ai/artifact/C1eEJt5CKeqauvfGGg8Ph3
- A seventh batch was added in the afternoon: the **IGU World LNG Report 2026
  intercomparison** (`1458ET_igu_reconciliation_igu2026`). It is a comparison artifact — it
  proposes nothing and is never applied — but it opens the decisions in §1b.
- An eighth batch followed from its first two decisions (`1702ET_fix_scrapped_status`): the new
  Status value `scrapped` on the 18 rows IGU dropped, and row 61 → Vessel type `FSU`. Rule set
  with it: **rows are never deleted from the backend**.
- All row numbers below are **live sheet rows** unless marked `row_id`.

## The batches (all under `batches/2026-09-17_…`)

| # | Batch dir | Contents | Accept / hold |
|---|---|---|---|
| 1 | `0421ET_fix_delivery_rollforward` | 63 rows → `active`, 26 delivery years corrected, 19 rolled forward, 116 names (224 cells / 151 rows) | 186 / 38 |
| 2 | `0458ET_fix_delivery_confirmed` | rows 887 (→ active, `Al Nigyan`) and 924 (→ active) | 0 / 3 |
| 3 | `0431ET_discovery_since_jun_2026` | 12 new vessels in 5 clusters | 7 / 5, plus 10 backend flags |
| 4 | `0511ET_data_fill_on_order` | 1,003 cells / 483 rows, incl. 48 order-total Prices (all hold) | 493 / 510 |
| 5 | `0505ET_ref_fill_rule_f` | 8 refs, 11 documented negatives | 0 / 8 |
| 6 | `1114ET_shipvault_companion_refs` | unit-record URL appended as second ref on 175 cells / 27 rows (values untouched) | all accept |
| 7 | `1458ET_igu_reconciliation_igu2026` | whole backend vs IGU 2026 (fleet at end-2025), IGU 2025 as the previous edition: 1,054 rows matched by IMO, 188 with a field diff, 18 dropped, 47 Status disagreements (24 already in batch 1), 1 candidate | n/a — comparison only (IG rev 2) |
| 8 | `1702ET_fix_scrapped_status` | 18 rows IGU dropped → Status `scrapped` (press + shipvault refs replace the IGU-2025 `Status [ref]`); row 61 Puteri Delima Satu → Vessel type `FSU` (two MISC documents) | 19 / 0 |

Discovery candidates in batch 3: Samsung HI × Dynagas 4 × 200,000 cbm (14-Sep-2026, Y);
HD Hyundai HI × Tsakos (01-Jul-2026, $254M, G); HD Hyundai HI FSRU, owner undisclosed
(30-Jun-2026, Y); Jiangnan × ADNOC L&S H2706–H2709 (10-Jul-2026, G); Jiangnan H2858/H2859
(25-Aug-2026, G; press says delivery 2029, shipvault 2030).

## 1. Decide the holds

Edit the `hold` rows in each batch's `decisions.csv`, then re-run
`python scripts/apply_batch.py --batch batches/<dir>`.

- [ ] **Proposed bucket** (`…discovery…/proposed_review.json`): delete Woodside placeholders
      rows 1204–1206 (they duplicate Seapeak on-order rows 1165–1167). Other Woodside rows,
      Equinor (1186) and Mozambique LNG slots (1187–1203) stay `proposed`. Also the
      Mozambique owner/yard split flagged in the discovery batch.
- [ ] **Likely duplicates**: Hanwha Philly 1083 ↔ 1085 and 1132 ↔ 1086.
- [ ] **Vessel type / Cargo type rule.** "conventional" is a tracker classification, never
      page wording, so it can't pass the ref gate (10 Rule-F orphans; most type fills are Y).
      Decide: let a capacity-derived type stand on the Capacity ref, or leave it unreffed.
- [ ] **Price convention**: backend mixes `250` + `$m` with `250000000` + `USD`. New fills
      use full USD. (Shipvault contract prices were left unused — single-source.)
- [ ] **`Greenenergy …` names** look wrong — shipvault and AIS both say `Greenergy`.
- [ ] **Manual-review rows**: `…rollforward/manual_review.json` (54) and
      `…delivery_confirmed/manual_review.json` (24 unconfirmed). Mostly ships AIS-live while
      shipvault says on order; plus the sanctioned Zvezda / Arctic LNG 2 hulls (status
      untouched); rows 1017 / 1033 show an MMSI early (low priority).
- [ ] **Marinetraffic.org-only names on hold** in batch 1 (10, incl. row 1039 `Libsayer`).
- [ ] **Backend flags from discovery**: BW LNG rows 1168/1169 capacity (177,000), row 1162
      price, COSCO hulls.
- [ ] **Possible mis-citations / value conflicts** from the data-fill agents — full list in
      `…data_fill_on_order/notes.md` (rows 1182–1185; row_ids 1162/1163, 1212/1213, 1218,
      1207/1208, 197, 375, 255/256, 318/319, 515/516; Samsung × CMES and Jiangnan × Taiping
      capacity).
- [ ] **Batch 4 companion cells**: 140 `Price currency` / `Capacity units` cells are
      derivable but sit on `hold` because they follow their parent Price / Capacity fill —
      flip each with its parent. (This is why `digest.md` says 633 auto-safe while
      `decisions.csv` carries 493 accept / 510 hold.)
- [ ] **48 order-total Prices** in batch 4 (total ÷ N, Y max, all hold) — accept or not.
- [ ] **Batch 5**: 8 Rule-F refs on hold.

## 1b. IGU 2026 intercomparison — decisions it opens

Detail, per-row tables and shipvault leads: `batches/2026-09-17_1458ET_igu_reconciliation_igu2026/notes.md`
and the workbook beside it (11 sheets, live sheet row first). Nothing here is a proposal yet:
the IGU landing page cannot pass the §3.8c gate and the shipvault dates are single-source
leads, so each accepted item needs a verified ref and goes into a follow-up `fix` batch.

- [x] **`scrapped` Status value — decided 2026-09-17: yes, and rows are never deleted.** IGU
      dropped 18 backend `active` rows between editions; all are scrapped steam tonnage. All 18
      move to Status `scrapped`, whichever side of Dec 2025 the scrapping falls (the earlier
      "11 leave / 7 stay" split is void) — **batch 8** (`1702ET_fix_scrapped_status`), press +
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
      IGU edition): **done — batch 8 proposes `FSU`** on MISC's release + Annual Report 2025.
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

## 2. Apply and verify (Apply SOP, `docs/sops/apply.md`)

Apply 1–2 before 4 (they rename rows 4 also touches; artifacts are keyed by row_id, so the
order is about readability, not safety).

- [ ] Batch 1 — apply, then `python scripts/verify_apply.py --batch batches/<dir> --pull`
- [ ] Batch 2 — apply + verify
- [ ] Batch 3 — apply + verify
- [ ] Batch 4 — apply + verify
- [ ] Batch 5 — apply + verify
- [ ] Batch 6 — apply via `apply_patch.csv` (not full rows) + verify
- [ ] Batch 8 — apply + verify (any order; no cell overlaps another batch). If the sheet's
      Status column has a validation dropdown, add `scrapped` to it first. Row 61 → FSU changes
      the map fleet: re-export after applying.
- [ ] Review any HIGH/MED group in each `dedupe_report.csv` (apply.md §5a). Known MED
      pairs: Knutsen × Hanwha 1145/1146 vs 1161/1172 are different orders (Dec-2025 vs
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
      2026-09-17 15:24 UTC). Do not loop.

## 5. Tooling follow-ups

- [ ] **Controlled vocab carries seeded corruption**: `Supporting` (Vessel type) and
      `prismatic conventional DFDE` / `prismatic small-scale DFDE` (Propulsion) are in
      `scripts/lookups.py` / `data/controlled_vocab.md` because they were seeded from rows
      451 / 499–501 / 509. Remove them with the fix batch, and add a vocab-membership check on
      Cargo / Vessel / Propulsion type to `qc_backend.py` (Status has one since batch 8; the
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
  contract dates and prices; the 48 per-vessel prices come from order totals (all hold).
- **Verifier false reads fixed along the way**: "IMO 1162403" read as a 403, "$500 million"
  as HTTP 500, CSS `font-size:16px` matching a bare "16", Wayback 429s read as "no snapshot".
