# 2026-09-22 22:08 ET — fix: shipvault hull numbers and delivery years

Mode: `fix`. Source: `fix.json` (copied in place; `build_workbook.py --mode fix` stamps the
computed §5 grades back into it).

## Where this came from

Baird, 2026-09-22: "for al seej, you seem to have missed that the owner is no longer misc but
now nakilat, according to shipvault?" The answer for that row was no (the backend's MISC is
right; shipvault's `owner` is the commercial counterparty on a program fleet — see the
`data/source_roster.md` change committed with this batch), but the question exposed a real
gap: a shipvault record cited for one cell had never been compared against the row's other
cells. So the whole backend was swept — every one of the 212 rows citing a
`shipvault.com/ships/{id}` page, each record re-fetched and compared field by field against
the row (`work/shipvault_owner_scan.json`, gitignored).

Of 335 comparable value cells, 15 disagreed; most are our own placeholder conventions. Five
real defects survived triage, and they are this batch.

## What is proposed

| live row | row_id | cell | backend | proposed | grade |
|---|---|---|---|---|---|
| 1054 | 178 | Name, Hull number | `Hull 3301 (HDHHI)` | `Hull 3501 (HDHHI)` | G |
| 1075 | 314 | Name, Hull number | `Hull Unknown 01 (HSHI)` | `Hull 8327 (HSHI)` | G |
| 1076 | 315 | Name, Hull number | `Hull Unknown 02 (HSHI)` | `Hull 8328 (HSHI)` | G |
| 1076 | 315 | Delivery year | `2028` | `2029` | Y |
| 1077 | 316 | Name, Hull number | `Hull Unknown 03 (HSHI)` | `Hull 8329 (HSHI)` | G |
| 1077 | 316 | Delivery year | `2028` | `2029` | Y |

Companions (RF §4.19, `delivery_history.py`, decided with their Delivery year line): rows 315
and 316 get `Previous delivery year(s)` = `2028` and `Delivery delayed` = `yes`, both Y.
`other_names.py` proposed nothing — all four Name changes are placeholder → placeholder, which
§4.16 explicitly does not carry into `Other names`.

Live row 1054 is the sharpest case: the cell's **own** cited record (unit 477422, IMO 1066568)
gives yard no. 3501 at HD Hyundai Ulsan. The backend's `3301` contradicts the ref pinned to it —
a §3.8c conflict resolved the way §3.8c says to resolve it, by changing the value.

Hull tag `(HSHI)` for HD Hyundai Samho and `(HDHHI)` for HD Hyundai Heavy Industries are the
established backend forms (QC §2 / RF §4.17); 32 other Samho rows already use `(HSHI)`.

## What was checked and NOT proposed

- **Live row 937, Al Sadaf (IMO 9972957), Delivery year.** The sweep read shipvault's
  `built: 2026` against the backend's `2025`. It is not a defect: the same record gives
  `delivered: 2025-12-10`, and the IGU 2026 fleet table prints delivery year **2025** for that
  IMO (`work/igu_fleet_2026.json`, p. 77). The backend stands.
- **Live row 1078, row_id 317 (`Hull Unknown 04 (HSHI)`).** Its shipvault record (unit 490167)
  carries no hull number — `name: "HULL 4"`, `yardno: "NA"`. The placeholder stays.

## Open items for Baird

- **Possible duplicate cluster.** Rows 1075–1078 (Capital Maritime & Trading Corp, HD Hyundai
  Samho, on order, $257.0m) and rows 1115 / 1149 / 1150 (`HD Hyundai Samho (Capital Clean ECC
  1/2/3)`, on order, $256.5m, delivery 2028 / 2029 / 2029) look like the same order entered
  twice — Capital Clean ECC is Capital's LNG-carrier vehicle, the yard is the same, and the
  delivery pattern matches once rows 1076/1077 move to 2029. Four rows vs three. Flagged only:
  rows are never deleted by a batch, and a duplicate is yours to remove by hand.
- **Blank cells these records could fill** (out of the scope you named, so not proposed):
  IMO for rows 1054 (1066568), 1075 (1130773), 1076 (1130785), 1077 (1130797), 1078 (1130802);
  Capacity 174,000 cbm on all five. Say the word and they go in a data-fill batch.

## Tooling change committed with this batch

`scripts/confidence.py` — `_host()` now folds the shipvault unit-record host
(`shipvaultapi-….ondigitalocean.app`) onto `shipvault.com`. The companion ref (RF §6a.8 rev 21)
is the same source as the page it sits beside, but it was counting as a second independent host
in `live_hosts()`, which silently disarmed the RF §4.18 roll-forward carve-out: rows 315/316
graded **G** on shipvault alone before the fix and **Y** after, which is what §4.18 says they
are. `tests/test_confidence.py` passes (41).

`data/source_roster.md` — the shipvault bullet now says its `owner` is never a `Shipowner` ref
on a program fleet, with the sweep's numbers.

## Verification

- §3.8c gate: 14 cells, **0 refs dropped**. Every ref is a live shipvault unit record keyed to
  the vessel (`OK (cf_impersonate, shipvault_api)`).
- `shipvault_api_refs.py --batch`: 4 pages cited, all 4 render blank, 10 companion refs added,
  0 skipped.
- `recalc.py`: zero formula errors across 3 sheets.
- `apply_batch.py`: 14 proposals → 8 accept (the Green Name / Hull number lines), 6 hold, 0
  conflicts.

## Apply

The 8 Green cells were written to the backend in-session on Baird's direction (AP §2d) —
"if they are high confidence (green) you can go ahead and make the changes yourself, otherwise
you can leave them for review" (2026-09-22). Pre-write values are in `revert.csv`, the write is
logged in `push_log.jsonl` under `reviewer: "claude session (directed)"`, and no
`review_log.jsonl` record was written for them: they are correctly still `unclicked` to §2b.
The 6 Yellow delivery lines were left for review.
