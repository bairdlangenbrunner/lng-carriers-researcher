# 2026-09-17 10:17 ET — overnight update, combined results

Not a research batch. A read-only roll-up of the five overnight batches
(`batches/2026-09-17_04*ET_*`, `_05*ET_*`; see `docs/plans/2026-09-17_overnight_summary.md`)
into one workbook and one shareable report page. Nothing here is applied to the backend;
apply still runs per batch through the Apply SOP, in the order on the README sheet.

## Contents

- `lng_carrier_overnight_results.xlsx` — 14 sheets. `all_proposals` is every proposed
  change (1,186 lines: 685 accept / 501 hold by default; 647 G / 539 Y) with **live sheet
  row**, current backend value, proposed value, source URL(s), confidence, decision and
  gate verdict. `open_decisions` lists the nine decisions waiting on a person. `b1_`–`b5_`
  are each batch's wide paste-ready sheet with a live-row column prepended (data-fill
  filtered to rows with at least one proposal). Then `flags_conflicts` (206),
  `manual_review` (45), `proposed_bucket`, `shipvault_unmatched`, `documented_blanks`
  (841) and `url_verification` (442).
- `report_data.json` — the same data as JSON, input to the report page.
- `build_combined.py` — builds the two files above. Read-only over the batch dirs and
  `work/backend.csv`.
- `build_report.py` + `report_template.html` — render the report page (one self-contained
  HTML file with the workbook embedded base64 for the download button):
  `python batches/2026-09-17_1017ET_overnight_combined/build_report.py <out.html>`
- Report page, published as a private Claude artifact (share from the page's share menu):
  https://claude.ai/artifact/C1eEJt5CKeqauvfGGg8Ph3

## Notes

- Live rows and "current backend value" come from a 10:15 ET re-pull, identical to the
  overnight pull (1,220 row_ids, 0 rows changed): none of the five batches had been applied.
- README counts are static values computed in Python, not COUNTIFS formulas: LibreOffice is
  not installed here, so formulas would ship with no cached values. They count the default
  decisions and will not follow review edits made in `all_proposals`.
- Backend flags for the discovery batch are read from its `candidates.json`, not from the
  discovery workbook: that workbook's QA_review "Backend status flags" section renders ten
  blank rows, because `build_workbook.py` discovery mode expects `row_id` / `issue_type` /
  `details` / `suggested_action` while the flags carry `flag` / `rows` / `note`. Not fixed here.
