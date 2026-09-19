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
