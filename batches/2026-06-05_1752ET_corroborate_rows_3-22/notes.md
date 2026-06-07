# Corroborate batch — rows 3–22 (IGU-2025-only refs) — PILOT

**Date:** 2026-06-05 17:52 ET · **Mode:** corroborate (new batch type) · **Scope:** row_id 3–22 (20 rows)

## Why this batch exists

The backend leans on a single aggregate source: the IGU 2025 World LNG Report
(`https://www.igu.org/igu-reports/2025-world-lng-report`) is the **sole** `[ref]`
on ~10,165 cells across ~1,076 rows. A report PDF standing alone behind a specific
per-vessel figure is weak provenance and fails the spirit of the §3.8c value↔ref
gate (the report page does not surface per-vessel numbers). This batch type **keeps
IGU** and **appends ≥2 independent corroborators** per cell.

This is the **20-row pilot** to measure corroboration hit-rate and per-row cost
before the full campaign (decisions locked with user: keep IGU + append ≥2;
priority fields only — Name, Shipbuilder, Shipowner, Capacity, Delivery year;
yellow corroborators allowed; pilot first).

## Scope and clusters

88 IGU-only priority cells across 20 rows, 3 clusters:
- **zvezda|smart lng** (rows 3–16) — Arctic LNG 2 carriers, Zvezda yard, Smart LNG owner. Rows 3–4 named (Pyotr Stolypin, Sergei Witte); rows 5–16 are placeholder hull names (`Hull 0XX (Zvezda)`).
- **hudong-zhonghua|mol** (rows 17, 18, 19, 22) — Rex Tillerson, Umm Ghuwailina, Hlaitan, Greenergy Ocean.
- **hudong-zhonghua|united liquefied gas** (rows 20, 21) — Huashan, Kongtong.

## Results

| | count |
|---|---|
| IGU-only priority cells in scope | 88 |
| Corroborated (≥1 surviving independent ref) | 76 |
| — **full** (≥2 corroborators) | **74** |
| — **partial** (1 corroborator; IGU kept, flagged) | **2** |
| Documented blanks (no corroboration possible) | 12 |
| Gate drops (proposed ref didn't contain value) | 0 |

- **Hit-rate:** excluding the 12 Zvezda placeholder-name cells (a placeholder like `Hull 044 (Zvezda)` can never appear in an external source), **76/76 cells got corroboration and 74 (97%) reached the ≥2 bar.** Note rows 3–22 are well-documented recent deliveries — expect a lower rate on older/opaque rows in the full campaign.
- **2 partial cells** (rows 20/21 Shipowner = "United Liquefied Gas"): the literal owner string verifies only on lngprime.com; every other independent source names the operator as COSCO Shipping Energy Transportation. Logged to `conflicts.csv` + `documented_blanks` as an owner-stylization review item — IGU kept, not promoted to full.
- The Zvezda series (rows 5–16) Shipbuilder/Shipowner/Capacity are corroborated at the **series level** (the 15-carrier Arctic LNG 2 program), so they're labelled **yellow** and default to **hold** for human review — correct, not per-hull green.

## decisions.csv / apply

`apply_batch` first run: 76 proposals → **32 accept** (green, 8 named-vessel rows), **44 hold** (yellow, await review), **0 reject**, **2 conflicts**. Edit the holds in `decisions.csv` and re-run `apply_batch` to finalize. Apply (offset-proof): paste `apply_rows.csv` over matching backend rows, or run `tools/apply_patch.gs` on `apply_patch.csv` (DRY_RUN first). Then `python scripts/verify_apply.py --batch <dir> --pull`.

**Apply safety verified offline:** every accepted change is a pure `[ref]`-cell append — `apply_patch.csv` and `apply.json` touch only `… [ref]` columns; diffing `apply_rows.csv` against the live backend shows **0 value-column changes, 32 `[ref]` changes**, and IGU is **first** in every appended cell.

## Tooling shipped with this batch

The corroborate type reuses the data-fill pipeline. Changes (commit alongside this batch):
- **`scripts/derive_corroborate.py`** (new) — selects priority cells whose `[ref]` is *exactly* the IGU url and whose value is non-blank, within `--rows X-Y`; emits `work/data_fill.json` (empty `fills`, `scope.igu_url`) + `work/research_tasks.json` clustered. Modeled on `derive_fills.py`.
- **`scripts/merge_fills.py`** — for `prev_state == "corroborate"`: IGU is excluded from research `new_urls` (so the gate never tests it) then re-prepended first; requires ≥2 surviving corroborators (`corroboration: "full"`), else `"partial"` (keep IGU + survivors, log a finding, never drop the value). Partial findings use `_conflict_row`-compatible keys so `conflicts.csv` is populated.
- **`scripts/apply_batch.py`** — `ref_only` flag on corroborate fills guards the value-column write, so a corroborate accept emits only a `set <field> [ref]` patch; the value column is never written and never enters `accepted_cells`.
- **`scripts/build_workbook.py`** — excludes `prev_state == "corroborate"` fills from `data_fill_by`, so the value cell stays gray (untouched) while the `[ref]` cell shows peach (existing IGU kept first + corroborator appended). Reuses `--mode data_fill`; no new mode.

## ⚠ Process gotcha discovered (applies to data-fill too)

`merge_fills.py` globs **all** `work/research_*.json`. `work/` is gitignored and persists
between batches, so the first merge here silently pulled in **6 stale research files from
the 2026-06-04 data-fill batch** (133 fills / 31 spurious gate-drops). Fix applied:
archived them to `work/_stale_research_pre_corroborate/` and re-ran. **Recommended standing
step: clear `work/research_*.json` at the start of every data-fill / corroborate batch**
(after `derive_*`, before the research fan-out). Worth a small `--clean` guard in a future
batch if it recurs.

## Rollout note

Pilot supports ~50–80 rows/batch at the user's ~2-batches/day cadence (~14–20 batches for
the remaining ~1,056 rows). Partial cells (IGU + 1 corroborator) accumulate into a follow-up
sweep rather than blocking a batch. Placeholder-hull Name cells should likely be dropped from
scope in the selector for future batches (they can never corroborate) — flagged for the user.
