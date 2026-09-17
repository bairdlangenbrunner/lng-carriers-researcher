# 2026-09-17 10:17 ET — sep-17-pass, combined results

Not a research batch. A read-only roll-up of the six sep-17-pass batches
(`batches/2026-09-17_04*ET_*`, `_05*ET_*`; see `docs/plans/2026-09-17_sep-17-pass_summary.md`)
into one workbook and one shareable report page. Nothing here is applied to the backend;
apply still runs per batch through the Apply SOP, in the order on the README sheet.

## Contents

- `lng_carrier_sep-17-pass_results_<YYYY-MM-DD>_<HHMM>ET.xlsx` (current: `…_2026-09-17_1747ET.xlsx`) — the
  name carries the build date and US Eastern time; each rebuild writes a new name and removes
  the previous file (git keeps it). 17 sheets. `all_proposals` is every proposed
  change (1,425 lines: 861 accept / 564 hold by default; 688 G / 737 Y) with **live sheet
  row**, current backend value, proposed value, source URL(s), confidence, decision and
  gate verdict. `all_changes_backend_shape` is all six batches merged into the backend's own
  structure: columns A:AT are the backend columns in backend order, one full row per vessel,
  sorted by live sheet row (549 edited rows, 12 new rows at the bottom, the 3 Woodside
  duplicates struck through as DELETE ROW; 2,687 changed cells, 1,077 on hold). Accepts *and*
  holds are laid in — fill = confidence (peach = an existing `[ref]` rewritten/appended),
  italics = hold, cell comment = batch / decision / old value / note — so it is a review
  surface, not a blind paste: the per-batch `apply_rows.csv` files stay the accept-only
  apply artifacts. Helper columns AU:AZ (live sheet row, row action, holds) sit right of
  the backend columns. `flags_conflicts` are not laid in. `open_decisions` lists the ten decisions waiting on a person. `b1_`–`b6_`
  are each batch's wide paste-ready sheet with a live-row column prepended (data-fill
  filtered to rows with at least one proposal). Then `flags_conflicts` (155),
  `manual_review` (54), `proposed_bucket`, `shipvault_unmatched`, `documented_blanks`
  (818) and `url_verification` (458).
- `report_data.json` — the same data as JSON, input to the report page.
- `build_combined.py` — builds the two files above. Read-only over the batch dirs and
  `work/backend.csv`.
- `build_report.py` + `report_template.html` — render the report page (one self-contained
  HTML file with the workbook embedded base64 for the download button):
  `python batches/2026-09-17_1017ET_sep-17-pass_combined/build_report.py <out.html>`
- Report page, published as a private Claude artifact (share from the page's share menu):
  https://claude.ai/artifact/C1eEJt5CKeqauvfGGg8Ph3

## Notes

- The pass was first called the "overnight update"; renamed **sep-17-pass** on 2026-09-17
  (this dir, the workbook, the `docs/plans/2026-09-17_sep-17-pass_*.md` docs). `work/overnight/`
  scratch paths and the `overnight-update-2026-09-17` branch keep the old name.
- `all_changes_backend_shape` is built with `apply_batch.py`'s own item model, in apply order,
  and asserts that every cell in each batch's `apply.json` lands with the same value.

- Live rows and "current backend value" come from a 10:15 ET re-pull, identical to the
  original ~01:15 ET pull (1,220 row_ids, 0 rows changed): none of the five batches had been applied.
- README counts are static values computed in Python, not COUNTIFS formulas: LibreOffice is
  not installed here, so formulas would ship with no cached values. They count the default
  decisions and will not follow review edits made in `all_proposals`.
- Backend flags for the discovery batch are read from its `candidates.json`, not from the
  discovery workbook: that workbook's QA_review "Backend status flags" section renders ten
  blank rows, because `build_workbook.py` discovery mode expects `row_id` / `issue_type` /
  `details` / `suggested_action` while the flags carry `flag` / `rows` / `note`. Not fixed here.
- **Shipvault companion refs (11:14 ET rebuild).** Most shipvault pages render blank in a browser
  (RF rev 21 §6a.8), so every shipvault ref now carries the unit-record API URL as a second ref:
  350 companions across batches 1, 3, 4, 5, plus a sixth batch, `2026-09-17_1114ET_shipvault_companion_refs` (tab
  `b6_shipvault_companions`), that appends it to the 175 corroborated cells already citing
  shipvault in the backend (27 rows). Workbook rebuilt: 1,361 proposals, backend-shape tab
  543 rows / 2,565 cells. The published report page was **not** republished; its counts predate this.
- **Order-total prices (afternoon rebuild, DF rev 3 §5a).** 21 batch-4 Price lines were showing a
  value with no source URL and a default `accept` (e.g. live row 918): per-vessel prices divided
  out of an order total, whose total-stating URL the gate had dropped while a mis-set
  `derivable: true` kept the value. Fixed at the source — see the data-fill batch's notes.md,
  "Order-total prices". Batch 4 now carries 48 such Prices (15 orders), each with a passing ref,
  all Y / `hold`; 23 of them were previously documented blanks. Workbook rebuilt: 1,415
  proposals (818 accept / 597 hold); no non-derivable proposal is without a URL. The published
  report page still predates this.
- **marinetraffic.org cross-check (late-afternoon rebuild).** vesselfinder never answered for 176
  on-order IMOs; the 95 that are named or deliver in 2027 were re-checked on marinetraffic.org
  (`scripts/sweep.py`, paced) and folded into batch 1 — see that batch's notes.md, last section.
  Batch 1 is now 223 cells / 150 rows, 168 accept / 55 hold (19 names Y → G with a marinetraffic.org
  second ref, 6 Status / Delivery-year cells Y → G, 9 new marinetraffic.org-only names on hold);
  `manual_review` is 52 + 24. Workbook rebuilt: **1,424 proposals (843 accept / 581 hold; 670 G /
  754 Y), 16 sheets**; backend-shape tab 549 edited rows + 12 new / 2,685 changed cells,
  1,111 on hold. `report_template.html`'s hard-coded counts were refreshed to these numbers (six
  batches) and the report page republished.
- **marinetraffic.org cross-check, second run (evening rebuild).** The remaining 81 IMOs were swept
  too, so all 176 are now cross-checked: 18 more names Y → G (live rows 1017–1024, 1031–1037, 1043,
  1057, 1058), 1 new marinetraffic.org-only name on hold (live row 1039 `Libsayer`), 2 early-MMSI
  rows to manual review (1017, 1033). Batch 1 is now 224 cells / 151 rows, 186 accept / 38 hold;
  `manual_review` is 54 + 24. Workbook rebuilt: **1,425 proposals (861 accept / 564 hold; 688 G /
  737 Y), 16 sheets**; backend-shape tab 549 edited rows + 12 new / 2,687 changed cells, 1,077 on
  hold. Report template counts refreshed and the page republished; the counts in the bullet above
  are the earlier rebuild's.
- **IGU 2026 intercomparison (14:58 ET batch, folded in afterwards).** A seventh batch,
  `2026-09-17_1458ET_igu_reconciliation_igu2026`, compares the whole backend against the IGU World
  LNG Report 2026 (IG rev 1). It proposes nothing, so `all_proposals`, the backend-shape tab and
  every count above are unchanged (checked cell-for-cell against the previous build). Added: the
  `igu_findings` tab (291 lines keyed by live sheet row — 18 rows IGU dropped, 47 Status
  disagreements, 224 field diffs, 2 IGU-only vessels — with the pending batch that already
  proposes each one and the shipvault lead, which is not a ref) and a tenth line on
  `open_decisions` (the `scrapped` Status question). 17 sheets. `report_data.json` gained an
  `igu_findings` count only; the report template and the published page were **not** touched and
  still describe six batches.
- **The two IGU follow-up fix batches (folded in 17:15 ET).** Batch 8,
  `2026-09-17_1654ET_fix_igu2026_sourced` (468 lines: 443 accept / 24 hold / 1 reject — what IGU 2026
  prints, the report PDF as sole ref, IG §5.4), and batch 9,
  `2026-09-17_1702ET_fix_scrapped_status` (19 lines, all G / accept — the 18 dropped rows →
  Status `scrapped`, live row 61 → `FSU`). Apply orders 8 and 9; there is no apply order 7 —
  batch 7 is the comparison. Workbook rebuilt as `…_2026-09-17_1715ET.xlsx`, then `…_1720ET.xlsx` after the row 61 reject: **20 sheets, 1,912
  proposals (1,323 accept / 588 hold / 1 reject; 1,150 G / 762 Y)**; backend-shape tab 662 edited rows,
  3,628 changed cells, 1,096 on hold (the counts in the Contents bullet are an earlier build's).
  New tabs `b8_igu_sourced_rows`, `b9_scrapped_rows` and `b8_igu_manual_review` (the 32 IGU
  values batch 8 left to a human). On `igu_findings` the 18 dropped rows show batch 9 and the
  field diffs show batch 8 as the pending batch that proposes them; `open_decisions` line 10
  records the `scrapped` decision (rows are never deleted) and what is still open.
  **Shared cells:** batch 8 re-proposes cells batches 1 and 4 hold (same value, IGU PDF as the
  ref) — the later apply order shows on the backend-shape tab; live row 61 Vessel type is in
  both 8 (`conventional` ref — **rejected** by Baird 2026-09-17, so it is off the backend-shape tab) and 9 (accepted `FSU`, green). One builder rule added: a
  *held* proposal never displaces a cell an earlier batch *accepted* on the backend-shape tab
  (live row 814 Sea Energy, Status: batch 8's held `on order` vs batch 6's accepted companion ref); it stays
  on `all_proposals`. The report template and the published page were **not** touched and still
  describe six batches.
- **Batch 10 — former Names → `Other names` (folded in 17:47 ET).**
  `2026-09-17_1737ET_fix_other_names_former` (131 lines: 95 accept / 36 hold), the new RF §4.16
  rule applied to the Name changes of batches 1, 2 and 8: every former Name (hull placeholders
  included) is *appended* to the row's `Other names`, its gated ref appended to `Other names
  [ref]`. Apply order 10 — after 1, 2 and 8, by `apply_patch.csv` only — and each line is decided
  together with its Name line. Workbook rebuilt as `…_2026-09-17_1747ET.xlsx`: **21 sheets, 2,043
  proposals (1,418 accept / 624 hold / 1 reject; 1,245 G / 798 Y)**; backend-shape tab unchanged
  in rows (647 edited + 12 new + 3 delete — batch 10 only touches rows 1, 2 and 8 already edit),
  3,861 changed cells, 1,139 on hold. New tab `b10_former_names_rows`. No cell of batch 10 is
  proposed by any other batch. 19 Name changes carry no former name (spelling / truncation
  fixes, and live row 942's wrong-vessel name) — listed in the batch's `notes.md`.
