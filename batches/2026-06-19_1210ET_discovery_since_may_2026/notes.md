# Discovery batch — since-May-2026 catch-up sweep

**Date:** 2026-06-19 12:10 ET
**Mode:** discovery (date-window sweep)
**Scope (confirmed with user, Discovery SOP §2):**
- Gap window: **2026-05-01 → 2026-06-19** (backend's latest contract date at pull: 29-May-2026)
- Yard coverage: **all yards** (7 main + 14 secondary)
- Proposed threshold: **default** (named owner + specific count + delivery window)
- FSRU handling: **batched in** with conventional LNGCs
- Output: default `batches/<dir>/lng_carrier_candidate_vessels.xlsx`

**Output:** `lng_carrier_candidate_vessels.xlsx` — **1 candidate (C1), confidence Yellow.**

## Headline result

The backend is **very current** — the user has already entered the entire May-2026
leading edge and even the early-June orders. After full four-ring reconciliation, only
**one** new vessel sits past the backend's edge: a single Samsung HI LNG carrier disclosed
08-Jun-2026 for an unidentified owner. This is a normal small leading-edge outcome (cf. the
SOP operational tip that CSB's edge lags the contract front by ~weeks).

## The one candidate — C1 (Yellow)

**Samsung Heavy Industries, 1× LNG carrier, unidentified owner, contract 08-Jun-2026.**
- Status `on order`; Shipbuilder `Samsung Heavy Industries`; Contract date `08-Jun-2026`;
  Delivery year `2029` ("by January 2029"); Price `252000000` (USD; 385.5 bn won / ~$252m).
- **Shipowner = `unknown`.** Samsung's DART single-supply-contract disclosure names only an
  "Oceania region" shipping company; LNG Prime reports a "Bermuda-based owner" and that the
  order was **linked to Purus Marine** but that it "could not verify this immediately." Purus
  already has a 2026 Samsung series in the backend (1× 20-Mar, 2× 22-Dec-2025), so a 4th
  Purus hull is plausible — but unconfirmed, so the owner stays `unknown` rather than asserting
  Purus.
- **Blank on purpose:** Capacity, Propulsion type, Vessel type, Operator/charterer, Name/Hull/IMO
  (+ their refs) — not disclosed / not yet assigned. (Vessel type left blank to match the
  existing May-2026 on-order Samsung rows.)
- Yard-location block autofilled from the existing Samsung HI backend row (§6.7).
- **Count note:** asiae + the DART disclosure say **one** vessel; the 385.5bn-won value matches
  a single 174k-class hull (~$250m, in line with the May-2026 cluster prices). Riviera's
  headline says "two" — appears to conflate Purus's earlier Samsung pair. Treated as **one**.

**Why Yellow, not Green:** the contract event / yard / value / delivery are well-sourced
(primary DART coverage + LNG Prime), but the owner identity is unidentified/contested and the
count had a minor cross-source discrepancy (Discovery SOP §4.8 yellow definition).

## Ring-by-ring coverage

- **Ring A (CSB, all 21 yards swept):** LNG/FSRU leading edge on CSB is **March 2026** — zero
  LNG/FSRU contracts indexed ≥ 2026-05. Backend already extends to 29-May, so CSB confirms
  nothing is missing on its indexed front. Secondary yards (Zvezda 14 LNG rows, DSIC 2, COSCO
  yards, Japanese yards) yielded **0** new in-window vessels — consistent with prior pilots.
- **Ring B (regulatory):** DART/en.sedaily/asiae, KIND, Bursa, HKEX/SSE. Surfaced the 08-Jun
  Samsung order (C1). All other Korean-yard May disclosures map to existing backend clusters.
- **Ring C (trade press):** LNG Prime, Splash247, TradeWinds, Riviera, Seatrade, Offshore
  Energy, gCaptain, IndexBox. Corroborated C1; everything else resolved to existing rows.
- **Ring D (charterer programs + GTT + FSRU):** **Zero** qualifying proposed candidates
  (QatarEnergy resurfaced 2024, Venture Global hedged, Excelerate hinted — all fail the 3-part
  threshold). No new-build FSRU orders in window (only conversions, out of scope). GTT
  tank-design releases all cross-checked to existing orders (see below).

## Reconciled against backend — already present, NOT re-reported

- **COSCO 4× Jiangnan 175k (Shell 7-yr charter, 02-Jun-2026, ~$953m):** already 4 rows in
  the backend. ✔
- **MISC 1× FSRU Samsung 170k (Petronas Gas, 04-May-2026):** already in backend, correctly
  typed `FSRU`. ✔ (No vessel-type flag needed.)
- **Sonangol 2× HD Samho 174k (07-Apr-2026):** already in backend; the GTT 28-May tank-design
  release is the design announcement for that April order — out of window, not new. ✔
- **GTT "Greek owner" 2× Samsung (09-Jun)** → tank design for the existing **TMS Cardiff**
  14-May order. **GTT "European owner" 1× Hanwha (28-May)** → existing **Knutsen** order.
  Neither is a new cluster — GTT releases lag the shipowner-yard contract by 1–3 quarters
  (Discovery SOP §3.4 Ring D).
- Out-of-window / resurfaced and correctly excluded: Maran Gas 2× Hanwha (Mar 2026), Alpha Gas
  2× Hanwha (Jan 2026), Cheniere/NYK option (Feb 2026), QatarEnergy QC-Max steel-cutting
  (construction milestone, not a new order), Yangzijiang "first LNGC" (charter of existing
  hull), K Line LNG-fuelled car carriers (out of scope), all Russian (Zvezda — deliveries/
  launches only, no new contract).

## §3.8 URL verification

| URL | Result | Checked for |
|---|---|---|
| asiae.co.kr/en/article/IT/2026060809373146202 | **PASS** | Samsung; 385.5; Oceania; LNG |
| lngprime.com/.../samsung-heavy-clinches-another-lng-carrier-order/188654/ | **PASS** | Samsung; LNG; 2029; Bermuda; 252 |
| tradewindsnews.com/.../purus-linked-to-lng-carrier-order.../2-1-2000639 | **PASS** | Purus; Samsung |

TradeWinds verifies but is **not cited in any data cell** (it supports only the unverified
Purus owner attribution; owner left `unknown`). asiae did not contain "2029" or "252", so
Delivery-year and Price cite **LNG Prime only** (the source carrying those value strings) —
keeping each ref value-corroborating.

## Backend QC at pull

`qc_backend.py` on the fresh pull: 31 findings (2 MED orphan-ref, 29 LOW name-drift/ordinal),
all pre-existing from the 06-18 QC normalization pass — none in this batch's discovery scope.

## Promotion

Candidate is additive. Copy the backend-column range (after the 4 prefix columns) into one new
backend row. Owner is `unknown` pending identification (likely Purus — reconcile if confirmed,
distinct from the 27-May unknown Samsung row and the existing Purus/Samsung rows).
