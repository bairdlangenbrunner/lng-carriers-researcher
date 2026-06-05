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
| `citations.json` / `candidates.json` / `data_fill.json` | Input to `build_workbook.py` (by mode) |
| `lng_carrier_backend_ref_fill.xlsx` / `lng_carrier_candidate_vessels.xlsx` / `lng_carrier_data_fill.xlsx` | The output workbook (by mode) |
| `notes.md` | Conflicts flagged, defects corrected, escalations, anything that needs human attention |
| `verification.log` | Optional — full `url_verifier.py` log if useful for audit |
| `digest.md` | Triage view (auto-safe vs needs-a-decision) — `batch_digest.py` (apply SOP) |
| `decisions.csv` | Per-proposal accept/hold/reject — the batch's acceptance record (`apply_batch.py`) |
| `apply_rows.csv` / `apply_patch.csv` / `apply.json` | Offset-proof apply artifacts (`apply_batch.py`); `conflicts.csv` for non-blank conflicts |
| `verify_report.csv` | Post-apply landed/mismatch/missing diff (`verify_apply.py`) |

After the candidate workbook is reviewed, run the **apply & verify** workflow
(`docs/sops/apply.md`) to get accepted proposals into the backend offset-proof and confirm
they landed. Commit `decisions.csv` (and `apply.json`) with the batch as the acceptance record.

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
| 2026-06-03 | discovery | since May 1 2026 (gap 05-01→06-03, 7 main yards) | [folder](2026-06-03_discovery_since_may_2026/) | _(pending)_ | 3 clusters / 6 vessels (1 green, 5 yellow); 1 status flag; build_workbook full-schema discovery fix; rebuilt under RF17/DC7 (owner stylization, multi-URL ", ", yard-location autofill) |
| 2026-06-04 | data_fill | Last updated ≥ 2026-05-18 (rows 1144-1223, 42 rows) | [folder](2026-06-04_data_fill_rows_1144-1223/) | _(pending)_ | 88 fills (59 green, 29 yellow); 140 documented blanks; 1 unknown preserved (O1213); 5 candidate findings; new data_fill workflow (DF rev 1) |

<!-- Example row format:
| 2026-05-27 | ref_fill | rows 1148-1167 | [folder](2026-05-27_ref_fill_rows_1148-1167/) | [Sheets](https://docs.google.com/spreadsheets/d/...) | 2 defects corrected, 1 escalation |
-->
