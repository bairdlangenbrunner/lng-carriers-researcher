# Batches

Every research batch produces a directory here, with the inputs that drove it, the xlsx
output, and a `notes.md` recording anything notable about that batch. The committed xlsx
is the artifact of record.

## Directory naming

```
batches/<YYYY-MM-DD>_<HHMMET>_<mode>_<scope>/
```

- `<YYYY-MM-DD>` — run date.
- `<HHMMET>` — wall-clock time in US Eastern, e.g. `1509ET`. Batches can run more than
  once a day, so the time token keeps directories unique and sortable. (The earliest
  directories predate this token; don't rename them.)
- `<mode>` — `ref_fill`, `discovery`, `data_fill`, `corroborate`, `fix`,
  `qc_<label>`, `sfoc_reconciliation`, `fsru_reconciliation`, `igu_reconciliation`.
- `<scope>` — rows / gap window / target, in a few words: `rows_1148-1167`,
  `since_may_2026`, `giignl2026`, `igu2026`.

Example: `2026-06-19_1210ET_discovery_since_may_2026/`.

## Per-batch contents

| File | What |
|---|---|
| `citations.json` / `candidates.json` / `data_fill.json` / `fix.json` / `fsru_reconcile.json` / `igu_reconcile.json` | Input to `build_workbook.py` (by mode) — copied in from `work/` so the batch is reproducible |
| `lng_carrier_*.xlsx` | The output workbook (filename fixed by mode) |
| `notes.md` | The batch record — follow `_template_notes.md` |
| `verification.log` | Optional — full `url_verifier.py` log if useful for audit |
| `digest.md` | Triage view (auto-safe vs needs-a-decision) — `batch_digest.py` (apply SOP) |
| `decisions.csv` | Per-proposal accept/hold/reject — the batch's acceptance record (`apply_batch.py`) |
| `apply_rows.csv` / `apply_patch.csv` / `apply.json` | Offset-proof apply artifacts (`apply_batch.py`); `conflicts.csv` for non-blank conflicts |
| `verify_report.csv` | Post-apply landed/mismatch/missing diff (`verify_apply.py`) |
| `dedupe_report.csv` | Post-apply duplicate sweep over touched/added rows (advisory) |

Minimum for any batch: the input JSON, the workbook, and `notes.md`. The apply artifacts
appear once the batch has been reviewed and applied.

After the candidate workbook is reviewed, run the **apply & verify** workflow
(`docs/sops/apply.md`) to get accepted proposals into the backend offset-proof and confirm
they landed. Commit `decisions.csv` (and `apply.json`) with the batch as the acceptance record.

## Batch index

One row per batch, newest last. Add a row when the batch directory is committed.

| Date | Mode | Scope | Folder | Headline |
|---|---|---|---|---|
| 2026-06-03 | discovery | since May 2026 (gap 05-01→06-03, 7 main yards) | [folder](2026-06-03_discovery_since_may_2026/) | 3 clusters / 6 vessels (1 green, 5 yellow); 1 status flag; rebuilt under RF17/DC7 |
| 2026-06-04 | data_fill | Last updated ≥ 2026-05-18 (rows 1144–1223, 42 rows) | [folder](2026-06-04_data_fill_rows_1144-1223/) | 88 fills (59 green, 29 yellow); 140 documented blanks; first data-fill batch (DF rev 1) |
| 2026-06-04 | fix | rows 1216–1217 (structural) | [folder](2026-06-04_fix_rows_1216-1217/) | two column-offset corruptions corrected (stray capacity/cargo duplicates in yard-location cols) |
| 2026-06-05 | fix | rows 1216–1217 capacity | [folder](2026-06-05_1323ET_fix_rows_1216-1217_capacity/) | capacity 176,400 → 180,000 with refs re-gated (first value↔ref-gated fix batch) |
| 2026-06-05 | discovery | CNOOC/CMES/NYK JV roster (Hudong-Zhonghua) | [folder](2026-06-05_1509ET_discovery_cnooc-cmes-nyk-jv_hudong/) | 3 green placeholder candidates completing the firm six-ship JV order |
| 2026-06-05 | corroborate | rows 3–22 (IGU-only refs, pilot) | [folder](2026-06-05_1752ET_corroborate_rows_3-22/) | 74 cells fully corroborated (≥2 independent sources), 2 partial, 12 documented blanks |
| 2026-06-05 | fix | Name placeholder normalization (18 rows) | [folder](2026-06-05_1807ET_name_normalization/) | pre-release Name normalization, cosmetic (`preserve_ref`), 18 rows |
| 2026-06-18 | fix (QC) | whole-backend pre-release QC | [folder](2026-06-18_1054ET_qc_name_normalization/) | 31 findings, zero corruption; 14 rows renamed + 2 orphan refs dropped (QC rev 1) |
| 2026-06-19 | discovery | since May 2026 catch-up (all yards) | [folder](2026-06-19_1210ET_discovery_since_may_2026/) | 1 yellow candidate (Samsung HI, owner unidentified); rings B–D otherwise dry |
| 2026-06-26 | fsru_reconciliation | GIIGNL 2026 Annual Report (fleet as of end-2025) | [folder](2026-06-26_1556ET_fsru_reconciliation_giignl2026/) | 47 matched, 2 reclassify, 1 manual pairing; 4 gaps, all small-scale review (FR rev 1) |
| 2026-09-17 | fix | delivery roll-forward — on-order rows vs shipvault, AIS cross-check on marinetraffic.org (sep-17-pass 1/6) | [folder](2026-09-17_0421ET_fix_delivery_rollforward/) | 224 cells / 151 rows (186 accept, 38 hold): 63 → `active`, 26 delivery years corrected, 19 rolled forward, 116 names; 54 manual-review rows |
| 2026-09-17 | discovery | since Jun 2026 (gap 05-01→09-17, all yards) (sep-17-pass 3/6) | [folder](2026-09-17_0431ET_discovery_since_jun_2026/) | 5 clusters / 12 vessels (7 accept, 5 hold); 10 backend flags; proposed-bucket review (Woodside live rows 1204–1206 duplicate Seapeak 1165–1167) |
| 2026-09-17 | fix | press-confirmed deliveries shipvault lags on (sep-17-pass 2/6) | [folder](2026-09-17_0458ET_fix_delivery_confirmed/) | live rows 887 and 924 → `active` (3 cells, all hold); 24 unconfirmed manual-review rows |
| 2026-09-17 | ref_fill | Rule-F orphan `[ref]`s, whole backend (sep-17-pass 5/6) | [folder](2026-09-17_0505ET_ref_fill_rule_f/) | 8 refs (hold), 11 documented negatives — mostly `conventional` type cells no page words |
| 2026-09-17 | data_fill | on-order blanks + whole-backend derivables (sep-17-pass 4/6) | [folder](2026-09-17_0511ET_data_fill_on_order/) | 1,003 cells / 483 rows (493 accept, 510 hold), incl. 48 order-total Prices (DF §5a, all hold) |
| 2026-09-17 | combined | sep-17-pass roll-up of the six proposal batches + the IGU comparison (review aid, not an apply source) | [folder](2026-09-17_1017ET_sep-17-pass_combined/) | 17 sheets, 1,425 proposals (861 accept / 564 hold) keyed by live sheet row; backend-shape tab; `igu_findings` tab; report-page generator |
| 2026-09-17 | data_fill (ref-only) | shipvault companion refs on existing backend cells (sep-17-pass 6/6) | [folder](2026-09-17_1114ET_shipvault_companion_refs/) | unit-record URL appended to 175 `[ref]` cells / 27 rows (all accept; apply via `apply_patch.csv`); 46 shipvault refs the record does not corroborate |
| 2026-09-17 | igu_reconciliation | IGU World LNG Report 2026 (fleet at end-2025) vs the whole backend, 2025 edition as baseline (sep-17-pass 7) | [folder](2026-09-17_1458ET_igu_reconciliation_igu2026/) | 1,054 matched by IMO, 188 with a field diff; 18 dropped (all scrapped — 11 out of scope, 7 stay); 47 Status disagreements (24 already in batch 1); 1 candidate; comparison only, never applied (IG rev 1) |
