# Batch — data-fill — rows with `Last updated >= 2026-05-18` (run 2026-06-04)

**Mode:** data_fill (first batch of this workflow). **SOP revs:** RF rev 17, DC rev 7, **DF rev 1** (new — `docs/sops/data_fill.md`). pointers.md reconciled RF 17 / DC 7 / DF 1 / SR 4.

**Backend pull:** fresh CSV pulled at run start (the user was actively promoting rows into the backend during the session). Scope re-derived from the fresh pull per RF §3.0.

## Scope

- **Row filter:** `Last updated >= 2026-05-18` → **42 rows**, ids 1144–1223. (Includes rows 1218–1223, the discovery C1/C2/C3 candidates the user promoted into the backend mid-session; all carry `Last updated = 6/3/2026`.)
- **Columns:** everything researchable (IMO, Name, Hull, Shipowner, Shipowner country/area, Shipbuilder, Capacity+units, Cargo/Vessel/Propulsion type, Delivery year, Operator/charterer, Contract date, Price+currency).
- **Research targets at run start:** 224 blank cells + **1 `unknown`** (O1213 = id 1218 Shipowner), across 18 builder|owner clusters.

## Summary

**88 proposed fills (59 Green, 29 Yellow); 140 documented blanks; 5 candidate findings.** recalc: zero formula errors. Every proposed URL passed the §3.8 gate (subagent verification + central `merge_fills.py` re-verify). No off-vocab values, no orphan refs, no Price-without-currency.

Fills by field: Shipowner country/area 28, Cargo type 22, Propulsion type 14, Price 7 (+ Price currency 7), Operator/charterer 4, Vessel type 2, Capacity 2 (+ Capacity units 2). Derivable autofill: 16; researched: 72.

Documented blanks (honest negatives, §6a.9) concentrate where expected for fresh/leading-edge orders: Vessel type 26 (no source prints the literal `conventional` token — CSB says "LNG Tanker", press says "LNG carrier"), Propulsion 21, Cargo 18, IMO 18, Operator 16, Hull 16, Price 14, Name 6.

## The `unknown` case (O1213 / id 1218) — preserve-ref contract exercised

Id 1218 is today's promoted "C1": Samsung HI, 1 LNG carrier for an **undisclosed Bermuda owner** (brokers link it to JP Morgan, UNCONFIRMED). The Shipowner cell was entered as `unknown` with a Cyprus Shipping News URL already in its `[ref]`. The Samsung-B subagent researched the owner and confirmed it is **genuinely not public** (Shipping Herald + all coverage say only "a Bermuda-based shipping company"). Per DF §4, no owner was fabricated — `Shipowner` is a documented blank, and its existing Cyprus `[ref]` is **preserved untouched**. (The build's preserve mechanism — existing-URL-first + peach — was validated separately; here it correctly left the cell `unknown`/gray since no value was proposed.)

## Candidate findings (for human review — NOT fills; data-fill is additive to blanks only, RF §8 / DF §9)

1. **rows 1158–1161 — Operator/charterer conflict:** backend = "Shandong Marine Energy"; research shows the end charterer is **Shell (Singapore) Trading** (Shandong = commercial manager, Minsheng = lessor). Cell already populated → flagged, not filled.
2. **rows 1212–1213 — candidate hulls:** the 13-May BW/HD Samho duo is reported as **H8358 / H8359** (portnews 391499, single source; per-row mapping ambiguous) — confirm on CSB later.
3. **rows 1212–1213 — Capacity conflict:** backend = 174,000 cbm; LNG Prime 186420 + portnews + safety4sea + Riviera report **177,000** ("three-tank"). Flagged (never overwrite).
4. **rows 1216–1217 — Capacity note (not a conflict):** Deltamarin states "180,000 cbm, or 176,400 at 98%"; CSB uses 176,400, backend siblings use 180,000 — same vessel.
5. **rows 251–256 (out of scope, FYI):** sibling CMHI-282-01..06 have blank Cargo/Vessel type but the order is now well-sourced (membrane, ME-GA, 180,000) — a future backfill opportunity.

## Verification note (§3.8)

Per-cluster subagents ran `url_verifier.py` and included only PASS URLs. Central `merge_fills.py` re-verified the distinct fill URLs: dead/soft-errored URLs are dropped (research fills that lose all URLs → documented blanks); **derivable fills keep their value even if the copied sibling `[ref]` is env-blocked** (they stand on backend-internal consistency — e.g. the Celsius/Denmark country ref shipvault.com is 403 here, value kept). Environment blocks seen and excluded from new fills: Splash247, Seatrade-Maritime, Marine Log (Cloudflare 403/"Just a moment"). Pre-existing backend Splash247 refs are untouched (§3.8a).

## Script changes (committed this batch)

- **`scripts/build_workbook.py`** — new `data_fill` mode (`build_data_fill`): row-oriented `backend_data_fill` sheet mirroring the backend; gray=existing, confidence-color=proposed, **peach=`[ref]` with existing URL kept first + corroborator appended**, cell comment for `unknown`; `_join_refs` helper (existing-first, dedup, `", "`); two new QA sections; validator (`_DATA_FILL_VOCAB`, price→currency, capacity→units, orphan-ref). No change to ref_fill/discovery modes.
- **`scripts/normalize.py`** — `owner_country()` + `_OWNER_COUNTRY` (unambiguous sibling-country derivation; `mol`/`maran-gas` guarded).
- **`scripts/derive_fills.py`** (new) — scope selection + derivable autofills + per-cluster research task lists.
- **`scripts/merge_fills.py`** (new) — merge per-cluster research + central §3.8 re-verify gate.
- **`refdata/controlled_vocab.md`** (new) + **`refdata/owner_charterer_map.md`** (Owner→country table).
- **Docs:** `docs/sops/data_fill.md` (DF rev 1), `CLAUDE.md` router block, `docs/pointers.md` DF index.

## Drive link

_(pending upload — see batches/README.md for the upload + share-link procedure)_
