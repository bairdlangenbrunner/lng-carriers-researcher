# Full research pass — autumn 2026 (in-house, no SFOC / Clarksons)

**Written:** 2026-09-16. **Status:** proposed — waiting on Baird's go / scope edits.
**Owner:** Baird (review + apply); Claude Code runs the streams.

## Why now

The backend has not moved since June. Fresh pull 2026-09-16: 1,220 vessel rows
(822 active / 364 on order / 34 proposed); latest `Contract date` is May 2026;
latest `Last updated` stamp is 2026-06-22; the last committed batch is the
2026-06-26 FSRU reconciliation. Three and a half months of orders, deliveries
and namings are missing, and 119 on-order rows carry `Delivery year = 2026`
with placeholder names, most of which have now delivered.

Constraint for this pass: **everything is sourced in-house from public
sources.** No SFOC / Clarksons dataset, no GIIGNL table as a `[ref]`. The
verifier was brought to parity with the sibling repos first (rev 19, see
`docs/sops/ref_fill.md` §3.8 / §3.8a) so every stream below runs through the
graded gate.

## Streams, in run order

Each stream is one or more batches under `batches/<date>_<HHMMET>_<mode>_<scope>/`,
reviewed and applied through the Apply SOP before the next stream that depends
on it. Every batch starts with `pull_backend.py` + `qc_backend.py`.

### 0. Citation rot sweep (new; ~1 hour of wall-clock, mostly unattended)

```
python scripts/pull_backend.py
python scripts/citation_qc.py --delay 0.7            # -> work/citation_qc.csv
```

436 distinct URLs cover ~15,000 `[ref]` cells (one IGU 2025 World LNG Report
URL backs 10,180 of them). Triage by grade (RF §3.8a): `dead`/`banned` → a
fix-mode batch that replaces the ref (or logs a §3.8c conflict when the
value can no longer be sourced); `blocked` → kept, listed in the batch notes
as environment-blocked. First run's result is in the section at the bottom.

Decision needed: whether to run `--corroborate` (the per-cell §3.8c gate on
all ~15k cells; ~2–3 h). Recommendation: yes, but scoped with
`--sheet-rows` to the on-order/proposed block (live rows ~824–1220) where the
values are most likely to have drifted, and to any row a later stream touches.

### 1. Discovery — gap window 2026-05-29 → today

Discovery SOP §2 parameters, proposed values:

| Parameter | Proposed | Why |
|---|---|---|
| Gap window start | 2026-05-29 (latest contract date) with a 60-day look-back to 2026-04-01 | Orders reported late, and the two June discovery batches used a May window; the overlap is deduped by `dedup_index.py` |
| Yard coverage | all yards on CSB, plus DART/KIND/Bursa/HKEX regulatory sweep | The June 5 CNOOC/CMES/NYK batch showed orders landing at Hudong-Zhonghua and CMHI, outside the seven-yard core |
| Proposed-bucket threshold | include charterer programmes with a named yard OR a signed LOI/HoA; exclude pure “in talks” | 34 proposed rows already exist (Mozambique LNG 01–17, Woodside 01–16, Equinor); stream 5 reviews those |
| FSRU handling | batched in, tagged by vessel type | Volume is small; the June FSRU reconciliation is the baseline |
| Output | `batches/<date>_<HHMMET>_discovery_since_apr_2026/lng_carrier_candidate_vessels.xlsx` | |

Rings: A CSB every yard slug in `data/csb_yard_urls.md`; B DART/KIND via
`en.sedaily.com` first, Bursa/HKEX for Malaysian/HK-listed owners; C trade
press per `data/source_roster.md` (LNG Prime, TradeWinds public leads,
Splash247, Riviera, Offshore Energy, Baird Maritime); D charterer programmes
(QatarEnergy phase 3 residual, ADNOC L&S, Woodside, Mozambique) only for
the proposed bucket. Expect ~5 clusters/month → roughly 15–25 candidate
clusters; if it exceeds ~30, pause and re-scope per Discovery SOP §7.

### 2. Delivery roll-forward — the 119 on-order rows with `Delivery year = 2026`

No SOP covers this yet; it is a data-fill batch in `fix`-mode packaging. For
each row (live rows 824 onward; 95 of the 119 still carry a yard-hull
placeholder Name), research: delivered? → `Status = active`, real `Name`,
`IMO number` (9-series), naming date if the sheet carries one; not yet
delivered → confirm the year or roll to 2027 with a ref. Sources: yard
delivery PRs and CSB delivery columns, owner PRs, Equasis-free vessel
databases (vesselfinder / shipvault — both grade `ok` from curl), class
registers (DNV/ABS/BV/LR/KR), LNG Prime “delivers”/“names” items.

Packaging: one `fix.json` per yard cluster (`build_workbook.py --mode fix`),
every value+ref through the §3.8c gate; `preserve_ref` never used here
(these are sourced changes). The 2027 rows (73) get the same treatment for
any vessel already named/launched. Suggest writing this up as a short SOP
section (data_fill.md §11 “status roll-forward”) once the first cluster
has been through review, so the rule is durable.

### 3. Small [ref]-fill batch — 20 Rule-F cells across 17 rows

`derive_fills.py` finds only 20 filled data cells with a blank paired
`[ref]`. One batch, `--mode ref_fill`, standard §3 workflow. Cheap; run it
right after stream 0 so the fix batch and this one can be applied together.

### 4. Status-scoped data-fill

Blank/`unknown` counts (fresh pull) show where research actually pays:

| Column | On order (364) | Proposed (34) | Active (822) |
|---|---|---|---|
| Cargo type | 341 | 34 | 80 |
| Vessel type | 333 | 34 | 74 |
| Operator/charterer | 322 | 16 | 814 |
| Price | 321 | 34 | 819 |
| Contract date | 257 | 34 | 817 |
| Propulsion type | 96 | 34 | 6 |
| Hull number | 75 | 34 | 744 |
| IMO number | 41 | 34 | 0 |
| Capacity | 22 | 34 | 1 |

Batches, in priority order, each `--mode data_fill` with `derive_fills.py`
scoped by status/rows and one subagent per yard-owner cluster:

1. **On-order core facts** — IMO, hull, capacity, propulsion, contract date
   for the 364 on-order rows (derivable autofills first: cargo/vessel type
   are largely derivable from capacity + class per Data-fill SOP §5).
2. **On-order commercial facts** — operator/charterer and price where a
   public source exists (owner PRs, DART filings with contract value,
   Bursa announcements). Expect low yield on price; do not chase.
3. **Active vessels** — cargo type / vessel type (80 / 74 blanks, derivable)
   and the 6 propulsion blanks. Skip operator/price/contract-date for the
   983 rows bulk-loaded in Dec 2024: that is a separate decision (below).

### 5. Proposed-bucket review (34 rows)

Mozambique LNG 01–17 (live rows 888–904), Woodside Energy 01–16 (rows
1115–1130), Equinor (row 578). Each programme either converted to firm orders
(→ merge into discovery clusters and mark the placeholders for deletion or
promotion), lapsed, or is unchanged. Output: a fix batch with the decision
per row and a `conflicts.csv` note where a placeholder maps onto a
discovered firm order (dedupe rule apply.md §5a).

### 6. QC release + apply, per batch

`qc_backend.py` full sweep (7 LOW findings today, all name-consistency),
`dedupe_check.py` after every apply, `verify_apply.py --pull`. Re-export
`../lng-carriers-map` `fleet.json` after the FSRU/FSU rows change.

## Decisions for Baird

1. Run stream 0 `--corroborate` on the on-order/proposed block only, or on
   the whole sheet?
2. Gap-window look-back: April 1 (recommended) or strictly May 29?
3. The 983 rows bulk-loaded 2024-12 have mass blanks in Price / Operator /
   Contract date / Hull. Leave them (recommended for this pass — they were
   loaded from the Clarksons-era dataset and the public-source yield on
   operator/price for delivered ships is poor) or open a separate long-tail
   stream later?
4. Should the delivery roll-forward (stream 2) get its own SOP section
   before or after the first cluster is reviewed?

## Order of operations and effort

| Step | Batches | Mostly unattended? | Review load |
|---|---|---|---|
| 0 rot sweep + fix batch | 1 | yes | small (dead/banned list) |
| 3 Rule-F ref-fill | 1 | partly | small |
| 1 discovery | 1 | no | medium (candidate clusters) |
| 2 delivery roll-forward | 3–4 by yard | partly | medium-large (119 + some 2027) |
| 4 data-fill | 3 | partly | medium |
| 5 proposed review | 1 | no | small |
| 6 QC/apply | per batch | yes | — |

Streams 0 and 3 can start today. Stream 1 gates stream 5; stream 2 does not
depend on anything but is the largest human-review load, so it is split by
yard.

## Tooling state going in

- `scripts/url_verifier.py` rev 19 + `scripts/fetch.py`: graded verdicts,
  Forbidden list in code, Wayback fallback, PDF text, JSONL audit log.
  153 offline tests pass. Live smoke test 2026-09-16: vesselfinder, Riviera,
  Splash, IGU, Google Maps links → `ok`; **every marinetraffic-class URL →
  `blocked` (Cloudflare)** — marinetraffic.org, marinetraffic.com,
  marinevesseltraffic.com and shipvault.com, including the IMO-search
  endpoint `imo_tracker.py` uses — so the §6a.8 fallback is browser-only
  this pass; vesselfinder per-IMO pages cover 9XXXXXX IMOs only (RF §6a.8
  caveat updated).
- `scripts/citation_qc.py`: new.
- `merge_fills.py` / `build_workbook.py --mode fix` now log `blocked` refs
  as a separate finding instead of a conflict.

## Stream 0 — first run results (2026-09-16)

Run: `python scripts/citation_qc.py --delay 3` over the 2026-09-16 pull
(15,034 `[ref]` cells, 436 distinct URLs), then
`--resume --regrade dead,blocked` after the verifier fixes below. Output in
`work/citation_qc.csv` (gitignored); rows are live sheet rows.

### Tally (regrade pass)

| verdict | URLs | ref cells |
|---|---|---|
| ok | 288 | 14,511 |
| blocked | 129 | 498 |
| dead | 19 | 25 |
| banned | 0 | 0 |

No GEM or abarrelfull URL is cited anywhere in the backend.

### Blocked (keep — §3.8a)

All but a handful are the four Cloudflare vessel-tracker hosts:
marinetraffic.org (55 URLs), shipvault.com (27), marinetraffic.com (20),
marinevesseltraffic.com (9). The refs were added by the June 2026 data-fill
and corroborate batches and passed the same verifier at HTTP 200 then; the
sites now serve a JS managed challenge (marinetraffic.org,
marinevesseltraffic) or an "Attention Required" firewall page (shipvault,
marinetraffic.com) to every non-browser client, from this machine and from
Anthropic egress alike. Wayback has no captures of the per-vessel pages.
Treatment: keep, spot-check a sample in a browser, record
"environment-blocked — kept". No scripted workaround (RF §6a.8 caveat).
Remaining blocked hosts (bairdmaritime challenge platform, seatrade-maritime,
trusteddocks, chantiers-atlantique HTTP 418, businesstoday.com.my, dnv,
bloomberg, dnb, hls.co.kr) are ordinary bot walls; same treatment.

### Dead (fix batch — Stream 5 input)

- **TradeWinds Woodside rows 1205–1219** (Status [ref], 15 cells): the URLs
  are sequential guesses `2-1-1875729` … `2-1-1875743` off the real article
  `2-1-1875728` cited on row 1204; they 404 or slug-drift to unrelated
  stories. Hand-entered (no batch in this repo introduced them). Fix: point
  all 15 at `2-1-1875728`, whose standfirst ("between 16 and 20 LNG carrier
  newbuildings", in the page's Nuxt JSON payload) covers the 16 unnamed
  Woodside rows. Verifier now matches that string and rejects bare "16"/"20".
- **new-ships.com shipyard pages** (rows 347, 351, 362, 365, 367, 509, 540;
  Shipbuilder yard country/area + one lat/lon): HTTP 422; the site moved to
  `/ns/shipyard/<id>` and the old ids do not resolve — truly dead. Re-source
  yard country from the yard's own site or CSB.
- **indiashippingnews row 1118** (Name; Shipowner): redirects to site root.
  Replace with the SHI DART filing or a Korean-press equivalent.

Four first-pass `dead` verdicts did not survive the regrade: imarinenews
4851 (rows 1116–1117) is `ok` on re-fetch (transient HTTP 000);
jnshipyard.com.cn (20 rows, yard country/area) and the COSCO Energy page
(row 688) are HTTP 000 from here but Wayback holds captures, so they grade
`blocked` (geo-block / .cn outage, keep); investors.seatrium.com row 11 is
an empty HTTP 202 bot wall, `blocked`.

### Verifier fixes this run surfaced

Wayback 429s were being read as "no snapshot" (now retried and labelled);
archive.org's "Temporarily Offline" page is now labelled "Wayback
unavailable"; HTTP 000 with an archived copy grades `blocked`, not `dead`;
raw-source matching only counts meta / JSON-LD / JSON-payload strings /
data attributes, with letter boundaries on numbers (the TradeWinds "16"
false positive came from CSS `font-size:16px` and a favicon `16x16`).
`citation_qc.py` now re-checks fresh `dead` verdicts after a pause and
takes `--resume --regrade`.

### Regrade delta

First pass: ok 287 / blocked 126 / dead 23 (49 cells). After the fixes and
`--resume --regrade dead,blocked`: ok 288 / blocked 129 / dead 19 (25
cells). Net: one URL flipped to `ok`, three from `dead` to `blocked`, no
`blocked` URL recovered (the tracker hosts are still walled). The 25 dead
cells are the fix-batch scope: 15 TradeWinds Status refs, 8 new-ships yard
cells, 2 indiashippingnews cells.
