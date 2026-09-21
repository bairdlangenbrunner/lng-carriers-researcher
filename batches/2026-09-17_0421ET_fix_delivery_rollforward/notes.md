# Fix — delivery roll-forward (on-order rows vs shipvault), 2026-09-17

**Batch:** `2026-09-17_0421ET_fix_delivery_rollforward`
**Mode:** `build_workbook.py --mode fix`, every ref pre-gated (§3.8c) and re-gated at build (0 dropped)
**Rows:** 151 live rows, 224 cells (141 / 214 before the marinetraffic.org cross-check, see the last section)
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

54 rows were deliberately NOT proposed (45 from the overnight run, 9 added by the marinetraffic.org cross-check):

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
is pre-filled by confidence: 186 G cells accept, 38 Y cells hold (143 / 71 before the marinetraffic.org cross-check) — flip the holds you agree with
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

## marinetraffic.org cross-check (added 2026-09-17 afternoon)

vesselfinder firewalled our IP part-way through the overnight sweep, so 176 on-order IMOs (live rows
973-1181, mostly 2027+ deliveries) never got the AIS cross-check, and every claim on
them stayed shipvault-only (Y). The 95 of those that are named or deliver in 2027 were re-checked on
marinetraffic.org through `scripts/sweep.py` (10 s +/- 3 s per request, circuit breaker armed):
95/95 answered 200, no throttling (`work/sep17/marinetraffic_sweep.jsonl`). The other 81
(backend placeholders not due before 2028) were swept in a second run the same evening - see the
last bullet. The bullets before it describe the first run.

- **19 Name cells Y -> G.** marinetraffic.org independently lists the IMO under the same name, and its
  page passed the §3.8c gate, so it is now cited as a second source next to shipvault: live rows
  973-987 (the QatarEnergy Hudong series, `Al Ghuwair` ... `Ezhara`), 999 `Al Sabsab`, 1008
  `Alliance Venture`, 1013 `Elisa Halcyon`, 1080 `Friendship Venture`.
- **3 Status + 3 Delivery-year cells Y -> G**: live rows 1005 `Clean Rio Grande`, 1006 `Clean Texas`,
  1013 `Elisa Halcyon` - marinetraffic.org shows each with a real MMSI (AIS-registered). Cross-check
  only, **not cited** on these cells: the page does not state a delivery, so it cannot corroborate
  `active` or a year.
- **9 new Name cells (Y, hold)** where shipvault still carries a hull placeholder and
  marinetraffic.org is the only source: live rows 988 `Diamond Gas Nexus`, 989 `Grace Himawari`,
  990 `Grace Gerbera`, 991 `Ferdy Vanguard`, 1000 `Al Fanar`, 1007 `Prime Creativity`, 1012
  `Prime Unity`, 1014 `Solidarity`, 1079 `Prime Glory`.
- **7 rows added to `manual_review.json`**: shipvault says ON ORDER but marinetraffic.org shows a
  named ship with an MMSI - live rows 973, 988, 999, 1000, 1002, 1015, 1080. Probably on sea trials
  or just delivered; needs a press check before Status moves. Row 973's MMSI (538000000) looks like
  a placeholder, so treat that one as the weakest.
- No disagreements: where both sites name a ship, the names match on all 24 rows.
- All 28 marinetraffic.org URLs passed the gate (`OK (cf_clearance)`, appended to `gate_log.json`);
  the workbook was rebuilt with tracker-host gate calls paced, 0 refs dropped, recalc zero errors.
  `decisions.csv` had no hand edits, so it was regenerated from the new confidences: **168 accept /
  55 hold** (Name 79 / 36, Status 63 / 0, Delivery year 26 / 19).
- **Second run, the remaining 81 IMOs (same evening).** 81/81 answered 200, no throttling. 19 of
  them carry a real name on marinetraffic.org - the QatarEnergy series at Hanwha, Samsung and
  HD Hyundai, named years ahead of a 2028 delivery; the other 62 show only yard / hull labels.
  **18 more Name cells Y -> G** with the gated marinetraffic.org page as a second ref next to
  shipvault: live rows 1017-1024, 1031-1037, 1043, 1057, 1058 (`Al Nasraniya` ... `Al Wa'ab`).
  **1 new Name (Y, hold)**: live row 1039 `Libsayer`, where shipvault still has the hull number.
  19/19 URLs passed the gate. Two of the 18 already show an MMSI despite the 2028 delivery (live
  rows 1017 `Al Nasraniya`, 1033 `Lekhraib`) - added to `manual_review.json` as low priority
  (probably an MMSI assigned early). Totals after both runs: **224 cells / 151 rows, 186 accept /
  38 hold** (Name 97 / 19, Status 63 / 0, Delivery year 26 / 19); 37 names Y -> G, 10
  marinetraffic.org-only names on hold, `manual_review.json` 54, 47/47 marinetraffic.org URLs
  passed (`gate_log.json`, 263 entries). Workbook rebuilt paced, 0 refs dropped, recalc zero
  errors; `decisions.csv` again had no hand edits and was regenerated. All 176 IMOs vesselfinder
  missed have now had an AIS-site cross-check.

## Second source for the rolled-forward years (added 2026-09-21, RF rev 25 §4.18)

Baird, reviewing live row 828: a proposed delivery delay should carry at least one ref besides
shipvault, and IGU 2026 is a good backup where it agrees. `add_igu_second_ref.py` (this directory)
looks each of the 19 roll-forwards up by IMO in `work/igu_fleet_2026.json`:

- **12 rows Y -> G** — IGU 2026 Appendix 4 prints the same year (2027); the report PDF is added after
  the shipvault refs: live rows 833, 835, 876, 881, 882, 883, 898, 906, 917, 918, 919, 922.
- **5 rows stay Y, no second source** — live rows 828-832 (Zvezda hulls 046-050, Smart LNG): IGU 2026
  still prints **2026** for these (its schedule is as of end-2025 — not a disagreement, just no help;
  row 828 is *not* 2027 in IGU, PDF p.78). A press / database search found nothing hull-level for the
  sanctioned Arc7 series (`second_ref_search.json`).
- **Row 836 (Zvezda hull 054) stays Y** — shipvault says 2028, IGU 2027. Both later than the
  backend's 2026; nothing found to settle which.
- **Row 933 (`Dalian No 1 G175K-4`) stays Y, second ref added** — Maritime Optima prints `SEA ARGOSY
  built in 2027` for IMO 9989120 (gate PASS). Not moved to G: the row is in `manual_review.json`
  (vesselfinder had it AIS-live, and Maritime Optima lists an MMSI, callsign and flag), so Status may
  be the real question. `Sea Argosy` is shipvault's and Maritime Optima's name for it — a Name lead.

## Delivery history cells (added 2026-09-21, RF rev 25 §4.19)

Baird added three columns to the sheet — `Delivery delayed`, `Previous delivery year(s)`,
`Previous delivery year(s) [ref]` — and `python scripts/delivery_history.py --batch <this dir>`
(new) adds the history to every Delivery year cell that moves the year **later**: the 19
roll-forwards. The other 26 Delivery year cells are actual deliveries that moved the year earlier
or kept it — not delays, nothing added.

- **19 × `Previous delivery year(s)` = `2026`** and **19 × `Delivery delayed` = `yes`**, each at its
  Delivery year line's confidence (12 G / 7 Y) and **decided together with that line** — never
  accept the history where the year change is held or rejected.
- **Refs for the former year:** the IGU report PDF wherever an IGU extraction prints 2026 for the
  IMO (17 rows; row 933 has both the 2025 and 2026 editions). Live rows **835 and 836: `[ref]`
  blank** — IGU prints 2027 and no existing ref prints 2026 as a delivery year. The rows' old
  `Delivery year [ref]` URLs were asked too; none states 2026 as a delivery year (one Riviera
  article passed the plain gate on a sidebar date — hence the same-sentence check in the script).
- Totals now **262 cells / 151 rows** (Name 97 G / 19 Y, Status 63 G, Delivery year 38 G / 7 Y,
  Previous delivery year(s) 12 G / 7 Y, Delivery delayed 12 G / 7 Y). Rebuilt paced: 0 refs dropped, recalc zero
  errors. `decisions.csv` had no hand edits (no `review_log.jsonl`), so the 12 upgraded Delivery year
  lines moved from their stale Y default to `accept` with their history lines: **222 accept / 40 hold**.
- Tooling follow-up: a bare year passes §3.8c on any page with a dated sidebar (and any long PDF).
  That affects every Delivery year gate in the repo, not only this batch; `delivery_history.py`
  has the stricter `states_delivery_year`, the main gate does not yet.
