# Discovery batch — CNOOC/CMES/NYK JV roster completion (Hudong-Zhonghua)

**Date:** 2026-06-05 15:09 ET
**Mode:** discovery (targeted roster completion, not a date-window sweep)
**Output:** `lng_carrier_candidate_vessels.xlsx` (3 candidates, all Green)

## Why this batch exists

Started from a vessel-identity question on the existing `unknown` row at **sheet row 1087
(row_id 1092)** — a 174,000 cbm X-DF newbuild at Hudong-Zhonghua, owner `CNOOC, CMES, NYK
JV`, sourced to the IGU 2025 World LNG Report. Research established:

1. The row belongs to the **CNOOC + CMES + NYK tri-party JV** that ordered LNG carriers at
   Hudong-Zhonghua (contracts signed 2 May 2022; chartered to CNOOC Gas & Power Singapore;
   managed by OPearl LNG Ship Management).
2. That JV is **firmly six vessels, all 174,000 cbm, all at Hudong-Zhonghua** — six
   single-ship companies (NYK PR, Offshore Energy, gCaptain, Maritime Executive: "$1.26bn,
   China's largest LNG carrier order").

The backend already held **3** rows for this JV: two identified hulls (**H1889A / IMO
9994319** at sheet 275, **H1890A / IMO 9994321** at sheet 276) plus the one anonymous
placeholder (sheet 1087). To reach the firm count of six, this batch adds **3 placeholder
candidates** (C1/C2/C3) for the remaining unidentified slots. Firm-order placeholders are a
standard, in-scope pattern for this tracker (Discovery SOP §1, §5.2 — for a freshly-ordered
hull the yard hasn't named yet, Name/Hull/IMO stay blank; the populated data cells carry the
citations).

Final picture once promoted: 6 rows = H1889A + H1890A (identified) + sheet-1087 placeholder
+ C1 + C2 + C3.

## What each candidate carries

Mirrors the existing JV rows exactly, minus the unknown identity cells:
- `Status` = on order
- `Shipowner` = `CNOOC, CMES, NYK JV` (comma form, matching H1889A/H1890A)
- `Shipbuilder` = Hudong-Zhonghua Shipbuilding
- `Capacity` = 174000 / units cbm
- `Propulsion type` = X-DF
- Yard-location block (country + lat/lon/plus code/accuracy + refs) autofilled from the
  existing Hudong row by `build_workbook.py` (§6.7).
- **Blank on purpose:** `IMO number`, `Name`, `Hull number` (+ their refs) — not publicly
  assigned/indexed yet. `Delivery year` — program delivers 2026-2027 and the two identified
  sisters are 2026, but the unidentified hulls' individual years are **not separately
  sourced**, so left blank (do not assume 2026). `Operator/charterer`, `Vessel type`,
  `Contract date` left blank to match the existing JV rows.

## Confidence: Green

`gcaptain.com/nyk-orders-six-lng-carriers-...` carries **every** cell value verbatim
(174,000 / Hudong / CNOOC / NYK / CMES / X-DF) in one source, corroborated by the **NYK 2022
primary press release** and **Offshore Energy** (JV structure). Multiple cross-checked
sources incl. a primary owner PR → Green per Discovery SOP §6.3.

## §3.8 URL verification

| URL | Result | Checked for |
|---|---|---|
| gcaptain.com/nyk-orders-six-lng-carriers-for-long-term-charter-to-cnooc/ | **PASS** | 174,000; Hudong; CNOOC; NYK; CMES; X-DF |
| nyk.com/english/news/2022/20220502_01.html | **PASS** | Hudong; CNOOC; LNG |
| offshore-energy.biz/cnooc-nyk-and-cmes-agree-to-set-up-lng-carrier-joint-venture/ | **PASS** | CNOOC; NYK; CMES; joint venture |
| splash247.com/nyk-orders-six-lng-carriers-at-hudong-zhonghua-for-cnooc-charter/ | FAIL (HTTP 403) | — | environment-blocked; **not cited** in any cell (kept for reference per §3.8a) |

## Flags / watch items

- **Row 1087 is treated as the 1st unidentified slot, not a duplicate** of H1889A/H1890A.
  If a future pass resolves a hull/IMO for it, reconcile against H1889A/H1890A first to be
  sure it isn't one of those two re-entered from the IGU report. (The dedupe sweep flags
  1087 vs H1889A/H1890A as MED — that's the expected placeholder↔identified ambiguity, a
  human call, not a confirmed dup.)
- **"12/31/2024" on the JV rows is the `Last updated` stamp, not a contract date.** Contract
  date is blank on every JV row. (Corrects an earlier read of the row.)
- **The earlier MOL "Greenenergy" confounder was avoided.** H1886A = "Greenenergy River"
  (MOL/COSCO/CNOOC JV, IMO block 9961xxx) is a *different* program and is correctly left
  alone; this JV's hulls sit in the 9994xxx IMO block.

## Unresolved (next step to fully identify the 4 placeholders)

Name / Hull / IMO for the four unidentified hulls are not in public databases as of
2026-06-05 (unnamed; not indexed). Resolution path: **Equasis → manager "OPearl LNG Ship
Management"** (lists exactly these six), or a CCS/class-society newbuild register. Both need
a credentialed/human session (they 403'd automated fetch).

## Promotion

Candidate rows are additive — review and paste the backend-column range (after the 4 prefix
columns) into 3 new backend rows. Do not overwrite H1889A/H1890A or sheet 1087.
