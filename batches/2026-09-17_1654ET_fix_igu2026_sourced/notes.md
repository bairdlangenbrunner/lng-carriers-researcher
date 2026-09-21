# Fix batch — values sourced from the IGU World LNG Report 2026 (2026-09-17, sep-17-pass batch 8)

Promotes the batch 7 intercomparison (`../2026-09-17_1458ET_igu_reconciliation_igu2026/`) into
proposals. Same backend pull as batch 7 (1,220 rows; re-pulled 2026-09-17 16:4x ET — identical).
All row numbers are **live sheet rows**.

## The rule this batch runs under (Baird, 2026-09-17 — IG §5.4)

- **What IGU 2026 prints is a sufficient sole source for now.** Every cell cites the report PDF
  and nothing else: `https://www.datocms-assets.com/146580/1783403747-igu-world-lng-report-2026.pdf`.
  The PDF (unlike the landing page) passes the §3.8c gate: 468 cells, 0 refs dropped.
- **Vessel type may cite the IGU report** — the Vessel Type column for listed vessels, and the
  report's size-class scheme as the classification source for vessels IGU does not list.
- **OPEN, Baird asked to be reminded:** whether these IGU-only cells get a second reference at
  the ref-validation step. They are identifiable by the PDF URL being their only ref.
- Caveat on the gate: it checks that the cell value occurs in the document. In a 100-page PDF
  listing 1,100 vessels, `conventional` or `2026` always occurs, so the gate proves the URL is
  live and is the right document — the per-vessel reading is the extractor's (`igu_fleet.py`,
  check-digit + per-page count validated). Each cell's note gives the table and PDF page.

## Contents — 468 cells / 328 rows (443 accept / 24 hold / 1 reject)

| Group | Cells | Decision |
|---|---|---|
| Blank Vessel type filled from IGU's Vessel Type column (74 active + 210 on order) | 284 | accept |
| Blank Cargo type | 78 | accept |
| Blank Propulsion type (4), Capacity (2: rows 11, 1004, + `cbm` units) | 8 | accept |
| Vessel type Rule-F refs on rows IGU does not list (value unchanged) | 10 | 7 accept; rows 994, 1118 (no Capacity) hold; row 61 **rejected** 2026-09-17 (Baird) — batch 9 (`1702ET_fix_scrapped_status`) proposes `FSU` there |
| Names — 19 renames / sales, 5 truncated or mis-spelt backend names (88, 294, 446, 461, 584), `Vivit` 624, `Clean Sirocco` 790, `Greenergy` 780 / 781 / 915 / 916, row 909 `Fath Al Khair` | 28 | accept |
| Names — Karadeniz restylings 11 / 20 / 29 / 39, row 785 `Al Kheesah` | 5 | hold |
| Delivery year 2025 → 2026 on 13 active rows IGU still had on order at end-2025, + row 800, + row 929 (→ 2025) | 15 | accept |
| Row 929 Alexey Kosygin: Status → `active` (IGU fleet table) | 1 | accept (`TFDE` propulsion: hold — not a value the backend uses) |
| Row 814 + six Arctic LNG 2 hulls (797, 799, 805, 806, 812, 823): Status → `on order`, delivery year per IGU | 14 | hold (sanctioned family; Status left untouched in batch 1) |
| Load corruption rows 451 / 499 / 500 / 501 / 509: Vessel type `Supporting` → `conventional` (509 `small-scale`), Propulsion → `DFDE` | 10 | accept |
| Propulsion flips IGU made this edition (761, 765, 785, 788, 789, 792, 843, 844, 936, 941) | 10 | accept |
| Row 844 Capacity 200,000 → 174,000; row 503 Cargo type spherical → membrane | 2 | accept |
| Vessel type row 81 → FSU, row 270 → FSRU | 2 | hold (scope flags) |

Names are written without IGU's `(ex-…)` tail (the backend never carries one) and in the
backend's case (`SC SERENITY` → `SC Serenity`).

## Deliberately not proposed

- **The 18 dropped rows** — IGU's silence is not a statement; `scrapped` needs a demolition ref
  (separate fix batch, in progress in another session on `sep-17-pass-scrapped-status`).
- `backend_differs` fields (backend edited after the load from a better source): names on rows
  347, 565, 813–815, 826, 938, 939, 1015, 1016, 1067–1069, 531 (`Woodside Rees Withers` — IGU
  drops the s); owners on 124, 421, 782, 783, 841, 915, 916, 919, 924, 925; propulsion row 748;
  builder row 9.
- **61 on-order Delivery-year diffs** — IGU's schedule is nine months old; batch 1's roll-forward
  is the better source. Reading list only.
- Rows 873 / 910: batch 1 proposes `Minerva Eleonora` / `Mihzem`, IGU prints `Eleonara` /
  `Mizhem` — a spelling conflict between sources, left to the batch 1 decision.

## `manual_review.json` (32)

- **24 × `QC-max`** (rows 1070–1074, 1119–1131, 1174–1176, 1179–1181; 271,000 cbm QatarEnergy
  ships): not a controlled-vocabulary value → vocabulary decision, blank left unproposed.
- **8 owner / builder changes** IGU prints as short labels — rows 70 (→ Soechi Lines), 818 / 819
  (→ Venture Global), 11, 268, 567, 929, 941 (builders; `HD Hyundai` is ambiguous between Ulsan
  and Samho, and a builder change cascades into the yard-location columns).

## Overlap with the other pending batches

Shared cells all agree in value — they are holds elsewhere that the IGU ref now supports:
batch 1 Names rows 915 / 916; batch 4 Vessel type rows 1014, 1017–1024, Capacity (+ units) row
1004, Cargo type row 929. Batch 6 appends a shipvault companion to row 814's Status `[ref]`,
which this batch's (held) Status change would replace. **Apply from `apply_patch.csv`
(cell-level), not full rows** — 138 rows are shared with batch 1 and 193 with batch 4.

## Files

`build_fix_json.py` (regenerates `fix.json` + `manual_review.json` from batch 7's
`igu_reconcile.json`), `fix.json`, `lng_carrier_fix.xlsx` (zero formula errors), `digest.md`,
`decisions.csv`, `apply.json`, `apply_rows.csv`, `apply_patch.csv`, `conflicts.csv` (empty).
Folded into the combined workbook as apply order 8 (17:15 ET build; the scrapped-status batch is 9). Not in the report page.

## Update 2026-09-17 18:09 ET — `QC-max` resolved

Baird added `qc-max` to the Vessel type vocabulary. The 24 `QC-max` rows that sat in
`manual_review.json` are proposed by batch 11 (`2026-09-17_1809ET_fix_qcmax_vessel_type`);
`manual_review.json` now holds the 8 owner / builder changes only, and `build_fix_json.py` skips
`QC-max` so a re-run does not duplicate batch 11.

## Update 2026-09-18 — row 721 (live row 11) Name is `LNGT Antarctica`, not IGU's label

Baird's ruling: the current name by IMO lookup (8608872) is `LNGT Antarctica`
(offshoreshipadvisor.com, passes §3.8c); IGU 2026's `Karadeniz LNGT Antarctica` is a label and
goes to `Other names` with the former Name (batch `1737ET`). `fix.json` edited by hand for this
one cell — `build_fix_json.py` would regenerate the IGU value — workbook rebuilt (0 refs dropped,
zero formula errors), line accepted, `apply_batch.py` re-run: 444 accept / 23 hold / 1 reject.
Trackers disagree: shipvault (`KARMOL LNGT P ANTARCTICA`) and marinetraffic.org still print the
Karmol name. The other Karadeniz restylings (live rows 20 / 29 / 39) are untouched and still held.
Second Name ref added the same evening: vesseltracker.com (`Lngt Antarctica`, IMO 8608872, MMSI
636023902, live AIS position) passes §3.8c. Equasis not checked — it needs a registered login
and no credential is stored.

## Update 2026-09-21 — IGU-sole-source Names checked against other databases (IG §5.4 rev 3)

Baird's ruling: IGU alone never decides a Name. All 32 Name changes citing only the IGU PDF were
looked up by IMO in shipvault, marinetraffic.org (`imo_tracker.py`, paced) and, for the contested
ones, vesseltracker.com. 22 stand (a database explicitly agrees; shipvault lags on live rows 69,
70, 114, 167 but marinetraffic.org agrees). Changed by `name_lookup_overrides.py` (patches this
batch's and batch `1737ET`'s `fix.json`; re-run it after `build_fix_json.py`):

| live row | was proposed (IGU) | now | refs |
|---|---|---|---|
| 20 | Karadeniz LNGT Americas | `KLNGTP Americas` (Y, hold) | vesseltracker — no database prints the backend's `LNGT Americas`; reject to keep it |
| 29, 39 | Karadeniz LNGT Powership Black Sea / Marmara | Name line dropped — `KLNGTP …` stays | — |
| 62 | Seapeak Jupiter | `Gas Polaris` (Y, hold) | vesseltracker, marinetraffic.org — renamed again since IGU |
| 73 | Arctic Metagas | `Arctic Metagaz` (G) | vesseltracker, marinetraffic.org, shipvault |
| 124 | LNG Soars | `LNG Scorpio` (Y, hold) | vesseltracker, marinetraffic.org; shipvault says `CCH Gas` |
| 365 | Cool Baltic | Name line dropped — `Kool Baltic` stays | — |
| 624 | Vivit City LNG | Name line dropped — `Vivirt City LNG` stays | — |
| 909 | Fath Al Khair | `Fat'h Al Khair` (G) | shipvault + unit record |

IGU's name goes to `Other names` in batch `1737ET` in every case. Live row 88 keeps IGU's
`Hongkong Energy`: the databases print `Ergy`, a demolition-voyage name (→ `Other names`).
Decisions made for the old values were reset to the confidence default on the changed lines.
Rebuilt: 0 refs dropped, zero formula errors; 440 accept / 23 hold / 1 reject.

Later the same day (Baird): live row 20 `KLNGTP Americas` accepted, with its `Other names` line in
batch `1737ET`. Live row 88 (IMO 9250725) gains a **Status `active` -> `scrapped`** line as a
suggestion — Y, held: shipvault (status `SCRAPPED`, + unit record) and vesseltracker.com (header
label `scrapped`, last position Bangladesh) both pass §3.8c; IGU 2026 still lists the vessel. The
row is kept (IG §5.2). Rebuilt: 0 refs dropped, zero formula errors; 441 accept / 23 hold / 1 reject.

Still a lead, not in this batch: live row 73 (IMO 9243148) is `LOST` on shipvault and `active` in
the backend — `lost` is not a vocabulary value; needs its own ref and a call on the Status.

## Delivery history cells (added 2026-09-21, RF rev 25 §4.19)

`python scripts/delivery_history.py --batch <this dir>` — 21 Delivery year cells here move the year
**later** than the backend's 2025 (15 → 2026, 6 Arc7 rows → 2027), so each row also gets
`Previous delivery year(s)` = `2025` and `Delivery delayed` = `yes`, at its Delivery year line's
confidence (14 G / 7 Y) and **decided together with that line**. Row_ids 40, 41, 42, 116, 117,
118, 121, 183, 432, 445, 488, 703, 752, 797, 916, 917, 981, 994, 995, 996, 1143.

- Ref for the former year: the **IGU 2025 report PDF**, whose extraction prints 2025 for every one
  of the 21 IMOs. Row_ids 41 and 42 (`Rotmistrz Witold Pilecki`, `Maran Gas Antiparos`) also keep
  their shipnext page, which says `built in 2025` — i.e. a live source still disagrees with
  IGU 2026's 2026 on those two; worth a look when deciding the Delivery year line.
- 42 proposals added (465 -> 507; 469 accept / 37 hold / 1 reject). Rebuilt paced: 0 refs dropped,
  recalc zero errors. `decisions.csv` keeps every existing decision; each new line's default matches
  its Delivery year line's decision.

## 10 Vessel type lines withdrawn (2026-09-21, IG rev 5 §1 / RF rev 26 §3.8c)

An IGU report PDF is a ref only for what it prints **for the row's IMO, in that column**
(`igu_refs.corroborates_cell`). Ten value-unchanged Rule F lines here cited the IGU 2026 PDF for
Vessel type `conventional` on vessels IGU 2026 does not print — the earlier text gate passed them
only because `conventional` appears ~700 times in the table:

- IMO not listed in IGU 2026: live rows 61 (IMO 9211872), 487 (9761803), 488 (9761815), 994 (1119078).
- No IMO, so nothing IGU prints can be tied to the row: live rows 1118, 1169, 1179–1182.

The lines are removed (value unchanged + no ref = nothing to apply) and listed in
`manual_review.json`; `build_fix_json.py` now routes this case there. They stay Rule F negatives:
each needs its own source, or a ruling that a capacity-derived size class stands on the Capacity
ref. Decisions lost with them: 7 accept, 2 hold, 1 reject (live row 61). Script fix in the same
change: a blank IMO now fails the IGU check instead of falling back to the text gate.

507 -> 497 proposals (462 accept / 35 hold); every other decision unchanged. Rebuilt paced:
0 refs dropped, recalc zero errors. The other fix batches were audited offline against the same
check: no other IGU ref fails.
