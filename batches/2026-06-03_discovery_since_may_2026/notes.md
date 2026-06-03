# Batch 2026-06-03 — discovery — since May 1, 2026 (gap window 2026-05-01 → 2026-06-03)

**SOP revs at time of batch:** RF rev 16, DC rev 6 (pointers.md reconciled RF 16 / DC 6 / SR 4 — consistent, no stale cross-refs).

**Backend pull:** 1,465,308 bytes, 1210 data rows, header row index 1 (data starts row 2). All 30 expected columns mapped; no schema drift. Full live schema = 46 columns.

## Scope

- **Gap window:** contracts since 2026-05-01. Backend's latest contract date = 14-May-2026; CSB indexed only through 2026-03. So the genuine leading edge investigated was **15-May → 03-Jun-2026** (plus a sanity re-check of early May).
- **Yards in scope:** seven main LNGC yards (samsung, hanwha-ocean, hyundai-ulsan, hyundai-samho, hyundai-mipo, jiangnan, hudong-zhonghua).
- **Mode-specific parameters:** proposed-vessel threshold = default (named owner/charterer + ship count + delivery window); FSRU batched with conventional LNGCs; output dir `batches/2026-06-03_discovery_since_may_2026/`.

## Summary

3 candidate clusters / **6 vessels**, all "on order", all postdating the backend's latest contract (14-May-2026):

- **C1 — Samsung HI, 1 LNG carrier** — undisclosed Bermuda owner (brokers→JP Morgan, unconfirmed), 27-May-2026, $252M, delivery Oct-2028. **Yellow** (owner unnamed).
- **C2 — Hanwha Ocean, 1 LNG carrier** — Knutsen OAS 9th ship, 29-May-2026, 174,000 cbm, $250M (375.9bn won), delivery Sep-2029. **Green**.
- **C3 — Jiangnan, 4 LNG carriers** — COSCO Shipping Energy (CSET), Shell 7-yr charter, ~02-Jun-2026, 175,000 cbm, $953M total (~$238M/ship), delivery 2029-2030. **Yellow** (corroborators env-blocked; see verification note).

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
