# Batches

Every research batch produces a directory here, with the inputs that drove it, the xlsx output, and a `notes.md` recording anything notable about that batch.

## Directory naming

```
batches/<YYYY-MM-DD>_<mode>_<scope>/
```

Examples:

- `2026-05-27_ref_fill_rows_1148-1167/` — [ref]-fill batch on rows 1148–1167
- `2026-05-27_discovery_q2_2026_gap/` — discovery run for the Q2 2026 gap window
- `2026-06-15_sfoc_reconciliation/` — SFOC reconciliation pass

## Per-batch contents

| File | What |
|---|---|
| `citations.json` or `candidates.json` | Input to `build_workbook.py` |
| `lng_carrier_backend_ref_fill.xlsx` or `lng_carrier_candidate_vessels.xlsx` | The output workbook |
| `notes.md` | Conflicts flagged, defects corrected, escalations, anything that needs human attention |
| `verification.log` | Optional — full `url_verifier.py` log if useful for audit |

## The batch index

When a batch is published, add a row to the table below with the Drive share link. To get the link:

1. Upload the xlsx to the project's Google Drive folder
2. Right-click → "Share" → "Anyone with the link" → "Viewer"
3. Copy the link
4. Open it once and use "Open with → Google Sheets" to get the Sheets URL (more useful than the raw xlsx preview)

For the `Drive link` column, prefer the Sheets URL.

## Batch index

| Date | Mode | Scope | Local | Drive | Notes |
|---|---|---|---|---|---|
| 2026-06-03 | discovery | since May 1 2026 (gap 05-01→06-03, 7 main yards) | [folder](2026-06-03_discovery_since_may_2026/) | _(pending)_ | 3 clusters / 6 vessels (1 green, 5 yellow); 1 status flag; build_workbook full-schema discovery fix |

<!-- Example row format:
| 2026-05-27 | ref_fill | rows 1148-1167 | [folder](2026-05-27_ref_fill_rows_1148-1167/) | [Sheets](https://docs.google.com/spreadsheets/d/...) | 2 defects corrected, 1 escalation |
-->
