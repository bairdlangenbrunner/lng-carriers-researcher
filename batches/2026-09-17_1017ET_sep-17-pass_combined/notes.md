# 2026-09-17 10:17 ET — sep-17-pass, combined results

Not a research batch. A read-only roll-up of the five sep-17-pass batches
(`batches/2026-09-17_04*ET_*`, `_05*ET_*`; see `docs/plans/2026-09-17_sep-17-pass_summary.md`)
into one workbook and one shareable report page. Nothing here is applied to the backend;
apply still runs per batch through the Apply SOP, in the order on the README sheet.

## Contents

- `lng_carrier_sep-17-pass_results.xlsx` — 15 sheets. `all_proposals` is every proposed
  change (1,186 lines: 685 accept / 501 hold by default; 647 G / 539 Y) with **live sheet
  row**, current backend value, proposed value, source URL(s), confidence, decision and
  gate verdict. `all_changes_backend_shape` is all five batches merged into the backend's own
  structure: columns A:AT are the backend columns in backend order, one full row per vessel,
  sorted by live sheet row (532 edited rows, 12 new rows at the bottom, the 3 Woodside
  duplicates struck through as DELETE ROW; 2,390 changed cells, 999 on hold). Accepts *and*
  holds are laid in — fill = confidence (peach = an existing `[ref]` rewritten/appended),
  italics = hold, cell comment = batch / decision / old value / note — so it is a review
  surface, not a blind paste: the per-batch `apply_rows.csv` files stay the accept-only
  apply artifacts. Helper columns AU:AZ (live sheet row, row action, holds) sit right of
  the backend columns. `flags_conflicts` are not laid in. `open_decisions` lists the nine decisions waiting on a person. `b1_`–`b5_`
  are each batch's wide paste-ready sheet with a live-row column prepended (data-fill
  filtered to rows with at least one proposal). Then `flags_conflicts` (206),
  `manual_review` (45), `proposed_bucket`, `shipvault_unmatched`, `documented_blanks`
  (841) and `url_verification` (442).
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
