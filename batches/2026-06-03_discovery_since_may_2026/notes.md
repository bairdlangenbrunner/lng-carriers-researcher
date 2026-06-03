# Batch 2026-06-03 — discovery — since May 1, 2026 (gap window 2026-05-01 → 2026-06-03)

**SOP revs at time of batch:** built under RF rev 16 / DC rev 6, then rebuilt 2026-06-03 under **RF rev 17 / DC rev 7** (pointers.md reconciled RF 17 / DC 7 / SR 4). The rev-17/rev-7 changes — owner stylization (RF §4.14), multi-URL `", "` join (RF §4.15), and yard-location autofill (DC §6.7) — were applied to this batch; see Script changes.

**Backend pull:** 1,465,308 bytes, 1210 data rows, header row index 1 (data starts row 2). All 30 expected columns mapped; no schema drift. Full live schema = 46 columns.

## Scope

- **Gap window:** contracts since 2026-05-01. Backend's latest contract date = 14-May-2026; CSB indexed only through 2026-03. So the genuine leading edge investigated was **15-May → 03-Jun-2026** (plus a sanity re-check of early May).
- **Yards in scope:** seven main LNGC yards (samsung, hanwha-ocean, hyundai-ulsan, hyundai-samho, hyundai-mipo, jiangnan, hudong-zhonghua).
- **Mode-specific parameters:** proposed-vessel threshold = default (named owner/charterer + ship count + delivery window); FSRU batched with conventional LNGCs; output dir `batches/2026-06-03_discovery_since_may_2026/`.

## Summary

3 candidate clusters / **6 vessels**, all "on order", all postdating the backend's latest contract (14-May-2026):

- **C1 — Samsung HI, 1 LNG carrier** — undisclosed Bermuda owner (brokers→JP Morgan, unconfirmed), 27-May-2026, $252M, delivery Oct-2028. **Yellow** (owner unnamed).
- **C2 — Hanwha Ocean, 1 LNG carrier** — Knutsen OAS 9th ship, 29-May-2026, 174,000 cbm, $250M (375.9bn won), delivery Sep-2029. **Green**.
- **C3 — Jiangnan, 4 LNG carriers** — **COSCO** (Cosco Shipping Energy Transportation / CSET; written as `COSCO` per RF §4.14), Shell 7-yr charter, ~02-Jun-2026, 175,000 cbm, $953M total (~$238M/ship), delivery 2029-2030. **Yellow** (corroborators env-blocked; see verification note).

Ring A (CSB) returned **zero** new — CSB's newest indexed contract at every main yard is 2026-03 (≈3-month lag), and every CSB LNG/FSRU cluster already matched the backend. All discovery came from Rings B+C (regulatory + trade press). **Count reconciliations were clean** and confirm the backend is at the leading edge, not systematically behind:
- Samsung YTD = 13 LNG incl 1 FSRU = backend 12 + C1's 1.
- Samsung's entire May book = 6 vessels (1 FSRU + 5 LNG) = exactly the 6 May Samsung backend rows ⇒ the 18-May "3 Oceania LNG" filing is the Seapeak trio (rows 1209-11), **not** a new order.
- HD Hyundai YTD = 16 LNG (as of 14-May) = backend 16 (Ulsan 11 + Samho 5). Zero gap.

## Confidence breakdown

| Confidence | Count |
|---|---|
| Green | 1 (C2) |
| Yellow | 5 (C1, plus C3 ×4) |
| Red | 0 |
| Blank (§6a.9 negative log) | n/a (discovery mode) |

## Defects corrected

None.

## Conflicts flagged for human review

- **Seapeak ×3 (rows 1209-1211) contract-date verification** (see `backend_status_flags`): backend records 01-May-2026; Samsung's regulatory disclosure of these three "Oceania" LNG carriers was 18-May-2026. No new vessel implied — flagged only to reconcile the date (01-May LOI/announcement vs 18-May firm disclosure).

## Escalations

None. 3 candidate clusters is under the DC §7 ">5 clusters" systematic-gap threshold, and the reconciliations confirm no systematic gap.

## Items checked and excluded (audit trail)

- **Shenzhen Gas 1+1 at Hudong-Zhonghua** — EXCLUDED: 79,960 cbm mid-sized shallow-draft river-sea carrier (out of scope per inclusion criteria).
- **CCEC 3 LNG at HD Samho** — out of window (Dec-2025); already known.
- **MOL/JERA "Japanese giant takes order"** — stale article (Jan-2025); not a 2026 order.
- **30-Jan COSCO/Shandong Jiangnan quartet** — already in backend (rows 1158-61, Minsheng/Shandong); distinct from C3.
- **HD HHI $501M Hayfin (pub 15-May)** — = backend rows 1214-15 (14-May), deduped out.
- **Maran "doubles down"** — = 24-Mar option pair (rows 1172-73), covered.
- **Secondary yards** not swept (user chose seven-main coverage; May-2026 pilot found 0 across 14 secondary yards). FSRU sweep: only the MISC FSRU at Samsung (row 1206), covered.

## Verification note (§3.8 / §3.8a)

8/10 candidate URLs passed the gate (HTTP 200 + content match). The 2 failures are both **C3 corroborators** — Splash247 and Seatrade-Maritime — which returned **HTTP 403 in this environment** (Cloudflare). Kept and flagged per §3.8a (not deleted); browser spot-check recommended. C3's numeric values (175k cbm, $953M, 2029-2030) are present in LNG Prime 188357's fetched page but in its **paywalled body**, while the publicly-visible title/lead confirm only COSCO + Shell + LNG-quartet + on-order ⇒ C3 labeled **yellow**, not green.

## Drive link

_(pending upload — see batches/README.md for the upload + share-link procedure)_

## Script changes

- **`scripts/build_workbook.py`** — fixed discovery mode to mirror the **full live backend column order (46 cols)** after the 4 prefix columns, instead of the previous hardcoded 29-column subset. Required by Discovery SOP §5.2/§6.6 for paste-compatibility: the `candidate_vessels` sheet now reproduces every backend column (geolocation, Researcher, Last updated, [Original source], Notes, Other names, country/units/currency) in native order as blank columns. `row_data` is now keyed by exact backend header strings and placed by header index. This is the repo's first discovery batch, so the discovery path had not been exercised against the real schema before. Verified: candidate_vessels mirrored columns `== backend header` (paste-compatible); recalc zero errors.
- **`scripts/build_workbook.py` (rev-17/rev-7 conventions)** — two behaviors added, and this batch rebuilt under them:
  - **Yard-location autofill (DC §6.7):** the 7 yard-location columns (`Shipbuilder yard country/area` + [ref]; `Yard location latitude`/`longitude`/`plus code`/`accuracy` + lat/lon [ref]) are copied from an existing backend row for the same (normalized) shipbuilder, or left blank if the shipbuilder is new. All 6 candidates matched (Samsung HI, Hanwha Ocean, Jiangnan) and now carry the full block (e.g. Samsung `34.89804 / 128.6045 / VJW3+QV`, Jiangnan `31.355766 / 121.502217 / 9G32+XJ`). `candidates.json` row_data no longer carries these columns.
  - **Multiple URLs join with `", "` (RF §4.15):** `[ref]` cells with more than one URL join with `", "`, never a newline (defensive newline→`", "` rewrite added; both modes). C1's Shipowner / Contract date / Price `[ref]` cells were converted from newline-joined.
- **`scripts/normalize.py`** — added `_OWNER_DISPLAY` + `display_owner()` for the RF §4.14 owner-stylization rule; seeded `cosco-shipping-energy → COSCO`. C3's Shipowner was restyled `Cosco Shipping Energy Transportation → COSCO` (backend uses `COSCO` / `MOL, COSCO`).
- **Rebuild:** `lng_carrier_candidate_vessels.xlsx` regenerated 2026-06-03 under the above; recalc zero formula errors; 50 cols × 6 candidate rows verified (yard-location block populated, Shipowner `COSCO`, `", "`-joined refs, no newlines).
