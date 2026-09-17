# 2026-09-17 10:17 ET — sep-17-pass, combined results

Not a research batch. A read-only roll-up of the six sep-17-pass batches
(`batches/2026-09-17_04*ET_*`, `_05*ET_*`; see `docs/plans/2026-09-17_sep-17-pass_summary.md`)
into one workbook and one shareable report page. Nothing here is applied to the backend;
apply still runs per batch through the Apply SOP, in the order on the README sheet.

## Contents

- `lng_carrier_sep-17-pass_results.xlsx` — 16 sheets. `all_proposals` is every proposed
  change (1,424 lines: 843 accept / 581 hold by default; 670 G / 754 Y) with **live sheet
  row**, current backend value, proposed value, source URL(s), confidence, decision and
  gate verdict. `all_changes_backend_shape` is all six batches merged into the backend's own
  structure: columns A:AT are the backend columns in backend order, one full row per vessel,
  sorted by live sheet row (549 edited rows, 12 new rows at the bottom, the 3 Woodside
  duplicates struck through as DELETE ROW; 2,685 changed cells, 1,111 on hold). Accepts *and*
  holds are laid in — fill = confidence (peach = an existing `[ref]` rewritten/appended),
  italics = hold, cell comment = batch / decision / old value / note — so it is a review
  surface, not a blind paste: the per-batch `apply_rows.csv` files stay the accept-only
  apply artifacts. Helper columns AU:AZ (live sheet row, row action, holds) sit right of
  the backend columns. `flags_conflicts` are not laid in. `open_decisions` lists the nine decisions waiting on a person. `b1_`–`b6_`
  are each batch's wide paste-ready sheet with a live-row column prepended (data-fill
  filtered to rows with at least one proposal). Then `flags_conflicts` (155),
  `manual_review` (52), `proposed_bucket`, `shipvault_unmatched`, `documented_blanks`
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
