# LNG Carrier Tracker — New-Vessel Discovery SOP

**Document purpose:** This SOP describes the workflow for discovering LNG carrier and FSRU vessels that are NOT yet in the backend Google Sheet. It complements the [ref]-Fill SOP (which covers citation work on rows that already exist). It is the operating manual for one-time gap analyses and (with adjustments) for recurring catch-up sweeps.

**Last revised:** 2026-05-28 rev 6 (repository migration — output model changed to one committed directory per discovery run under `batches/`; `present_files` references updated for the Git/Claude Code workflow. No research-rule changes from rev 5.). Prior: 2026-05-27 rev 5 (added paywalled-source guidance to §4.6: per [ref]-Fill SOP §3.8b, QA notes quote only publicly-visible content; LNG Prime's editorial entity tags support yellow confidence as corroboration, not green. Surfaced by the same 2026-05-27 F8 finding that drove the [ref]-Fill SOP rev 15.).

---

## 1. Scope and prerequisites

**What this SOP covers.** Discovering vessels NOT yet in the backend, packaging them into a backend-shaped candidate-vessels workbook for human review.

**What it does NOT cover.** Filling missing `[ref]` URL citations on existing backend rows — see the separate [ref]-Fill SOP for that.

**Tracker inclusion criteria** (from the user's project description, applied as a filter throughout):
- INCLUDED: conventional LNG carriers and FSRUs in global LNG trade
- EXCLUDED: FSUs (storage-only), small-scale and mid-scale LNG carriers, LNG bunkering vessels, domestic-only ships, anything cancelled or decommissioned before December 2025

**Three vessel status categories** (the discovery workflow targets the first two):
- **On order**: binding shipbuilding contract signed; has a yard, a delivery year, usually a hull number
- **Proposed**: announced by a shipping company or charterer with public sources, but no binding shipyard contract yet
- **Active**: built, delivered, operable — out of scope for discovery (active vessels are catalogued via the IGU annual report)

**Backend file.** Public CSV export of the "backend" tab:
`https://docs.google.com/spreadsheets/d/1FjjeQD8AlQ_kQAMrohA3jAV3yZy7Lb61djt25D-4Fh8/export?format=csv&gid=243795339`

Download via `bash + curl -A "Mozilla/5.0"` (web_fetch is blocked by Google's robots.txt for this URL).

---

## 2. Parameters to confirm with the user before starting

Always confirm these before kicking off research:

1. **Gap window start date.** Either inferred from the backend's latest contract date or specified directly by the user (e.g. "anything contracted Jan 2026 onward").
2. **Yard coverage.** Either the seven main LNGC yards (cheaper, covers ~99% of conventional LNGC newbuilds), or the full 382-yard CSB master directory (more thorough — catches occasional LNGC orders at secondary yards like CMHI, DSIC, Zvezda).
3. **Proposed-vessel threshold.** Default: named charterer/owner + specific ship count + approximate delivery window. Generic statements like "Cheniere will need more ships" or "Qatar will add 70-80 vessels" do NOT meet the threshold.
4. **FSRU handling.** Default: batch with conventional LNGCs (same workflow, different vessel-type tag). Could split into a separate stream if FSRU volume justifies it.
5. **Output naming.** Default: `batches/<batch-dir>/lng_carrier_candidate_vessels.xlsx` (one committed directory per discovery run — see repo `batches/README.md`).

---

## 3. The four-ring source model

Discovery searches happen across four "rings," in roughly this order. Each ring serves a distinct purpose and the rings together cover the full discovery space.

### 3.1 Ring A — Shipyard orderbooks (authoritative for on-order)

**ChinaShipBuild (CSB)** is the spine. CSB indexes ~382 yards globally and is updated within a few weeks of contract signing. The seven yards that build essentially all conventional LNGCs:

| Yard | CSB stable URL |
|---|---|
| Samsung HI | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcbganmkhTk8Pl4EN` |
| Hanwha Ocean | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJXanmkhTk8Pl4EN` |
| HD Hyundai HI, Ulsan | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccbanmkhTk8Pl4EN` |
| HD Hyundai Samho | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccCanmkhTk8Pl4EN` |
| HD Hyundai Mipo | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccBanmkhTk8Pl4EN` |
| Jiangnan Shipyard | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFcanmkhTk8Pl4EN` |
| Hudong-Zhonghua | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFXanmkhTk8Pl4EN` |

CSB master directory (8 pages, 382 yards): see [ref]-Fill SOP §6.2 for pagination URLs.

**Secondary LNGC-capable yards** to sweep when the user opts for "all yards" coverage:

| Yard | CSB token |
|---|---|
| Dalian Shipbuilding Industry Co (DSIC) | `pklujyukkpp4JJgJFanmkhTk8Pl4EN` |
| China Merchants Heavy Industries Jiangsu (CMHI Haimen) | (look up in master directory; CMHI delivered Celsius Georgetown 27-Apr-2026) |
| Mitsubishi HI | `pklujyukkpp4BsXCg` |
| Kawasaki Shipbuilding, Kobe | `pklujyukkpp4BscJg` |
| Zvezda Shipbuilding (Russia, Arctic LNGCs) | `pklujyukkpp4BbcBSanmkhTk8Pl4EN` |
| JMU Tsu, JMU Ariake | `pklujyukkpp4BscJF`, `pklujyukkpp4BbcXb` |
| NACKS (Nantong COSCO KHI) | `pklujyukkpp4BbcFcanmkhTk8Pl4EN` |
| DACKS (Dalian COSCO KHI) | `pklujyukkpp4BbcJFanmkhTk8Pl4EN` |
| Imabari Shipbuilding, Marugame | `pklujyukkpp4BbccSanmkhTk8Pl4EN` |
| COSCO yards (Yangzhou, Qidong, Dalian, Zhoushan) | various |
| Yantai CIMC Raffles | `pklujyukkpp4BbcBBanmkhTk8Pl4EN` |

Realistically, in any given catch-up window the secondary yards rarely yield missing vessels — the May 2026 pilot found 0 missing across all 14 secondary yards swept. But the sweep is cheap (one curl per yard) and gives auditable "we looked and didn't find anything" coverage.

**Korean yard IR sites, CSSC press releases** are useful corroborators but CSB usually aggregates them within 1-2 weeks; not separate "ring" work.

### 3.2 Ring B — Regulatory disclosures (authoritative for the contract event itself)

Korean-listed yards must legally disclose material contracts within hours of signing. This is where the leading edge lives — contracts that haven't yet been indexed by CSB.

**DART (Korea):** `https://dart.fss.or.kr/dsab007/main.do` (English: `https://englishdart.fss.or.kr/`)

Filing type to search: 단일판매ㆍ공급계약체결 ("Single Sales/Supply Contract Conclusion").

Companies to search:

| Yard | DART entity name |
|---|---|
| Samsung HI | 삼성중공업 / Samsung Heavy Industries |
| Hanwha Ocean | 한화오션 / Hanwha Ocean Co., Ltd. |
| HD Hyundai Heavy Industries | HD현대중공업 |
| HD Korea Shipbuilding & Offshore | HD한국조선해양 |
| HD Hyundai Samho | HD현대삼호 |

**Important calibration from [ref]-Fill SOP §6a.2:** DART filings use a standardized template that includes contract value (KRW), counterparty region (often a euphemism like "Oceania" or "Americas"), contract start/end dates, and contract type. They generally do NOT include hull numbers, and the counterparty is rarely named directly — trade press is needed to identify the actual buyer behind the "Oceania-region shipowner" tagline.

**KIND (KRX English mirror):** `https://kind.krx.co.kr/disclosure/details.do`

**Bursa Malaysia (MISC / Petronas-linked orders):** disclosures usually surface via TheStar.com.my, The Edge Malaysia, BusinessToday Malaysia.

**Hong Kong Exchange and Shanghai Exchange:** for Chinese owner-side filings (CSSC, China Merchants Energy, COSCO Shipping Energy).

**English-language proxies for Korean reg filings** are often easier than parsing the Korean PDFs:
- **Seoul Economic Daily (en.sedaily.com)** — fastest English coverage of DART filings, typically within hours
- **Asia Business Daily** — similar coverage
- **iMarine, BigGo Finance** — Asia-focused trade reporting

### 3.3 Ring C — Trade press (best for proposed vessels and pre-CSB-indexing on-order signal)

The on-order leading edge AND the proposed bucket both live here. The full source roster from [ref]-Fill SOP §7 applies; for discovery the most productive sources are:

- **LNG Prime** (`lngprime.com`) — most comprehensive LNG-specific coverage; many articles paywall the body but headlines/leads are public
- **Splash247** — strong on cluster-level reporting (one article often covers 3-5 orders across yards)
- **TradeWinds** — strong on shipbroker attribution (identifies "Oceania-region buyer" → actual owner)
- **Riviera Maritime Media**
- **LNG Industry** (`lngindustry.com`) — strong on technical and tank-design / GTT angles
- **Seatrade Maritime**
- **Hellenic Shipping News / Shipping Telegraph**
- **Offshore Energy** (`offshore-energy.biz`)
- **IndexBox** — repackages multiple sources into single articles
- **Marine Link, Maritime Executive** — broader maritime, useful for delivery announcements

**Most productive query patterns:**
- `LNG carrier newbuild order [month] [year]`
- `LNG carrier order announced [year]`
- `[Yard name] LNG carrier order [month] [year]`
- `[Charterer name] LNG carrier program [year]`
- `[Yard] [Owner] LNG newbuild` (combine when there's a known cluster shape)

**Charterer-program searches for the proposed bucket** (only useful when the user has expanded the threshold):
- QatarEnergy fleet expansion, Q-Max additions
- Cheniere shipping requirements
- Venture Global LNG newbuild
- ADNOC LNG, Woodside, Shell, BP, TotalEnergies LNG carriers
- NextDecade Rio Grande LNG shipping

**Owner-press-release searches** — when a recent article names a charterer/owner you don't recognize, hit their newsroom directly:
- Knutsen, Capital Gas, MISC, Maran Gas, Cool Co, Celsius, EPS, Sonangol, TMS Cardiff, Purus, Dynagas, Nakilat, BW LNG, Seapeak, Hayfin Capital Management, Cosco Shipping Energy, China Merchants Energy Shipping, Mitsui OSK, NYK, K-Line

### 3.4 Ring D — Cross-references and indexes

These don't usually yield new vessels directly but they validate that the Ring A+B+C sweep is comprehensive:

- **IGU World LNG Report** — the project's spine; annual orderbook reconciliation
- **Clarksons Research, Drewry, Poten & Partners, Affinity Shipping, Banchero Costa** — broker market commentary; their public summary pieces sometimes name specific newbuilds and (more usefully) state quarterly LNGC contract counts so the Ring A count can be reconciled against the industry total
- **Vessel databases (VesselFinder, MarineTraffic, Equasis, BalticShipping)** — mostly catch ships near or after delivery; less useful for on-order discovery, but worth checking for "ordered" status filters
- **GTT press releases** — GTT receives a tank-design subcontract from the yard typically 1-3 quarters after the shipowner-yard contract. A GTT release announcing N new tank designs at Yard X is a cross-check on the shipowner-yard order count at that yard

---

## 4. Workflow per discovery run

### 4.1 Confirm parameters with the user (§2)

### 4.2 Pull the latest backend CSV

`curl -A "Mozilla/5.0" "<export URL>" -o backend.csv`

The user is actively editing the backend, so always start with a fresh pull.

### 4.3 Build the dedup index

Build two indexes:
- `(builder_norm, hull_norm)` → backend row — for matching CSB hulls
- `(builder_norm, owner_norm, contract_month)` → backend rows — for matching cluster-level signals from trade press and DART when hull numbers aren't yet assigned

Builder and owner normalization is project-specific (see the May 2026 build script for canonical mappings: Samsung HI / Samsung Heavy Industries → `samsung`; Daewoo / DSME / Hanwha Ocean → `hanwha-ocean`; etc.).

Also extract the subset of backend rows whose contract date is within the gap window — this is the "existing coverage" to compare against.

### 4.4 Scrape Ring A (CSB)

For each yard in scope:
1. Fetch page 1 (covers ~25 rows, typically reaches back ~6-12 months which is enough for most gap windows)
2. Parse the orderbook table using the `<tr><td>` pattern (see [ref]-Fill SOP §6.3 or the May 2026 build script for the parser)
3. Filter to LNG/FSRU vessel types — `is_lng_relevant(typecap)` returns true for "LNG Tanker" and "FSRU"; false for "LNG bunkering"
4. Filter to contracts in the gap window
5. Compare each (yard, owner, contract month) tuple against the backend dedup index; flag anything that doesn't match

CSB page 1 is normally sufficient. If page 1's oldest entry is more recent than the gap window start, paginate further (pagination tokens are `aORDERBOOK4c`, `aORDERBOOK4X`, `aORDERBOOK4J`, etc. — append to the yard token).

**Before flagging any specific hull as missing from CSB, sweep every page of that yard's orderbook.** Per [ref]-Fill SOP §6.3, pagination can split a single owner's cluster across pages (e.g. CMHI Haimen splits the 8-hull Celsius Shipping order with hull -04 on page 2 while -01/02/03/05/06/07/08 are on page 1). A discrepancy finding based on a page-1-only sweep is not yet trustworthy — paginate fully first, normalizing fullwidth `－` and ASCII `-` per [ref]-Fill SOP §6.4, before treating the absence as real.

### 4.5 Scrape Ring B (regulatory) for the post-CSB leading edge

For the period AFTER the backend's latest contract date AND not yet covered by CSB (typically the last 2-6 weeks):
- Search en.sedaily.com, asia.nikkei.com, lngprime.com for each yard ("Samsung Heavy LNG carrier order", "HD KSOE LNG carrier disclosure", etc.)
- Search Bursa Malaysia coverage on TheStar.com.my, BusinessToday.com.my, The Edge for MISC / Petronas orders
- Search Hong Kong Exchange announcements for COSCO Shipping Energy

The DART originals can be parsed directly when needed, but English-language trade press coverage of DART filings is usually sufficient and dramatically cheaper to process.

### 4.6 Trade press sweep (Ring C)

For each post-cutoff signal found, expand into trade press:
- Verify the contract event in cross-checked sources where possible (ideally 2 agreeing URLs both containing the key facts); 1 URL is sufficient when it's explicit and contains the data value verbatim or comes from a primary/regulatory source (DART, Bursa, yard PR, owner PR). See [ref]-Fill SOP §5 for the full sourcing standard.
- Identify the actual buyer (DART discloses regional euphemisms; trade press names the company)
- Capture: vessel count, capacity, propulsion type, contract value, delivery timing, charterer if applicable

Watch for cluster identity collisions: orders that look like the same cluster across two sources may actually be separate orders (different contract dates, different ship counts, different hulls). Use [ref]-Fill SOP §4.12 (Rule E) cluster-coherence logic.

**When trade press is paywalled** (LNG Prime, TradeWinds, Riviera in some cases), follow [ref]-Fill SOP §3.8b: quote only publicly-visible content in QA notes, never the paywalled body. LNG Prime's editorial entity tag list is a real corroboration signal — a Woodside tag on a Samsung HI / Seapeak article means the body names Woodside — but it supports **yellow** confidence per §5, not green. To get green from a paywalled-tagged source, pair it with a second source that names the same entity in publicly-visible content (yard or owner press release, non-paywalled outlet body, regulatory filing).

### 4.7 Charterer program sweep (Ring D)

Search for proposed-but-uncontracted programs that meet the threshold. The May 2026 pilot returned zero candidates because all named-charterer programs had already converted to confirmed orders captured in earlier rings. Expect the proposed bucket to be small or empty in most catch-up runs.

### 4.8 Dedup, enrich, classify by confidence

For each candidate:
1. Cluster duplicates that surfaced from multiple rings into a single cluster entry
2. Decide on a confidence label per [ref]-Fill SOP §5:
   - **Green** = ideally 2 cross-checked sources agree on the cluster and both contain the data value verbatim, OR 1 source that's explicit (value verbatim + cluster-coherent) and/or primary/regulatory (DART, Bursa, yard PR, owner PR). See [ref]-Fill SOP §5 for full criteria.
   - **Yellow** = entity-level confirmation but some material data point (owner identity, capacity, delivery year) is implied or contested across sources
   - **Red** = single source, weak corroboration, or sourcing chain that depends on a broker attribution that isn't yet corroborated — recommend leaving for the next round

### 4.9 Build the workbook (see §5)

### 4.10 URL verification gate (per [ref]-Fill SOP §3.8)

Every URL in the workbook must pass HTTP 200 + content match. In environments where headless curl is rate-limited or geo-blocked, `web_fetch` is the fallback. Per [ref]-Fill SOP §3.8a, environment-blocked URLs are kept and flagged, not deleted.

### 4.11 Run recalc.py, then write notes.md and commit the batch directory

---

## 5. Output workbook structure

Written to `batches/<batch-dir>/lng_carrier_candidate_vessels.xlsx`. Four sheets:

### 5.1 `README`
Generated date, scope, backend snapshot, methodology summary, candidate summary table, additional findings (non-candidate backend status flags), URL verification note.

### 5.2 `candidate_vessels`

**Column order is the backend column order, exactly.** The sheet must mirror every column in the backend in the same order, including columns the discovery workflow doesn't research and won't populate (geolocation lat/lon/plus code/accuracy and their `[ref]`; Researcher; Last updated; `[Original source]`; Other names; Notes; etc.). The four prefix columns (`cluster_id`, `cluster_label`, `confidence`, `discovery_notes`) come BEFORE the backend columns, then every backend column appears in its native order.

This is so the user can copy a candidate row's backend columns (starting at the first backend column, after the four prefixes) and paste directly into the backend Google Sheet without column-shuffling. Per §6.6, paste-compatibility is the hard requirement.

**Blank cells stay blank.** Per Rule F (see [ref]-Fill SOP §4.13), data cells the discovery workflow doesn't fill remain blank. Their paired `[ref]` cells also stay blank — never orphan a `[ref]`. Specifically:
- Geolocation cells (lat, lon, plus code, accuracy, lat/lon [ref]) are out of scope per [ref]-Fill SOP §4.8 — leave blank.
- Researcher, Last updated, [Original source] — these are backend workflow columns, not data values to research — leave blank.
- For a freshly-announced order where the yard hasn't assigned a hull number yet, Hull / Name / IMO stay blank, and so do their `[ref]` cells. The URLs that confirm the cluster cite the data cells that ARE populated: Shipowner, Shipbuilder, Status, Contract date, Delivery year, Capacity, Vessel type, Operator/charterer, Price.

Color coding (applied across all columns of a candidate row):
- **Green fill**: green confidence
- **Yellow fill**: yellow confidence (contested or implied)
- **Red fill**: red confidence (review needed before promoting)

The candidate's research notes (in `discovery_notes` and in QA_review's per-candidate provenance log) carry the broader source URLs even when no specific cell can cite them — that's where the audit trail lives for facts the backend doesn't yet record.

**How to verify backend column order before building.** Always re-read the header row of the freshest backend CSV pull and use those column names in that order — the schema may change between runs (e.g. the May 2026 backend added a "checked for May 2026 update" leading column, shifting indices by one). Don't hardcode the column order from a previous workbook.

### 5.3 `QA_review`
Four sections:
1. **Per-candidate provenance log** — one row per cluster: cluster ID, label, confidence, all source URLs, date verification, methodology notes
2. **Backend status flags** — non-candidate findings worth surfacing (status updates, owner-convention mismatches, propulsion-spec updates)
3. **URL verification log** — per-URL HTTP status + content-check results from [ref]-Fill SOP §3.8
4. **Search methodology audit** — yard sweep summary: which yards were checked, how many LNG/FSRU rows each had in the gap window

### 5.4 `backend_status_flags`
The non-candidate findings as a standalone sheet for easy filtering and triage. Same content as QA_review Section 2 but stands alone for users who want to act on existing-row updates separately from new-vessel discovery.

---

## 6. Hard rules

### 6.1 Inherit [ref]-Fill SOP rules where they apply
All rules in the [ref]-Fill SOP §4 apply to the candidate workbook, especially:
- **§4.7** Never overwrite backend values (candidate rows are additive; existing backend rows are never modified by discovery work)
- **§4.8** Skip geolocation `[ref]` fields
- **§4.11 Rule D** URL verification gate (§3.8)
- **§4.12 Rule E** Cluster coherence
- **§4.13 Rule F** Never fill a `[ref]` without a corresponding data value (the orphan-prohibition rule — see [ref]-Fill SOP §4.13 in detail; applies to candidate rows just as strictly as to backend rows)

### 6.2 Candidate rows are NOT backend additions
The workbook produces CANDIDATES for human review, not direct backend edits. Per [ref]-Fill SOP §4.7, the user reviews and decides what to promote into the backend. The candidate-vessels sheet is structured to support copy-paste into backend rows once approved.

### 6.3 Confidence labels are conservative by default
Default to yellow when there's any doubt. Green requires either (a) 2 cross-checked sources that agree and both contain the data value verbatim, or (b) 1 source that's explicit (data value verbatim + cluster-coherent) and/or primary/regulatory (DART, Bursa, yard PR, owner PR, class society). Red candidates should be rare — if a signal is too thin to support yellow, consider holding it for the next run rather than including it as red.

### 6.4 Proposed-vessel threshold (default)
A vessel makes the proposed bucket only when ALL three are true:
- A specific charterer or shipowner is named
- A specific ship count is given
- An approximate delivery window is stated

Statements like "we'll need more ships in the next few years" or "the program will expand" fail the threshold and don't generate candidate rows.

### 6.5 Don't double-count
Many trade-press articles report on multiple unrelated clusters in one piece. Each cluster needs its own attribution; the URL is a Rule-E-coherent citation for only the cluster(s) it actually names. A Splash247 wrap-up article that mentions "recent orders include BW + Hayfin + TMS Cardiff + Knutsen" is a valid source for all four clusters provided the body actually contains each cluster's identifying facts; otherwise treat it as a corroborator only for the cluster it discusses in detail.

### 6.6 Candidate rows must be paste-compatible with the backend
The `candidate_vessels` sheet must mirror the backend column order exactly (after the four prefix columns) — see §5.2. The user should be able to select a candidate row, copy the backend-column range (everything after the four prefix columns), and paste it into a new backend row without column-shuffling. This is the hard requirement; the contents of the cells can be blank where research didn't fill them (per Rule F and §4.8), but the COLUMN STRUCTURE must match the live backend schema byte-for-byte.

Before building the workbook, always re-read the header row of the freshest backend CSV pull. Don't hardcode the column order from a previous run — the schema may have changed (new columns added, columns reordered). If the schema has changed in a way that affects existing candidate workbooks, mention it in the README.

---

## 7. Pause-and-ask triggers

Stop and ask the user before proceeding when:

- Backend has more than ~5 candidate clusters in the same gap window and you suspect a systematic gap rather than the normal leading-edge lag (this would indicate the backend has fallen behind by a quarter or more)
- A candidate's identification depends entirely on one trade-press broker attribution with no DART/Bursa/yard-PR corroboration (publish as yellow or hold for next run)
- A finding suggests systemic backend issues (e.g. all candidates from one yard, or one whole owner's fleet appears missing — the May 2026 pilot did NOT find this but it's a possible scenario)
- The CSB master directory paginated search times out or returns inconsistent results across multiple sessions
- The gap window is unclear (no clear "latest contract date" in backend, multiple recent rows with blank contract dates)

---

## 8. Operational tips

**Start with CSB even when CSB is "obviously not enough."** CSB takes ~30 seconds per yard and immediately surfaces what isn't missing. It's the cheapest disconfirmation of "the backend has lots of gaps." In the May 2026 pilot, CSB confirmed the backend was complete for every cluster CSB had indexed — meaning all discovery work could focus on the ~3-week leading edge after CSB's last index update.

**One Splash247 wrap-up article can verify multiple clusters.** Look for "recent LNG carrier deals" or "LNG newbuild contracting wave" pieces — these often name 4-6 clusters in one body, with cluster-specific facts (yard, owner, ship count, value). They're the single highest-yield URLs in the trade press.

**English-language Korean reg filings are usually enough.** Parsing DART originals (Korean PDFs, EUC-KR encoding, standardized templates) is doable but rarely necessary. Seoul Economic Daily's en.sedaily.com publishes within hours of DART filings and captures everything important except hull numbers (which DART templates don't include anyway).

**Broker attribution often names the actual buyer.** DART discloses counterparties by region ("Oceania-based shipowner", "Americas region"). TradeWinds, Splash247, and Riviera identify the actual company via shipbroker channels. The pattern is consistent enough that "Oceania" frequently means TMS Cardiff, Hayfin, or another Greek/UK-managed entity using a Marshall Islands or Bermuda flag.

**Don't trust article-publication dates that seem off by years.** During the May 2026 pilot, a Splash247 article on the DSIC / Ocean Jade order initially looked like a May 2026 piece but on close reading was actually about an Apr 2024 deal that surfaced again in an aggregator. Always check publication date AND contract date in the article body before treating something as new.

**CMHI (China Merchants HI Jiangsu / Haimen) is a real LNGC yard.** First large LNGC ("Celsius Georgetown") delivered Apr 2026. Outside the seven main yards but worth keeping on the secondary-yard sweep going forward. May surface more candidates as the Chinese LNGC industry expands.

---

## 9. Changelog

- **rev 1** (2026-05-19): Initial SOP after the May 2026 catch-up gap analysis (Jan 2026+ window, all-yards coverage, 10 candidate vessels in 5 clusters discovered post-08-May-2026 backend cutoff: MISC FSRU at Samsung HI, TMS Cardiff 2x at Samsung HI, Seapeak 3x at Samsung HI, BW LNG 2x at HD Samho, Hayfin Capital 2x at HD HHI Ulsan). Three additional non-candidate backend status flags also surfaced. Workflow captured from the May 2026 build verbatim with parameter generalization for future runs.
- **rev 2** (2026-05-19): Relaxed sourcing standard in three places (§4.6 trade-press sweep, §4.8 confidence labels, §6.3 default confidence policy) to align with [ref]-Fill SOP rev 12. New standard: ideally 2 cross-checked URLs that agree and both contain the data value verbatim, but 1 URL is sufficient when it's explicit or primary/regulatory. Cross-references [ref]-Fill SOP §5 rather than restating the full criteria.
- **rev 3** (2026-05-26): Tightened §5.2 and added §6.6 — the `candidate_vessels` sheet must mirror the backend column order EXACTLY (after the four prefix columns), including columns the discovery workflow doesn't research and won't populate (geolocation, Researcher, Last updated, [Original source], etc.). This is so the user can copy a candidate row's backend columns and paste directly into the backend without column-shuffling. Surfaced by the 2026-05-26 discovery run, where the workbook had skipped Researcher / Last updated / [Original source] / geolocation columns, making paste-into-backend awkward. Rule F is unchanged: blank data cells stay blank, including their [ref] cells.
- **rev 4** (2026-05-27): Added a cluster-split pagination step to §4.4 — before flagging any specific hull as missing from CSB, sweep every page of the yard, since pagination can split a single owner's cluster across pages (not just split by date). Cross-references [ref]-Fill SOP §6.3 (which now carries the authoritative version of this rule) and §6.4 (which covers hyphen normalization). Surfaced by the 2026-05-27 SFOC reconciliation false-positive on Hull CMHI-282-04, which appeared missing on CSB page 1 but was actually on page 2 — and was further hidden by CSB rendering it with a fullwidth hyphen between `CMHI` and `282`. Also corrected the page-1 row count from ~50 to ~25 to match [ref]-Fill SOP §6.3.
- **rev 5** (2026-05-27): Added paywalled-source guidance to §4.6 — QA notes quote only publicly-visible content (cross-references [ref]-Fill SOP §3.8b); LNG Prime's editorial entity tag list is a real corroboration signal supporting yellow confidence per §5, not green. Surfaced by a 2026-05-27 F8 finding that quoted paywalled LNG Prime body text in a QA note (same finding that drove [ref]-Fill SOP rev 15). Same workflow guidance applies to TradeWinds and other paywalled trade-press sources.
- **rev 6** (2026-05-28): Repository migration. Output model changed from `/mnt/user-data/outputs/lng_carrier_candidate_vessels.xlsx` to one committed directory per discovery run under `batches/` (§2 param 5, §5). `present_files` reference in §4.11 replaced with "write notes.md and commit the batch directory." No research-rule changes — the four-ring source model, the §4.10 verification gate, and confidence labeling are unchanged from rev 5.
