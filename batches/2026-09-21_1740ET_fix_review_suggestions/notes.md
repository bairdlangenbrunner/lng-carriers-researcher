# Fix batch — review-app suggestions, hand-built (2026-09-21, sep-17-pass 14)

One cell. Baird's review-app suggestion of 2026-09-21 17:30 ET on batch 10's line
`2026-09-17_1737ET_fix_other_names_former::509|Other names` (rejected there, suggested value
`Dalian No 1 G175K-12; Youyi Yongshi`), which `review_app/suggestions.py` refused to emit because the
suggestion adds two elements to the cell. Built by hand with a per-ref `gate_value` (`build_workbook.py`
fix mode). `fix` mode, QC §4 / Apply SOP. Row numbers are **live sheet rows** (pull of 2026-09-21,
1,220 rows); `fix.json` and `apply_patch.csv` key on the column-A `row_id`.

## The rule (Baird, 2026-09-21)

> you suggested renaming it to Friendship Venture — which is correct, but Youyi Yongshi is the name of
> the page, so clearly that should be another name in "other names"

An AIS-transmitted / tracker-reported alternate name joins `Other names` beside the former Name,
gated on the tracker page. Codified as [ref]-Fill SOP §4.16 (RF rev 27).

## What is proposed — 1 cell, 1 row: `G` accept

| live row | row_id | IMO | Name (batch 1, accepted) | column | proposed | refs |
|---|---|---|---|---|---|---|
| 1080 | 509 | 1030557 | `Dalian No 1 G175K-12` → `Friendship Venture` | `Other names` (blank) | `Dalian No 1 G175K-12; Youyi Yongshi` | IGU 2025 PDF, IGU 2026 PDF (former Name, by IMO), vesselfinder `/vessels/details/1030557` (AIS name) |

Gate verdicts (`QA_review` sheet): all three PASS, 0 dropped —
- IGU 2025 PDF: prints `Dalian No 1 G175K-12` for IMO 1030557 (coordinate extraction, IG §1).
- IGU 2026 PDF: same.
- vesselfinder: page title / description `YOUYI YONGSHI` (IMO 1030557, MMSI 636025371, Liberia); the
  particulars table prints `FRIENDSHIP VENTURE` as the registered Vessel Name, so one page carries both
  names. shipvault unit 469427 and marinetraffic.org print only `FRIENDSHIP VENTURE`.

`Youyi Yongshi` (友谊勇士) is the Chinese rendering of *Friendship Venture*, the name the vessel
transmits over AIS.

## Decisions

- **Decide with batch 1's Name line** (`0421ET_fix_delivery_rollforward::509|Name`, accepted, not yet
  pushed — RF §4.16 coupling: both or neither).
- Batch 10's own `509|Other names` line stays **rejected**; this batch replaces it. Nothing else in
  batch 10 changes.
- Apply via `apply_patch.csv` (patch path — batch 10 shares the row); the cell is blank in the backend,
  so `OVERWRITE_NONBLANK` is not needed for it. Or the review app's push accepted.

## Lead, not proposed

vesselfinder shows the vessel with a live MMSI (636025371, Liberia) and "Year of Build 2025"; the
backend has Status `on order`, Delivery year `2028`; shipvault says ON ORDER, built 2027-01. An
AIS identity on an on-order hull is usually launch / sea trials. Worth a look when batch 1's roll-forward
rows are revisited (RF §4.18 second source needed for any year change) — not a proposal here.

## Tooling note

`suggestions.py` hands back any suggestion that adds more than one element to a multi-valued cell
("hand-build this cell"). The fix-mode cell already supports it: give each ref its own `gate_value`
(see `fix.json`). Teaching `suggestions.py` to split a two-element suggestion across the original
refs and a URL in the note is a follow-up, not done here.
