# Batch digest — 2026-06-03_discovery_since_may_2026

**Mode:** discovery  ·  **Proposals:** 6 (auto-safe 1, needs-decision 5)  ·  **Conflicts:** 1  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: (new vessel) ×1

These 1 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **cluster C1**: `Samsung HI — 1 LNG carrier — undisclosed Bermuda owner` (Y) — Samsung HI disclosed on 27-May-2026 a five-vessel order (1 LNG carrier + 2 VLGCs + 2 crude tankers) from an unidentified Bermuda-based shipowner; only the 1 LNG carrier is in scope. ~$252M (381.4bn won), delivery Oct-2028. Owner name not disclosed; brokers link it to JP Morgan interests (UNCONFIRMED) -> yellow. Net-new confirmed by reconciliation: Samsung YTD 13 LNG incl 1 FSRU = backend 12 + this 1; and Samsung's 6 May-2026 vessels (1 FSRU + 5 LNG) all already in backend, so the 27-May ship is the only addition. Capacity not disclosed (left blank).
- **cluster C3**: `Jiangnan — COSCO 4x LNG (Shell charter) — vessel 1/4` (Y) — COSCO Shipping Energy (via Cosco Shipping LNG Investment Shanghai / CSET) ordered 4x 175,000 cbm LNG carriers at Jiangnan, announced ~02-Jun-2026, on a 7-year charter to Shell (Shell Tankers Singapore). 6.445bn yuan ($953M total, ~$238M/ship), delivery 2029-2030. DISTINCT from the 30-Jan Shandong Ocean Energy/Minsheng quartet already in backend (rows 1158-1161, delivery 2028-29). VERIFICATION CAVEAT: COSCO+Shell+LNG-quartet+on-order are in LNG Prime 188357's publicly-visible title/lead; the yard (Jiangnan), capacity, price and delivery passed the curl content-check but sit in LNG Prime's paywalled body. Corroborating Splash247 + Seatrade returned HTTP 403 in this environment (kept per SOP 3.8a). Recommend a browser spot-check before promoting -> yellow.
- **cluster C3**: `Jiangnan — COSCO 4x LNG (Shell charter) — vessel 2/4` (Y) — Sister hull of C3 (COSCO Shipping Energy 4x 175,000 cbm at Jiangnan, ~02-Jun-2026, Shell 7-yr charter, ~$238M/ship, delivery 2029-2030). See vessel 1/4 for the full verification caveat (LNG Prime 188357 paywalled body; Splash247/Seatrade 403-blocked here).
- **cluster C3**: `Jiangnan — COSCO 4x LNG (Shell charter) — vessel 3/4` (Y) — Sister hull of C3 (COSCO Shipping Energy 4x 175,000 cbm at Jiangnan, ~02-Jun-2026, Shell 7-yr charter, ~$238M/ship, delivery 2029-2030). See vessel 1/4 for the full verification caveat.
- **cluster C3**: `Jiangnan — COSCO 4x LNG (Shell charter) — vessel 4/4` (Y) — Sister hull of C3 (COSCO Shipping Energy 4x 175,000 cbm at Jiangnan, ~02-Jun-2026, Shell 7-yr charter, ~$238M/ship, delivery 2029-2030). See vessel 1/4 for the full verification caveat.

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

Not auto-applied (data-fill is additive to blanks only). Decide each in `conflicts.csv`.

- **row 1209-1211** Contract date verification: backend `` vs research `` — Confirm whether 01-May (LOI/announcement) or 18-May (firm-contract disclosure) is the intended Contract date for rows 1209-1211; no new vessel implied.

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-06-03_discovery_since_may_2026`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-06-03_discovery_since_may_2026` to confirm everything landed.
