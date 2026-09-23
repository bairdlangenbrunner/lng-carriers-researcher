# Shipvault companion refs — existing backend cells

**Date:** 2026-09-17 (11:14 ET)  **Mode:** data_fill workbook, ref-only fills (`prev_state: "corroborate"`)
**SOP:** RF rev 21 §6a.8 (shipvault companion ref), §4.15 (`", "` join), §3.8c gate
**Output:** `lng_carrier_data_fill.xlsx`; apply artifacts in this directory (all 175 set to `accept` in
`decisions.csv` — Baird asked for these additions on 2026-09-17).

## Why

`https://www.shipvault.com/ships/{id}` renders blank in a browser for most units: the site's API
answers with a double-encoded record and the page's own code cannot read it, so every value
(capacity included) shows empty. Our verifier unwraps the record, so the ref passes the gate while a
reviewer sees nothing — found on live row 61 (Puteri Delima Satu, Capacity 135000). The unit-record
URL `https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}` opens with a plain click and
shows the figures, so it goes in as a **second ref** after the page URL.

## What this batch does

The backend has 222 `[ref]` cells citing a shipvault page, in 27 rows / 27 ships (live rows 6, 7,
11, 61, 487, 488, 769, 814, 840, 946, 948, 950, 953, 954, 964, 994, 1004, 1025–1028, 1054, 1059,
1075–1078). All 27 pages render blank today.

- **175 cells get the companion** appended to the existing `[ref]` (nothing removed, no data value
  touched): Status 27, IMO number 24, Delivery year 23, Shipbuilder 20, Price 20, Contract date 18,
  Name 18, Hull number 12, Shipowner 12, Shipowner country/area 1. Live row 61 gets it on all 8 of
  its existing shipvault cells (its 9th, Capacity, is in the Rule-F batch).
- **47 cells get none** (`shipvault_api_refs.json` lists each): 46 because the shipvault record does
  not contain the cell's value, 1 (live row 948 Name) because the pending roll-forward fix rewrites
  that `[ref]` and already carries the companion.

Confidence is Y throughout: page + record are one source; the companion adds readability, not
corroboration.

## The 46 uncorroborated cells — for the (paused) citation rot sweep, not acted on here

These are existing backend refs where the shipvault record — readable or not — does not state the
cell's value, so the page ref itself is not supporting the cell:

- Shipowner country/area (18): live rows 487, 488, 946, 948, 950, 953, 954, 964, 1004, 1025–1027,
  1054, 1059, 1075–1078 — the record has a flag, not an owner country.
- Name (6) / Hull number (5): live rows 11, 1054, 1075–1078 — placeholder names and `Hull Unknown`
  numbers the record cannot state; row 11's record carries a different name form.
- Shipowner (4): live rows 11, 964, 1004, 1028 — stylized owner vs the registered owner on the record.
- Contract date (4): live rows 488 (`9-Mar-2014`), 964 (`17-Jan-2025`), 1027, 1028 (`1-Jun-2024`) —
  the record's `ordered` date differs.
- Shipbuilder (3): live rows 487, 488, 964 — record says `SAMSUNG SHIPBUILDING & HEAVY IND CO LTD`;
  the gate's token match wants "Industries". Likely a wording miss rather than a wrong ref.
- Shipbuilder yard country/area (3): live rows 6, 7, 1004 — not on the record.
- Delivery year (2): live rows 1076, 1077 (`2028`); Price (1): live row 946 (`224`).

## Applying

Use `apply_patch.csv` (cell-level, by name) rather than pasting `apply_rows.csv`: several of these
rows are also touched by the other sep-17-pass batches, and the full rows here are a snapshot of the
backend before those land. Or apply this batch last and re-run `apply_batch.py` after a fresh pull.

## Script changes in this batch

- `scripts/url_verifier.py`: the shipvault adapter also serves the API host (the companion is gated
  on the same record as the page); ISO timestamps render as dates and `newprice` also in $m, so
  Contract date / Price cells corroborate against the record. Tests added (196 pass).
- `scripts/shipvault_api_refs.py`: new (`--batch`, `--backend-batch`).

## Reconciled — 2026-09-21 21:05 ET

172 of 175 lines are in the backend (`verify_apply.py`: 172 landed, 0 mismatch, 0 missing; pushed
2026-09-21 17:04 ET through the review app). Two accepted companion lines were **superseded by
later pushes and set to `reject`** (logged in `review_log.jsonl`, `via: reconcile`):

- live 61, `Shipowner country/area [ref]` — batch 15 (`2026-09-21_2003ET_fix_shipowner_country_refs`)
  replaced the row's country ref with MISC sources; a shipvault page or unit record is never a
  `Shipowner country/area` ref (Data-fill SOP §5), so the companion has nothing to accompany.
- live 814, `Status [ref]` — batch 8 moved Status `active → on order` with the IGU 2026 PDF as
  sole ref (19:35 ET); the shipvault page this companion sat beside is no longer a Status ref, and
  the unit record itself says `active`.


## Directed session write 2026-09-23 (AP §2d)

On Baird's direction ("change the backend for 2 (I approve those), and for 3, put the refs in the backend too"), a session wrote 1 cell(s) straight to the sheet: T6 (Shipbuilder [ref], row 6). Verified on re-pull. Revert file: `directed_2026-09-23_revert.csv`; logged in `push_log.jsonl` as `claude session (directed)`.
