# Comprehensive discovery pass — plan (written 2026-09-23)

Scope confirmed with Baird 2026-09-23 (Discovery SOP §2): all four completeness streams,
FSRU stream reconciled against IGU as well as GIIGNL, Ring A at 7 main + 14 secondary yards
with **full pagination**, **expanded** proposed threshold, and **no** whole-active-fleet
re-audit (the 2026-09-17 IGU reconciliation covers it).

## 0. Why this pass is shaped differently

Every discovery run so far has been a **gap-window catch-up**: pick a contract-date window,
sweep CSB page 1, compare. That finds the leading edge and nothing else. The question here is
different — *has anything been missed anywhere* — so the pass is a **completeness audit**
keyed on the orderbook and the delivery cohort, not on a date window. The date window survives
only as one cheap stream (S4).

Four structural blind spots no previous run could have caught:

| Blind spot | Why nothing has caught it |
|---|---|
| A hull on a yard's orderbook outside the swept window | CSB has only ever been compared inside a gap window, page 1 |
| An IGU orderbook slot with no IMO | IG SOP treats `igu_no_imo` as cluster-level hints only — 19 clusters / 46 rows never matched row-for-row |
| A vessel **delivered in 2026** that was never in our orderbook | IGU 2026's fleet table is as-of end-2025; GIIGNL 2026 tabulates 2025 deliveries. Nothing enumerates 2026 deliveries |
| An FSRU serving a GEM-tracked terminal with no vessel row here | `fsru_sync_check.py` has never been run with `--carrier-export`; its output still says `"mode": "gem_only"` |

Backend at the 2026-09-23 09:00 pull: 1,229 rows — 862 `active`, 305 `on order`, 31 `proposed`,
19 `scrapped`. Latest contract date in the sheet: 29-May-2026. 2026 delivery cohort: 56 `active`
+ 38 `on order`.

## 1. Preflight (S0) — mandatory, before any research

1. `python scripts/pull_backend.py` — fresh CSV + re-derived colmap.
2. `python scripts/qc_backend.py` — review `work/qc_report.csv`; surface anything in scope.
3. `python scripts/dedup_index.py --pending batches/2026-09-17_0431ET_discovery_since_jun_2026`
   — four indexes (hull, cluster, IMO, name) + the stub list + the pending mapping.
4. **Stub rows.** Batch 3 (`2026-09-17_0431ET_discovery_since_jun_2026`) **is** in the backend,
   but only as columns A–E: sheet rows **1220–1231** carry Name, IMO and their `[ref]`s, with
   Status / Shipbuilder / Shipowner / Contract date / Capacity still blank pending the batch's
   remaining holds. Both of the old indexes key on the shipbuilder, so a stub row is invisible to
   them: every completeness stream would re-report those 12 vessels as missing, and the reverse
   direction would read them as "backend rows in no source".
   → **Tooling item T1** (done): `dedup_index.py` now also builds `imo_index` and `name_index`,
   flags every blank-`Status` row as a `stub`, and takes `--pending <batch dirs>` to map a batch's
   candidates onto the rows holding them (IMO → name → ordinal-free name). All 12 of batch 3's
   candidates map to rows 1220–1231; **none is absent**, so no stream should re-report them.
   `name_key()` is deliberately not `normalize_vessel_name` (which drops the parentheses that are
   the only thing distinguishing one placeholder from the next) and folds the `(HHI)` / `(HDHHI)`
   yard-abbreviation variants the sheet and the workbook disagree on.

**Preflight result (2026-09-23 11:47 pull, 1,229 rows).** `qc_backend.py`: 9 findings — 1 MED,
8 LOW, no corruption-class check firing. The MED is sheet row 1170 (`Shipowner country/area`
= Bermuda for Purus Marine, not in `shipowner_facts.csv`); the LOWs are placeholder-naming drift
(`(HHI)` vs `(HDHHI)` on rows 1201–1204 / 1214–1215, a missing ordinal on 1219 and on the
`unknown shipowner` stub). All pre-existing and none in this pass's scope — they belong to a
pre-release QC batch. Noted, not fixed here.

## 2. The streams

### S1 — Whole-orderbook reconciliation (the main event)

Not date-bounded. Build one per-yard table: **CSB hulls ∥ backend on-order rows ∥ IGU Appendix 4
∥ shipvault on-order** — and make the counts balance yard by yard. A row that appears in any
source column and not in the backend column is a candidate; a row in the backend column and
nowhere else is a reverse-flag (possible phantom or duplicate).

- **Ring A, full pagination.** 7 main + 14 secondary yards from `data/csb_yard_urls.md`,
  every page, **no contract-date filter**, LNG/FSRU types only. Paginate until the orderbook
  is exhausted (tokens `aORDERBOOK4c/4X/4F/4b/4B/4C/4s`, pages 2–8), normalising fullwidth `－`
  per RF §6.4 and watching for clusters split across pages (Discovery §4.4).
  → **Tooling item T2**: `csb_fetch.py` currently fetches page 1 only (`fetch_and_parse`).
  Add `--all-pages`, walking until a page yields no new rows or page 8, caching per page.
  Route the sweep through `scripts/sweep.py` pacing — 21 yards × up to 8 pages is a bulk sweep
  on one host, and a bare loop is what got us IP-banned on 2026-09-17.
- **IGU Appendix 4, row-for-row.** The 19 `igu_no_imo` clusters (46 rows) matched against
  backend on-order rows on (owner, builder, contract month, delivery year, capacity) — a
  **count** comparison, not an identity one: does the backend hold N rows where IGU holds N?
  Known shapes to settle: Capital Gas × HSHI (3 clusters), Purus × SHI and × HSHI, Celsius × SHI
  (2), Hyundai Glovis × HSHI (2), BGT × Hudong-Zhonghua, MOL "Singapore FSRU" × Hanwha,
  Ocean Yield/NYK × HHI, Knutsen × Hanwha, Hanwha Shipping × Hanwha Ocean, TMS Cardiff × SHI,
  Evalend × HHI, ADNOC L&S × Hanwha.
- **shipvault on-order re-enumeration.** Last run: 244 units, 167 matched by IMO, 23 unmatched
  large hulls. Re-run and diff against that list so the residue is *new* residue.
- **GTT count cross-check.** GTT announces tank designs 1–3 quarters after the yard contract;
  a GTT release naming N designs at yard X reconciles against our per-yard order count. Count
  evidence only — never a per-vessel `[ref]`.

Expected output: `work/orderbook_reconcile.json` + a per-yard balance table in the workbook.

### S2 — 2026 delivery cohort

Enumerate LNG carriers **delivered Jan–Sep 2026** from sources independent of our orderbook:
yard delivery press releases (Samsung/Hanwha/HD Hyundai/Hudong/Jiangnan newsrooms), trade-press
delivery coverage, shipvault `built = 2026`, and class-society registers. Match by IMO against
the 56 `active` + 38 `on order` 2026 rows.

Two findings possible, both valuable: a delivered vessel with **no backend row at all** (a true
miss — the blind spot this stream exists for), and a delivered vessel sitting in the backend as
`on order` (a Status finding, routed to a `fix` batch, not a discovery candidate).

Note the tracker-status trap already recorded in memory: flag/MMSI appear *before* handover, so
"Active" on a tracker is not delivery — check registry Service Status and the AIS destination
string before proposing a Status change.

### S3 — FSRU completeness (GIIGNL + IGU + terminals)

1. `python scripts/fsru_reconcile.py` against GIIGNL 2026 — re-run of the June 2026 pass on a
   backend that has moved a lot since (FSU reclassifications, `scrapped` statuses).
2. **IGU cross-check** (Baird's addition): the same 52 FSRU rows against IGU 2026's fleet table
   filtered to `vessel_type` FSRU — IMO-keyed, so it catches what GIIGNL's name-only join cannot,
   and it disagrees with GIIGNL usefully on the FSRU/FSU boundary (cf. row 61 Puteri Delima Satu,
   row 81).
3. **FSRU conversions.** A conversion never appears in a newbuild orderbook — trade-press and
   owner-newsroom sweep for conversion projects announced since the June 2026 pass.
4. **Cross-repo terminals check.** Run the terminals repo's
   `scripts/fsru_sync_check.py --carrier-export work/backend.csv` for the first time with the
   carrier side supplied. Every floating import unit in the GEM terminals tracker should have a
   vessel row here; the ones that don't are candidates or scope calls. Read-only against that
   repo — findings come back here, no writes there.

### S4 — Leading edge + open leads (cheap, mandatory)

- **2026-09-17 → 2026-09-23.** Six days; Rings B and C only (DART/KIND via en.sedaily.com,
  Bursa coverage, HKEX; LNG Prime / Splash247 / TradeWinds). CSB will not have indexed anything
  this recent.
- **Open leads carried forward** from the sep-17-pass worklist §4:
  - **MISC × Hudong-Zhonghua H2019A–H2023A** — shipvault has 10 hulls (H2014A–H2023A), the
    backend has 5 rows. Five possible missing vessels, blocked on citable press. Highest-value
    single lead in the pass.
  - **`Maran Gas Efessos`, IMO 9627497** — the one real `igu_only` candidate (Maran Gas /
    Hanwha Ocean, 159,800 cbm, 2014). Needs a non-IGU ref for the add.
  - **Mozambique LNG 17 slots** (rows 1187–1203) — TotalEnergies' slot deadline was pushed to
    September 2026, so the conversion decision is now due. Also settles the owner/yard split
    flagged in batch 3 (`MOL, NYK` on all 17 vs the press split).
  - **Woodside placeholders 1204–1206** — batch 3 recommends deletion (the slot converted into
    the Seapeak × Samsung HI order, rows 1165–1167). Confirm, then Baird deletes by hand.
  - **Hull↔row confirmations** left unwritten for want of press: Hanwha 2627/2628 (Knutsen) ↔
    rows 1161/1172, SHI 2803 (J.P. Morgan) ↔ row 1118, SHI 2808 (Purus) ↔ row 1173.

### S5 — Proposed bucket, expanded threshold

Baird expanded the threshold for this run: **a named charterer/owner + a named program + an
approximate delivery window qualifies, with no ship count required.** Generic expansion talk
("Qatar will add 70–80 vessels", "Cheniere will need more ships") still fails.

- Programs to sweep: QatarEnergy, ADNOC, NextDecade (Rio Grande), Venture Global, Commonwealth
  LNG, Woodside (Louisiana), Cheniere, Argent, plus any program surfaced by S1/S4.
- **Staleness review of the 31 existing `proposed` rows** — which have converted to firm orders
  (and should become `on order` via a `fix` batch), which have died. The 17 Mozambique rows and
  the 3 Woodside rows are already in S4.
- A count-less program produces **one** candidate row, not a guessed N, with the missing count
  called out in `discovery_notes`. Never fabricate ordinals.

## 3. Execution shape

Streams S1–S3 are independent and read-heavy → one subagent each, in parallel, each writing its
own `work/discovery_<stream>.json`. S4 and S5 are press-driven and overlap heavily in sources →
run them together as one agent so a single Splash247 wrap-up serves both. Cheaper models for
the mechanical enumerations (S1 CSB parsing, S2 registry enumeration); the judgment work —
cluster identity, the count reconciliation, scope calls — stays in the main loop.

Then, centrally and never in a subagent:

1. **Dedup and cluster** against the backend **and** the pending batch-3 candidates (§1.4).
2. **§3.8 verification gate** on every URL — `merge`-then-gate, as in the data-fill path. No
   ref goes in the workbook ungated, including ones that passed in a prior batch.
3. **Confidence is computed, not declared** (RF §5 rev 28) — `scripts/confidence.py` sets the
   grade from what the gate did; a subagent's label is overwritten. A researcher may cap down
   with `cap_reason`, never up.
4. **`build_workbook.py --mode discovery`** now refuses any filled cell with a blank `[ref]`
   (added 2026-09-23 after the unsourced `Vessel type` finding in batch 3) — expect that to bite
   on `Vessel type` and `Capacity` for freshly-announced orders, and leave those cells blank.
5. `python scripts/recalc.py` — zero formula errors required.
6. `python scripts/dedupe_check.py` — advisory sweep (AP §5a).

## 4. Outputs

- `batches/2026-09-23_<HHMM>ET_discovery_comprehensive/` — `candidates.json`,
  `lng_carrier_candidate_vessels.xlsx`, `notes.md`, plus the audit artifacts:
  `orderbook_reconcile.json` (S1 per-yard balance), `delivery_cohort_2026.json` (S2),
  `fsru_completeness.json` (S3, incl. the terminals cross-check), `proposed_review.json` (S5).
- **A completeness statement in `notes.md`** — the point of the pass. Per stream: what was
  enumerated, how many matched, what the residue is, and what "we looked and found nothing"
  covers. A null result is a deliverable here, not a failure.
- Backend findings that are *not* new vessels (Status wrong, capacity conflicts, proposed→firm
  conversions) go to `conflicts.csv` and a follow-on `fix` batch — never into the discovery
  candidate rows.
- Commit the batch directory. **No push without approval.**

## 5. Escalation triggers live for this pass

- Discovery SOP §7: >~5 candidate clusters in the same gap window. S4's window is six days, so
  more than one or two clusters there is already anomalous. S1–S3 are **not** gap-window
  streams and the §7 count does not apply to them — a large S1 residue is the finding, not an
  escalation.
- One whole owner's fleet or one whole yard appearing absent → stop and ask (the MISC ×
  Hudong-Zhonghua 5-hull gap is the live instance of exactly this shape).
- A `000`-with-timeout pattern on any host → IP ban, not a bot wall. Stop that host for the run;
  do not retry in a loop. vesselfinder is still banned as of the last probe (2026-09-17) and is
  out of scope for the pass.

## 6. Tooling items this pass needs

- **T1** (done) `dedup_index.py` — IMO + name indexes, stub-row flagging, `--pending <batch dirs>`
  (§1.4). Without it, every stream re-surfaces batch 3's 12 vessels. Tests: `tests/test_dedup_index.py`.
- **T2** (done) `csb_fetch.py --all-pages [--all-yards] [--max-page N]` — walks each yard's whole
  orderbook, one wave per page, paced through `sweep.py` (never a bare loop). A yard stops on an
  empty page, on a page whose ship tokens repeat one already seen (an invalid pagination token
  silently re-serves page 1), on a tripped breaker, or at `--max-page`. Resumable via
  `work/csb_orderbook_sweep.jsonl`. Tests: `tests/test_csb_fetch.py`.
- **S1** (done) `orderbook_reconcile.py` — the reconciler itself, plus `normalize.hull_core()`
  (the sources write one hull three ways, and `normalize_hull()` only canonicalizes the CSB
  shape, so keying on it matched nothing at all). Tests: `tests/test_orderbook_reconcile.py`.
- **T4** (done, unplanned) `orderbook_reconcile.py --resolve-imo` / `resolve_ship_imos()` /
  `_parse_ship_imo()`. `csb_fetch.py` parses the yard **orderbook list**, which has no IMO
  column, so a hull key was the only thing the first three passes could match on — and every
  vessel the backend holds under a **name**, with a blank hull cell, read as a missing vessel.
  The first artifact claimed 9 such vessels; all nine were in the backend (Hanwha 2593-2596 =
  sheets 1031/1032/1034/1035, Qatar 9/10 = 888/889, Dalian G175K-5 = 814 `Sea Energy`). The
  ship **detail** page does print the IMO, so a fourth pass fetches it (through `sweep.py`,
  cached in `work/csb_ship_imo.json`) and re-keys before anything is called absent.
  `csb_unmatched` 9 → 2, `csb_hull_to_add` 8 → 15. **Never call a CSB hull absent without it.**
- **T3** Discovery SOP gets a new section for the **comprehensive pass** as a mode distinct from
  the gap-window catch-up (the four blind spots in §0, the per-yard balance table, the
  completeness statement, and T4's rule). Write it after the run, from what actually worked — rev 8.

T1, T2, S1 and T4 all ride in this batch's commit with a note in `notes.md`, per the repo
convention that a script fix rides with the batch that needed it.

## 7. Outcome (2026-09-23)

Batch `batches/2026-09-23_1546ET_discovery_comprehensive/`. **1 candidate** — Maran Gas
Efessos, IMO 9627497, an IGU-2025 **seeding gap** (both IGU editions print it; its four
sister ships are sheets 343/376/377/379). CSB yielded **zero** new vessels: after T4 the two
surviving residues are near-miss fills for sheets 1159 and 1175, not new rows. 31
`backend_status_flags` (15 hull fills, 3 CSB status findings, 2 conflicted IMO+hull fills,
the `Athlos` IMO disagreement, the sheet-20 GIIGNL Name defect, 9 IGU no-IMO count deltas)
route to a fix batch. S2/S3 returned 0 candidates. Full statement in the batch's `notes.md`.
