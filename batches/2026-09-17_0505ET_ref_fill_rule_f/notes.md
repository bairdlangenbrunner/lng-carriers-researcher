# Rule-F [ref]-fill — whole backend (2026-09-17, sep-17-pass)

Scope: every cell in the fresh 2026-09-17 pull where a data value is filled but the paired
`[ref]` is blank (RF §4.13 Rule F). 19 such cells: Vessel type 10, Capacity 5, Hull number 3,
Shipowner country/area 1. Sourcing was mechanical (shipvault unit record for the row's IMO,
then refs already cited elsewhere on the row), every URL through the §3.8c value↔ref gate.

## Proposed (8 cells, all Y — single-source shipvault)

| live row | row_id | cell | value | ref |
|---|---|---|---|---|
| 6 | 415 | Capacity [ref] | 126750 | shipvault.com/ships/73086 |
| 7 | 663 | Capacity [ref] | 126750 | shipvault.com/ships/73085 |
| 61 | 969 | Capacity [ref] | 135000 | shipvault.com/ships/113754 |
| 487 | 1044 | Capacity [ref] | 174000 | shipvault.com/ships/373877 |
| 488 | 1045 | Capacity [ref] | 174000 | shipvault.com/ships/373876 |
| 771 | 121 | Hull number [ref] | Hull 2651 (SHI) | shipvault.com/ships/450944 |
| 775 | 226 | Hull number [ref] | Hull 8102 (HDHHI) | shipvault.com/ships/448545 |
| 776 | 230 | Hull number [ref] | Hull 8181 (HDHHI) | shipvault.com/ships/461187 |

Y, not G: one source each. The workbook sheet holds only these 8 rows (built against a
filtered copy of the pull so the sheet is reviewable); `citations.json` is keyed by row_id.

## Negative results (11 cells, still Rule-F orphans) — `unfilled_negative_results.json`

- **Vessel type = `conventional`, 10 cells** (live rows 61, 487, 488, 994, 1118, 1172,
  1182–1185). The one source that prints this value is the IGU World LNG Report fleet table
  (Appendix 3, "Type" column), and none of these ten is listed there — checked by IMO and by
  name against the 2025 and 2026 editions (live row 61, Puteri Delima Satu, IMO 9211872, is
  absent; the IGU 2025 entry "Puteri Delima" is IMO 9030814, live row 25, already IGU-reffed).
  Tracker pages and press do not use the word, so the hard corroboration gate cannot pass it. Needs a
  rule decision (same open question as the cargo/vessel-type derivation rule): either allow
  a capacity-derived Vessel type to stand on the Capacity ref, or leave these unreffed.
- **Shipowner country/area = `China`, live row 652** — the only passing refs were the IGU
  report landing page and a shipyards.gr yard page, which mention China generically, not the
  owner's domicile. Dropped as too weak; needs an owner profile page.

## Gate

67 URL checks logged in `citations.json` → `qa_log`. Recalc: zero formula errors.

## Shipvault companion refs (added 2026-09-17, RF rev 21 §6a.8)

Most `shipvault.com/ships/{id}` pages render blank in a browser (the site cannot parse its own
double-encoded API answer), so a reviewer cannot see the value the gate verified. Every ref citing
such a page now carries the unit-record URL
`https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}` as a second ref right after it:
**7 companions added, 0 skipped** (`shipvault_api_refs.json`). Source JSON patched with
`scripts/shipvault_api_refs.py`, workbook rebuilt + recalced (zero errors), apply artifacts
regenerated; decisions unchanged, and the only diff in `apply.json` / `apply_rows.csv` /
`apply_patch.csv` is the added URLs.

## IGU report PDF as the second source on the three hull cells (rebuilt 2026-09-21)

The first build asked the IGU 2025 **landing page** for the hull numbers, failed it (it prints no
per-vessel value) and left the three Hull number cells at Y on shipvault alone. The landing page
stands for the report PDF (IG §1 rev 5), and the PDF is now checked **by the row's IMO** against
the coordinate extraction (`scripts/igu_refs.py`), not by a text search:

| live row | row_id | IMO | Hull number | IGU 2025 prints | IGU 2026 prints | refs added |
|---|---|---|---|---|---|---|
| 771 | 121 | 9988700 | Hull 2651 (SHI) | Hull 2651 | Hull 2651 | 2025 + 2026 PDF |
| 775 | 226 | 9946362 | Hull 8102 (HDHHI) | Hull 8102 | Zoe Knutsen (8102) | 2025 + 2026 PDF |
| 776 | 230 | 9972218 | Hull 8181 (HDHHI) | Hull 8181 | Amaryllis Knutsen (no hull) | 2025 PDF |

Two independent sources → **Y → G** on all three (default `accept`; the reviewer's `hold` is
kept until re-decided). The five Capacity cells stay Y: neither edition lists their IMOs.

The `China` PASS on the landing page (live row 652, Shipowner country/area) was a false pass —
IGU prints no such column; `qa_log` now records it as FAIL. The cell was already dropped, so
nothing proposed changes. Workbook rebuilt against a filtered copy of the 2026-09-21 pull,
recalc zero errors, apply artifacts regenerated; no `decision` cell changed.
