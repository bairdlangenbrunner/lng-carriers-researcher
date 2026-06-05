# Correction — rows 1216 / 1217 (Hull CMHI-282-07, -08)

**Date:** 2026-06-04
**Trigger:** user flagged these two Celsius Shipping / China Merchants (CMHI) hulls — "data cells look wrong."
**Nature:** column-offset corruption from a copy/paste, **not** a research error. Every real
value was present but landed in the wrong column. Output is a candidate for human review
(SOP §4.7) — the backend is **not** edited by this batch.

## What was wrong — two distinct offsets

**Offset 1 — stray Capacity/Cargo duplicate in the Yard-location columns (cols 22–26).**
The Capacity/Cargo block (`176400 / cbm / [ref] / membrane / [ref]`) was pasted a second time,
5 columns to the left, into the geolocation columns:

| Column | Held (wrong) | Should be |
|---|---|---|
| Yard location latitude | `176400` | blank |
| Yard location longitude | `cbm` | blank |
| Yard location plus code | `…csb, deltamarin` | blank |
| Yard location accuracy | `membrane` | blank |
| Yard location lat/lon [ref] | `…deltamarin, imarinenews` | blank |

The correctly-placed copy at cols 27–31 (Capacity / units / ref / Cargo / ref) is intact and was
left as-is. CMHI yard-location is blank for the backend siblings (251–256), so the correct value
here is blank, not a researched coordinate (geolocation is out of scope — SOP §4.8).

**Offset 2 — the whole tail (Vessel type → Contract date) shifted +5 columns right.**
Each value sat one logical field too far right, so propulsion landed in Operator, delivery year
landed in Contract date, and the `[Original source]` tag landed in Price:

| Value | Was in (wrong) | Corrected to |
|---|---|---|
| `conventional` | Delivery year [ref] | **Vessel type** |
| `ME-GA` | Operator/charterer | **Propulsion type** |
| `2028` | Contract date | **Delivery year** |
| `Clearlake Shipping` | Price currency | **Operator/charterer** |
| `01-May-2024` | (trailing col 46) | **Contract date** |
| `Claude - agentic workflow new discovery - May 2026` | Price | **[Original source]** |

After the shift, each value's trailing URL re-pairs with it as the correct `[ref]`, and
Price / Price currency / Price [ref] become blank — consistent with the 2026-06-04 data-fill
batch documented blank ("order value never disclosed; sources explicitly say so").

## Corrected values (both hulls identical except hull/name)

| Field | Value | [ref] |
|---|---|---|
| Capacity | `176400` *(see flag below)* | csb, deltamarin |
| Capacity units | `cbm` | — |
| Cargo type | `membrane` | deltamarin, imarinenews |
| Vessel type | `conventional` | csb |
| Propulsion type | `ME-GA` | offshore-energy, lngprime |
| Delivery year | `2028` | csb |
| [Original source] | `Claude - agentic workflow new discovery - May 2026` | — |
| Operator/charterer | `Clearlake Shipping` | splash247, lngprime, offshore-energy |
| Contract date | `01-May-2024` | csb |
| Price / currency / [ref] | *(blank — undisclosed)* | — |

Propulsion `ME-GA` matches sibling rows 251–256 (also ME-GA), a good cross-check.

## Flags for the reviewer

1. **Capacity 176400 vs 180000.** This correction preserves the in-place `176400` (CSB / Deltamarin
   98%-figure). The 2026-06-04 data-fill batch recommended **`180000`** for these rows (Green) for
   consistency with siblings 251–256, noting Deltamarin states "180,000 cbm, or 176,400 cbm at 98%"
   — same vessel, not a conflict. **Your call** which figure the backend should carry; if 180000,
   also swap units source per that batch. This is a value choice, kept out of the structural fix.

2. **Soft-blocked refs (kept, not deleted — SOP §3.8a).** `splash247.com` (HTTP 403) and
   `deltamarin.com` (HTTP 000) are Cloudflare-blocked from the verifier environment. The other four
   refs (CSB, LNG Prime, offshore-energy, imarinenews) PASS §3.8 and corroborate every value, so the
   blocked URLs are retained as supporting citations.

## How to apply

`corrected_rows.csv` holds the two rows in exact backend column order (header + 2 data rows). In the
Google Sheet, overwrite rows 1216 and 1217 with these — or apply the cell moves in the two tables
above. Do not paste into `work/backend.csv` (regenerated each pull).
