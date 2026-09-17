# Fix — delivery roll-forward (on-order rows vs shipvault), 2026-09-17

**Batch:** `2026-09-17_0421ET_fix_delivery_rollforward`
**Mode:** `build_workbook.py --mode fix`, every ref pre-gated (§3.8c) and re-gated at build (0 dropped)
**Rows:** 141 live rows, 214 cells
**Output:** `lng_carrier_fix.xlsx` — apply through the Apply SOP (`batch_digest.py` / `apply_batch.py` artifacts are in this directory)

## Why

The backend had not moved since June 2026. Every `on order` row carrying an IMO (323) was looked up in shipvault (`scripts/imo_tracker.py` API; sweep in `work/overnight/shipvault_sweep.jsonl`) and, until vesselfinder began timing out our IP, in vesselfinder (AIS name / MMSI / year built).

## What is proposed

- **Status `on order` → `active`: 63 rows.** shipvault shows status ACTIVE with a delivered date on or before 2026-09-17. Confidence G where vesselfinder independently showed the vessel AIS-live under a real name with an MMSI (60), Y where shipvault is the only source (3).
- **Delivery year corrected to the actual delivery year: 26 rows** (mostly 2026 → 2025 deliveries), plus **19 undelivered rows rolled forward** from ≤2026 to the year shipvault now schedules (confidence Y).
- **Name: 106 rows** — hull placeholders replaced by the registered name (or a backend spelling corrected), only where shipvault carries that exact spelling. Title-cased; tokens such as LNG stay upper.
- Every proposed cell cites the vessel's `https://www.shipvault.com/ships/{id}` page (the verifier's shipvault adapter corroborates against the unit record). vesselfinder was used as a cross-check only — it is not cited because it could not pass the gate at build time.
- `Last updated` is not touched; set it when applying.

## Needs a human look (`manual_review.json`)

45 rows were deliberately NOT proposed:

- ~26 rows where shipvault still says ON ORDER but vesselfinder showed the ship AIS-live under a real name, built ≤2026 — probably delivered (or on sea trials) with shipvault lagging. Two research agents are confirming these against press; confirmed ones ship in a follow-up fix batch (`*_fix_delivery_confirmed`).
- Name spelling disagreements between vesselfinder and shipvault (shipvault has typos, e.g. CELCIUS GOA / GREENERGY CLOAD). The backend's `Greenenergy …` spelling looks wrong against both (`Greenergy`); left for a decision.
- Row 929 `Alexey Kosygin` (shipvault status SANCTIONED, delivered 2025-12-24) and the other Zvezda / Arctic LNG 2 hulls: status left alone.
- 7 on-order IMOs have no shipvault record.

## Script notes

- `scripts/url_verifier.py`: `value_variants` now renders `DD-Mon-YYYY` dates, accepts past-tense delivery wording for Status `active`, and no longer requires the backend's yard tag on hull numbers (`Hull 2598 (Hanwha)` → `Hull 2598` / `H2598`). Tests added in `tests/test_url_verifier.py`.

## Apply artifacts / script change

`scripts/apply_batch.py` (and so `batch_digest.py`) gained a `fix` mode in this batch: it reads
`fix.json`, and because a fix corrects a non-blank value its gated refs **replace** the paired
`[ref]` instead of being appended (`preserve_ref` cells rewrite the value only). `decisions.csv`
is pre-filled by confidence: 143 G cells accept, 71 Y cells hold — flip the holds you agree with
and re-run `python scripts/apply_batch.py --batch <dir>` before applying.

## Shipvault companion refs (added 2026-09-17, RF rev 21 §6a.8)

Most `shipvault.com/ships/{id}` pages render blank in a browser (the site cannot parse its own
double-encoded API answer), so a reviewer cannot see the value the gate verified. Every ref citing
such a page now carries the unit-record URL
`https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}` as a second ref right after it:
**212 companions added, 0 skipped** (`shipvault_api_refs.json`). Source JSON patched with
`scripts/shipvault_api_refs.py`, workbook rebuilt + recalced (zero errors), apply artifacts
regenerated; decisions unchanged, and the only diff in `apply.json` / `apply_rows.csv` /
`apply_patch.csv` is the added URLs.
