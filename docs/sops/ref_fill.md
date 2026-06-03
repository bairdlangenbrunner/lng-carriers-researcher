# LNG Carrier Tracker — Backend [ref]-Fill Research SOP

**Document purpose:** This is the operating manual for filling missing `[ref]` URL citations in the LNG Carrier Tracker backend Google Sheet. It captures every rule, source-handling convention, and workflow step accumulated through the project to date.

**Last revised:** 2026-06-03 rev 17 (three output-formatting rules surfaced by the first discovery batch: §4.14 — `Shipowner` / `Operator/charterer` values use the backend's existing short stylization, e.g. write `COSCO`, not `Cosco Shipping Energy Transportation`; §4.15 — multiple URLs in one `[ref]` cell join with `", "`, never a newline; and a §4.8 carve-out — the seven yard-location columns are never *researched* but may be *mirrored* from an existing backend row for the same shipbuilder, per the new Discovery SOP §6.7 autofill. `build_workbook.py` enforces §4.15 and the §6.7 autofill. No research-rule changes; the §3.8 gate, Rules A–F, and confidence labels are unchanged.). Prior: 2026-05-28 rev 16 (repository migration — output model changed from a single rolling xlsx to one committed directory per batch under `batches/`; scratch paths and `present_files` references updated for the Git/Claude Code workflow. No research-rule changes; §3.8 gate, Rules A–F, and confidence labels are all unchanged from rev 15.). Prior: 2026-05-27 rev 15 (added §3.8b — QA notes quote only publicly-visible content; paywalled body text is never quoted in a QA note; editorial entity tags on LNG Prime support yellow confidence as corroboration, not green. Surfaced by a 2026-05-27 F8 finding that quoted paywalled LNG Prime body text where the verifier could only see the public lead and the tag list.).

---

## 1. Project context

**Tracker scope.** The LNG Carrier Tracker covers conventional LNG carriers (and FSRUs) involved in global LNG trade. It excludes FSUs, small/mid-scale LNG carriers, LNG bunkering vessels, domestic-only ships, and anything cancelled or decommissioned before December 2025.

**Three vessel status categories.**
- **Proposed**: announced by a shipping company or charterer with public sources, but no binding shipyard contract signed
- **On order**: binding shipbuilding contract signed; typically has a delivery year and a hull number
- **Active**: built, delivered, operable (includes idle / under repair)

**What we are filling.** The backend has many `[ref]` columns that sit next to corresponding data columns (e.g. `IMO number` paired with `IMO number [ref]`). The data columns are populated; many `[ref]` columns are blank. Our job is to fill blank `[ref]` cells with publicly-accessible URLs that support the data value.

**Backend file.** Public CSV export of the "backend" tab:
`https://docs.google.com/spreadsheets/d/1FjjeQD8AlQ_kQAMrohA3jAV3yZy7Lb61djt25D-4Fh8/export?format=csv&gid=243795339`

`web_fetch` is blocked by Google's robots.txt for this URL; download via `bash + curl -A "Mozilla/5.0"`.

---

## 2. Output format

**One xlsx per batch** at `batches/<batch-dir>/lng_carrier_backend_ref_fill.xlsx`. Each batch gets its own directory under `batches/` (see repo `batches/README.md` for the naming convention); the workbook is committed there for an auditable history.

Three sheets:

### 2.1 `README`
First sheet. Explains the current batch, what changed this revision, the cumulative rules, how to read the workbook, and a cluster summary table.

### 2.2 `backend_ref_fill`
The backend rows for this batch, with new URL citations color-coded:
- **Green fill**: high confidence — source directly identifies the specific vessel (by hull number or commercial name)
- **Yellow fill**: medium confidence — entity-level confirmation; OR a contested value
- **Red fill**: low confidence / review needed
- **Peach fill**: override — pre-existing backend `[ref]` URL was replaced this batch due to an identified defect (broken URL, wrong cluster, etc.). See `QA_review > Defects corrected` for the rationale per cell.
- **Light-gray fill**: pre-existing backend value (not touched, shown for context)
- **No fill**: cell is still blank — see `QA_review` for why

Header row: dark blue with white text. Frozen panes at C2. `[ref]` columns 50 chars wide.

### 2.3 `QA_review`
Up to five sections (sections appear only when the batch produces relevant entries):
1. **Per-cell citation log** — one row per `[ref]` cell filled, with: row id, vessel name, field name, action ("filled [ref]"), confidence label, URL(s), and a note explaining the citation
2. **Data-value conflicts** — cases where research suggests the backend data value (not the `[ref]`) is wrong or contested. Backend is NEVER overwritten; conflicts are flagged for human review
3. **Candidate data-value fills** — blank backend data cells (e.g. blank `Cargo type`) where multiple sources explicitly support a fill value, suggested for human review
4. **Defects corrected** — pre-existing backend `[ref]` URLs that were overridden this batch. Per §3.0 step 3, each row records the old URL, why it was wrong, the new URL, and the reason for replacement
5. **URL verification log** — per-URL HTTP status + content-check results from the §3.8 verification gate, including any cluster-coherence assignments

---

## 3. Research process — the standard workflow per batch

When the user gives a row range (e.g. "rows 1148–1167"):

**3.0 BACKEND-PRIORITY (MANDATORY first step).** Always start by pulling the LATEST backend CSV from the public export URL — the user is actively editing it between batches, and existing `[ref]` URLs are often filled in. The workbook this batch produces must:
  1. Copy every existing backend `[ref]` URL verbatim into the workbook (with light-gray fill to mark "pre-existing, not researched this batch")
  2. ONLY perform new research for `[ref]` cells that are genuinely blank in the fresh backend
  3. ONLY override an existing backend `[ref]` URL when there is a specific identified defect (broken URL, wrong cluster, etc.) and the override should be flagged in `QA_review > Defects corrected` with the old URL, why it was wrong, the new URL, and the reason for replacement

The schema may change between pulls (e.g., the backend added a "checked for May 2026 update" leading column in May 2026 — column indices shifted by one). Always re-derive the column index map from the header row of the fresh pull rather than assuming a fixed schema.

**3.1 Read the batch.** Load the rows from the local backend CSV. For each row, identify what's blank vs filled, and which `[ref]` cells are fillable (blank `[ref]` paired with filled data value).

**3.2 Cluster rows.** Recent on-order rows usually come in groups (one order = 2–4 sister hulls at the same yard for the same owner). One trade-press article often covers an entire cluster.

**3.3 ChinaShipBuild lookup (mandatory for hull-number rows).** For each yard in the batch, fetch the yard page on chinashipbuild.com and verify every hull number is present. (See §6 for navigation.) This is the canonical source for Hull number [ref] under Rule A.

**3.3a Fallback hull search (MANDATORY when CSB does not list the hull).** When CSB does not yet list a hull, do NOT leave `Hull number [ref]` / `Name [ref]` blank without first running the §6a fallback protocol. The fallback is required, not optional. Only after exhausting it may the cells be left blank, and the negative result must be documented per §6a.9 so the blank is auditable. (See Rule A §4.4 for what satisfies Hull [ref], and §6a for the search recipes.)

**3.4 Trade press search.** For each cluster, search for the order announcement. Reliable sources: LNG Prime, Splash247, Riviera Maritime Media, Seatrade Maritime, Hellenic Shipping News / Shipping Telegraph, TradeWinds, en.portnews.ru, Ships Monthly, iMarine, UPI, Seoul Economic Daily (en.sedaily.com), Cyprus Shipping News, Maritime Gateway.

**3.5 Vessel database check (active or near-active vessels only).** For vessels with real IMOs or near-delivery, check VesselFinder / MarineTraffic / Balticshipping for ship-database confirmation.

**3.6 Build the workbook.** Encode citations into the build script. Run `recalc.py` to confirm no errors. (URL verification happens at §3.8 as a mandatory pre-commit gate, not here.) Save into the batch directory.

**3.7 Flag in QA.** Any conflicts found vs backend (capacity mismatch, delivery-year mismatch, owner-convention difference, missing rows entirely) go into the conflicts section of QA_review.

**3.8 URL VERIFICATION GATE (MANDATORY before committing the batch).** Every URL that will be written into the xlsx MUST pass two checks:
  1. **HTTP 200**: `curl -sL -w "%{http_code}" --max-time 30 -A "Mozilla/5.0 (...)"` returns 200 (or 200 with a non-error `<title>` for sites that serve soft-errors as 200, e.g. Riviera and some paywalled sources)
  2. **Content check**: the fetched body contains the entities the citation claims (the owner name, yard name, hull number, or order-specific identifier)

URLs that fail either check are **dropped** from the citation bundle, not written into the xlsx. If a `[ref]` cell's entire citation bundle fails, that `[ref]` becomes a documented-blank per §6a.9 with a note explaining the verification failure.

Use the `url_verifier.py` module included with the build script. It maintains a per-build cache, treats failed verification as a hard error in strict mode, and lets the build silently drop failed URLs in best-effort mode.

The gate is non-optional. Citations are worthless if they 404, soft-error, or don't actually contain the claimed facts. **Never** ship an xlsx whose citations haven't passed the gate.

Failure modes seen in practice (Batch 2 rev 2 retrospective):
- **404 on plausible-looking slugs** — a citation URL that was hallucinated or that worked in a prior batch but the article was unpublished/renamed (saw this on LNG Prime and Splash247 EPS/Jiangnan articles)
- **200 soft-error** — site returns HTTP 200 but the page is actually a "Too Many Requests" or "Not Found" template (saw this on Riviera — `<title>HTTP 429 Too Many Requests(6)</title>` returned as 200)
- **200 with navigation pollution** — page contains the expected substrings but only in nav/footer/sidebar, not in the article body itself

The HTTP-status and body-contains checks address (1) and (2) directly. For (3), pair content checks with title checks and with multi-substring requirements (e.g. require BOTH "Eastern Pacific" AND "Jiangnan" AND "175,000" — not just one).

When propagating citations from a prior batch into a new batch, **re-verify** them. URLs decay; an article that loaded last month may 404 today.

**3.8a 404 sweep across pre-existing backend refs.** Beyond verifying URLs Claude is about to add, do a full sweep of every URL currently in the batch's backend `[ref]` cells. Real 404s → override per §3.0 step 3. Environment-side blocks (Cloudflare anti-bot, geo-restrictions like 503 from .cn yard sites, headless 403s on shipyard corporate pages) are NOT real 404s — keep the URL and note in QA. The QA report should distinguish "real dead URL — removed" from "environment-blocked but valid — kept."

**3.8b QA notes quote only publicly-visible content.** When writing a QA_review entry that quotes the cited source, the quoted text MUST come from content the verifier can actually fetch — headline, lead, public excerpt, image caption, byline, publication date, tag list, meta description. Paywalled body text is **never** quoted in a QA note. If the article body is behind a subscriber wall, reference it as "paywalled body" without quoted text, and base the QA note's claim only on what the public surface attests to.

The §3.8 content check protects citations; §3.8b protects the QA narrative around them. Two examples:

1. *Good:* "LNG Prime article dated 18-May-2026 confirms yard, owner, and ship count in its public lead. Woodside named via article tag list (LNG Prime's tags are editorial — see below). Body is paywalled and not publicly verifiable."
2. *Bad:* "LNG Prime article says 'Seapeak secured 10-year fixed-rate charter contracts with an international energy company...'" — when that sentence is in the paywalled body. Don't write this even if memory or prior context suggests it's accurate; the verifier can't confirm it, and a future reviewer reading the QA can't either.

**Editorial tag attestation is a real signal — but it supports yellow, not green.** Some trade-press sites use editorially-curated entity tags at the bottom of articles. LNG Prime is the confirmed example: tags only appear when the entity is named in the article body, including when the body is paywalled. A `Woodside` tag on a Seapeak / Samsung HI article means LNG Prime's newsroom asserts Woodside is named in the body, even when the body itself isn't publicly readable.

For §3.8 verification purposes, an entity tag in the visible portion of the page passes the content check (the string is on the page, in the tag list). For §5 confidence labeling, a tag-only attestation supports **yellow** but not green — entity-level confirmation, not "data value verbatim in the visible body." To get green from a paywalled-tagged source, pair it with a second source that names the same entity in publicly-visible content. Not every site's tag list is editorial in this sense — some use auto-generated tags that aren't meaningful corroboration; currently confirmed editorial is LNG Prime only.

Surfaced by a 2026-05-27 F8 finding that quoted paywalled LNG Prime body text in a QA note (the underlying Woodside attribution turned out to be correct — corroborated by LNG Prime's editorial Woodside tag — but the quoted body sentence was unverifiable and on its face indistinguishable from fabrication).

---

## 4. Hard rules (no exceptions)

### 4.1 NEVER cite SFOC as a [ref] URL
SFOC is the project's data origin (and remains in the `[Original source]` column), but it is NOT a citable URL for any `[ref]` cell. Every `[ref]` URL must point to an independent, publicly-accessible source.

### 4.2 NEVER cite GEM
GEM is excluded as a source entirely.

### 4.3 NEVER cite GTT standalone
GTT marketing pages and announcements are useful but may not be the sole source for any `[ref]` cell. Always pair with a non-GTT corroborating URL.

### 4.4 Rule A — Hull number [ref] must explicitly contain the hull number

Three parts:

**(i) What satisfies Hull [ref].** The `Hull number [ref]` cell MUST cite a URL whose page text contains that exact hull number as it appears in the backend. A trade-press article that merely confirms the order at the yard is INSUFFICIENT. Acceptable sources (any one of which satisfies Rule A):
- chinashipbuild.com per-yard tables (best for Korean and Chinese yards)
- DART (Korean reg filings) entries that explicitly list the hull number
- KIND (KRX disclosures, English) entries that explicitly list the hull number
- Classification society publications or new-build listings (DNV, Lloyd's Register, ABS, KR, BV, NK) naming the hull
- Yard or parent-company press releases / investor materials naming the hull
- Owner / charterer press releases or annual reports naming the hull
- Vessel database newbuild entries (VesselFinder, MarineTraffic, Equasis, BalticShipping) containing the hull
- Trade-press articles that explicitly print the hull number (e.g. LNG Prime articles that say "Hull 8340")

**(ii) The §6a fallback is required before leaving blank.** When CSB is inaccessible (timeouts, token rotation, dead links, robots.txt) OR doesn't yet list the hull, the §6a fallback protocol is REQUIRED — not optional — before leaving `Hull number [ref]` (and `Name [ref]` where Rule B applies) blank. At minimum, run the targeted Google search variants, the DART/KIND check (Korean yards), and the classification-society + vessel-database newbuild check. CSB being slow to index a recent order is not by itself a stop condition — it's the normal trigger for §6a. Only escalate to the user when CSB is broken AND §6a has been exhausted for at least one cluster without success.

**(iii) Blank-with-search-log is the acceptable end state.** If the fallback returns no hit, document the negative result per §6a.9: `QA_review` row noting "Searched: [list of recipes]; no public source containing hull X found as of [date]." A blank with a search log is acceptable; a blank without a search log is not.

**Honest calibration (from 2026-05 pilot on Ulsan 3639):** The fallback protocol will sometimes return no hit even after a diligent run. DART filings for Korean LNG-carrier contracts use a standardized template that omits hull numbers; class society public registries don't index hulls until close to delivery; vessel databases don't have searchable newbuild listings by yard hull. For very fresh orders (contracted within the last ~3 months) at Korean yards, the realistic outcomes are roughly:
- ~30–50% of clusters: a public source (yard PR, owner PR, follow-on trade press, or a DART filing's free-text section) explicitly contains the hull → cite at Green
- The rest: contract metadata confirmed via DART + trade press, but no hull-specific public source found → leave `Hull number [ref]` blank with the §6a.9 search-attempt log, and re-run in 1–3 months when CSB indexes the order

The point of Rule A is NOT to guarantee every hull gets a citation — it's to make sure we **tried** and **documented the try**.

### 4.5 Rule B — When name = hull number, Name [ref] also needs the hull
When the vessel's `Name` column is itself the hull number (e.g. "Samsung HI Geoje 2775" — no commercial name yet), the `Name [ref]` cell ALSO must cite a URL containing the hull number. The same chinashipbuild.com URL satisfies both Rule A and Rule B.

### 4.7 NEVER overwrite backend values
The `[ref]` work is additive. Backend data cells are never edited. When research conflicts with a backend value, log it in `QA_review > Data-value conflicts` with both values and the source — human review decides.

### 4.8 Never *research* geolocation `[ref]` fields — but mirror a known yard's block
The `lat`, `lon`, `plus code`, `accuracy`, and their `[ref]` columns are out of scope for *research* — never go look them up. They are a property of the **yard**, not the vessel, so the one allowed way to populate them is to **copy** the whole yard-location block from an existing backend row for the **same shipbuilder** (a deterministic mirror, not research). The block is seven columns: `Shipbuilder yard country/area` + its `[ref]`, `Yard location latitude`, `Yard location longitude`, `Yard location plus code`, `Yard location accuracy`, and `Yard location lat/lon [ref]`. If the shipbuilder is **not** already in the backend, leave all seven blank.

- In **discovery** mode the build script does this automatically for every candidate row — see Discovery SOP §6.7 for the autofill mechanism.
- In **[ref]-fill** mode, when a backend row's yard-location cells are blank and a sibling row for the same shipbuilder has them, surface the block as a paired candidate fill in `QA_review > Candidate data-value fills` (per §4.9 / Rule F — never auto-edit the backend; the copied data value and its copied `[ref]` travel together, so no orphan `[ref]` is created).

(Note: the Discovery SOP §5.2 / §6.6 also requires these columns to APPEAR in the candidate_vessels sheet for paste-compatibility with the backend.)

### 4.9 Don't fill empty data cells without explicit source support
If a backend data cell is blank (e.g. blank `Cargo type`), do not auto-fill it. If a source explicitly supports a value, add it to `QA_review > Candidate data-value fills` for human review.

### 4.10 IMOs that look unusual (7 digits starting with 1, not 9)
Real IMO numbers are typically 7 digits starting with **9** (or **8** for very old vessels). The backend frequently has IMOs that start with **1** (e.g. `1157109`, `1158696`, `1159195`) — these were previously assumed to be Clarkson internal placeholders. **They are not.** Empirically (2026-05-18 confirmation across rows 1148-1155) every such IMO in the batch resolved to a real, indexed entry on marinetraffic.org and similar databases, with the page title containing both the yard-hull label AND the IMO. The 1XXXXXX format appears to be a pre-delivery IMO range used for newbuilds before they enter service.

Procedure: Run the §6a.8 IMO→marine-vessel-tracker lookup for every blank `IMO number [ref]` (regardless of whether the IMO starts with 9 or 1). If a per-vessel page resolves with the IMO in the body AND the page is cluster-coherent (yard-hull label matches the row's Name / Hull / Shipbuilder), cite it as **Green**. See §9 for the full IMO-handling procedure.

### 4.11 Rule D — Every cited URL must pass the §3.8 verification gate
No URL goes into a `[ref]` cell without passing §3.8 (HTTP 200 + content match). This is a SEVERE rule because broken citations are arguably worse than blank ones: blanks are honest, broken citations look authoritative but lead nowhere.

### 4.12 Rule E — Every cited URL must be cluster-coherent
A URL passes coherence iff its page text names the SAME cluster as the row it's cited for. "Same cluster" means same owner AND same yard AND (where applicable) same ship count or contract identifier. Two clusters at the same yard, or for the same charterer, are NOT the same cluster.

Examples of cluster-coherence failures seen in practice (Batch 2 rev 2 retrospective):
- **Cross-cluster citation at same yard**: a `petronas-misc-seal-...-quintet` URL describes a 5-ship MISC/Petronas cluster at Hudong-Zhonghua. Citing it for the 3-ship BGT/Nigeria-LNG cluster (also at Hudong-Zhonghua) is WRONG — the article does not name BGT or NLNG. Same yard, different owner, different ship count → different cluster.
- **Cross-cluster citation at same charterer**: a generic Cheniere-related article that names one of several Cheniere charter programs is not automatically a valid citation for a different Cheniere charter program with a different owner. Verify the SHIP COUNT and CONTRACT DATE match.
- **Bundling unrelated coverage**: appending a URL "because it's about LNG carriers at this yard" without checking that it names this row's owner is a coherence violation. Two valid URLs each citing different clusters do not combine into a valid citation for either cluster.

Coherence check protocol — before citing URL U for row R:
1. Identify R's cluster signature: (owner name, yard name, hull count or contract date, contract value if available)
2. Fetch U and confirm U's body contains: the owner name AND the yard name AND (if applicable) the same hull count / contract date / contract value
3. If U fails any of these checks, drop U from R's citation bundle even if U passed §3.8 generic verification

**Cluster-split detection (rev 6 extension).** Rows that share the same owner and yard may STILL be separate clusters if their contract dates or delivery years diverge. Before treating multiple rows as a single cluster, check the backend data for divergent values:
- If contract dates differ by more than ~30 days → likely separate orders, treat as separate clusters
- If delivery years differ → likely separate orders
- If ship counts implied by trade-press URLs differ from the backend row count → look for an additional order announcement

When this happens, each cluster gets only the URLs that describe that specific order. A URL describing order A is cluster-incoherent for rows belonging to order B even if A and B share owner and yard.

Worked example (Batch 2 rev 6): Sonangol rows 1186-1188 at HD Hyundai Samho looked like one 3-ship cluster, but the backend data showed row 1186 has Contract=30-Jan-2026, Delivery=2028 while rows 1187-1188 have Contract=07-Apr-2026, Delivery=2029. Trade press confirms these are two distinct orders ($245m single ship + $511m two-ship pair). Citations must be split: first-order URL only on row 1186, second-order URLs only on rows 1187-1188.

The verification gate in §3.8 catches URLs that don't load or don't contain ANY of the expected substrings. Rule E is stricter: it requires the URL to be coherent with this specific cluster, not just "about the topic in general." Verification expected-substrings should be cluster-specific (owner + yard + hull-count or contract-date), not just topical (e.g. "LNG" or "Hudong").

### 4.13 Rule F — Never fill a [ref] without a corresponding data value

**The core rule.** A `[ref]` cell exists to cite a specific data value in its paired data cell. Therefore a `[ref]` is filled ONLY when its paired data cell either (a) already contains a value in the backend, or (b) is being populated in the same change set (as a candidate fill, see below). An empty data cell + a populated `[ref]` cell is an "orphan citation" and is PROHIBITED.

**Two sub-rules govern what a citing URL must contain:**

**(i) Cluster coherence.** The URL must name the cluster (per Rule E §4.12 — owner + yard + ship count or contract date).

**(ii) Value presence.** The URL must explicitly contain the data value being cited, in its page body. Specifically:
- **Capacity [ref]** URL must contain the capacity figure (e.g. "174,000" or "174,000 cbm" or "174,000 cubic metre")
- **Delivery year [ref]** URL must contain the delivery year (e.g. "2028" or "2029" or a phrase like "delivery in 2029")
- **Contract date [ref]** URL must contain the contract date or month
- **Price [ref]** URL must contain the price figure
- **Operator/charterer [ref]** URL must explicitly name the operator/charterer
- **Status [ref]** URL must explicitly state or imply the on-order/active/proposed status (typically present in any trade-press contract article)
- **Cargo type / Vessel type / Propulsion type [ref]** URL must contain the specific type value
- **Hull number [ref] / Name [ref] / IMO number [ref]** — see Rules A, B, and §9 respectively for the value-presence requirement

Rule F is strictly stronger than Rule E: Rule E says "URL must name the cluster"; Rule F says "URL must also contain the specific data value being cited AND the paired data cell must hold that value." Both must pass.

**Workflow consequence for blank data cells (the orphan-prohibition consequence).** If the backend data cell is BLANK, do NOT fill its `[ref]` standalone. Instead:
1. Search for the value in cluster-coherent sources
2. Verify the URL explicitly contains the value
3. Propose BOTH the value AND the URL as a paired candidate fill in `QA_review > Candidate data-value fills`
4. Leave the `[ref]` cell blank in the workbook until the user accepts the candidate value into the backend

The user reviews the candidate fill, accepts or rejects it, and if accepted, enters the value into the backend data cell — at which point the URL becomes a valid `[ref]` (since it now matches a backend value).

Per §4.9 backend data cells are never auto-edited. Rule F closes a loophole where a `[ref]` could be filled while its paired data cell stays empty, leaving an orphan citation pointing at nothing in the backend.

**Restatement for emphasis.** The previous version of Rule F (rev 5) implicitly allowed some orphan citations as long as the URL contained the value. The current version (rev 11) closes this: a populated `[ref]` next to a blank data cell is a Rule F violation under all circumstances, even if the URL is otherwise impeccable. If you find yourself wanting to cite something the backend doesn't yet record, the right output is a candidate data-value fill — never a `[ref]` cell on its own.

Examples of Rule F violations seen in practice:
- **Capacity [ref] for blank Capacity cells** (Batch 2 rev 4 retrospective): rows 1189-1192 had Capacity [ref] filled with BGT/Glovis URLs that DO contain "174,000", but the backend Capacity column was blank. Fix: surface "174,000 cbm" as a candidate data fill paired with those URLs, leave Capacity [ref] blank until the value is entered.
- **Operator [ref] for blank Operator cell** (Batch 2 rev 4 retrospective): row 1189 had Operator [ref] filled with Glovis URLs naming "Itochu", but the backend Operator column was blank. Fix: surface "Itochu" as a candidate Operator fill paired with the URLs, leave Operator [ref] blank.
- **Hull [ref] in a discovery workbook where Hull column is blank** (Discovery batch 1 retrospective, 2026-05-19): candidate rows for the BW/Hayfin/TMS Cardiff/Seapeak/MISC May-2026 clusters had Hull [ref] / Name [ref] / IMO [ref] populated with trade-press URLs even though those data columns were blank for the candidate rows. Fix: leave those `[ref]` cells blank; the URLs belong only on cells whose paired data value is actually populated in the same row (e.g. Shipowner, Shipbuilder, Contract date, Delivery year, Capacity, Vessel type, Status).

Coherence + value-presence + populated-data-cell is the norm: a citation that doesn't paint a complete picture (URL names the cluster, URL contains the specific value, value is present in the same row's data cell) shouldn't go into a `[ref]` cell.

### 4.14 Owner / charterer names match the backend's existing stylization

When you write a `Shipowner` or `Operator/charterer` value (a discovery candidate row, or a candidate data-value fill in [ref]-fill mode), stylize the name **exactly as the backend already spells it**, and prefer the **short canonical form** the sheet already uses. Don't introduce a longer legal name when a short one is established.

- Example: the backend writes `COSCO` (and `MOL, COSCO`), so write **`COSCO`** — not `Cosco Shipping Energy Transportation`.
- The canonical short forms and their variants live in `refdata/owner_charterer_map.md` (human-readable) and `scripts/normalize.py` (`_OWNER_DISPLAY`, queried via `display_owner()`). When you settle an owner's stylization, record it in both.
- This keeps cluster-coherence (Rule E) and the dedup index aligned — the same owner must read the same way in every row.

### 4.15 Multiple URLs in one cell are joined with `", "`

When a single `[ref]` cell carries more than one URL, separate them with a comma-space (`", "`) — never a newline. URLs never contain `", "`, so the cell stays unambiguous and copy-pastes cleanly into the backend. `build_workbook.py` enforces this in both modes (and defensively rewrites any newline-joined `[ref]` value to `", "`). QA-narrative fields that deliberately mix URLs with parenthetical notes (e.g. the provenance log's `source_urls`) are exempt — those stay `" ; "`-separated for readability.

---

## 5. Confidence labels

The sourcing standard, in order of preference:

1. **Ideal:** 2 cross-checked URLs that agree on the data value AND both contain the value verbatim in their page bodies. This is the cleanest state and what we aim for whenever practical.
2. **Sufficient:** 1 URL when the URL is explicit (page body contains the data value verbatim AND names the cluster per Rule E) AND/OR the URL is a primary/regulatory source (DART filing, Bursa Malaysia disclosure, yard press release, owner press release, classification society register). One authoritative source carrying the value verbatim is acceptable.
3. **Insufficient:** 1 trade-press URL that names the cluster but doesn't contain the data value verbatim; 1 URL with weak attribution (broker channel only, no published filing or PR); inconsistent sources that disagree on the value.

The confidence labels:

- **Green**: Either (a) 2+ cross-checked sources agree on the value AND both contain the value verbatim, OR (b) 1 source that is explicit (value verbatim + cluster-coherent) and/or primary/regulatory (DART, Bursa, yard PR, owner PR, class society). Rule F still requires the paired data cell to be populated.
- **Yellow**: Entity-level confirmation (correct yard, correct owner, correct order) but the cited value is implied, contested across sources, or appears in only one non-primary source without verbatim text. Also used when broker attribution carries a critical fact (like the actual buyer behind a DART "Oceania" euphemism) that no public source yet confirms verbatim.
- **Red**: Single source, weak corroboration, or sourcing chain that depends on something not yet publicly published. Avoid — prefer leaving blank with a search log per §6a.9.

**ChinaShipBuild + trade press together default to Green** when both confirm. ChinaShipBuild alone, when it contains the specific data value (hull number, contract month, capacity), is sufficient for Green on its own under (2) above because CSB is treated as authoritative for shipyard orderbook facts.

**Note on URL count vs source quality.** The standard above is about meaningful corroboration, not URL accumulation. Adding a third URL that doesn't change confidence ("Maritime Gateway repackaged Splash247's article") adds noise without value. Pick the URLs that actually do work — preferably 2 that independently confirm — and stop.

---

## 6. ChinaShipBuild navigation

### 6.1 Access method
`web_fetch` fails on chinashipbuild.com (missing User-Agent header). Use bash + curl:

```bash
curl -sL -A "Mozilla/5.0" "URL" -o /tmp/page.html
```

### 6.2 Entry points

**Master directory of 382 yards (paginated, 8 pages alphabetical):**
- Page 1: `http://www.chinashipbuild.com/shipyards.aspx`
- Page 2: `http://www.chinashipbuild.com/shipyards.aspx?nmkhTk8Pl4ENaoklppLwi94cgapoljjlSLPHH4c`
- Page 3: same URL ending in `4X`
- Page 4: same URL ending in `4F`
- Page 5: same URL ending in `4b`
- Page 6: same URL ending in `4B`
- Page 7: same URL ending in `4C`
- Page 8: same URL ending in `4s`

**Stable per-yard URLs verified for batch-relevant yards:**

| Yard | URL |
|---|---|
| Samsung HI | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcbganmkhTk8Pl4EN` |
| Hanwha Ocean | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJXanmkhTk8Pl4EN` |
| Hyundai HI, Ulsan | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccbanmkhTk8Pl4EN` |
| Hyundai HI, Samho | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccCanmkhTk8Pl4EN` |
| Hyundai HI, Mipo | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccBanmkhTk8Pl4EN` |
| Jiangnan Shipyard | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFcanmkhTk8Pl4EN` |
| Hudong-Zhonghua Shipbuilding | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFXanmkhTk8Pl4EN` |

These URLs are persistent (confirmed across multiple sessions). For yards not on this list, paginate the master directory.

### 6.3 Yard page layout
Each yard page lists:
- The yard name and parent company
- A "Records: N" count
- An orderbook table with: row number, Ship's Name/Hull No., Vessel Type, Owner Company, Shipyard, Delivery (YYYY-MM), Contract Date (YYYY-MM)
- Pagination (25 rows per page); pagination URLs append `aORDERBOOK4c`, `aORDERBOOK4X`, `aORDERBOOK4J`, etc. to the yard token

**Pagination can split a single owner's cluster across pages.** Don't assume that all hulls for one owner sit on one page. CMHI Haimen (verified 2026-05-27) splits the 8-hull Celsius Shipping order across pages 1 and 2: hulls -01, -02, -03, -05, -06, -07, -08 on page 1; hull -04 on page 2. Before concluding that a backend hull is missing from CSB (and triggering §6a fallback or a status-update flag), sweep **every page** of the yard's orderbook. A hull missing from page 1 alone is not yet a §6a trigger.

### 6.4 Hull number formatting on CSB
Each yard uses its own hull-label convention. Examples:
- Samsung HI: `Samsung 2775`
- Hanwha Ocean: `Hanwha Ocean 2623`
- Hyundai HI Ulsan: `Ulsan 3635`
- Hyundai HI Samho: `Hyundai Samho H8340`
- Jiangnan Shipyard: `Jiangnan H2950`
- CMHI Haimen: `CMHI CMHI-282-01` (yard prefix + hull series + sub-hull number)

When verifying that a CSB URL contains a hull, use the full label including the yard prefix, not just the hull digits — searching for "2773" alone can match unrelated text.

**Normalize hyphens before matching.** CSB renders hyphens inconsistently within and across pages — page 1 of CMHI Haimen displays `CMHI-282-04` with ASCII hyphens (U+002D), page 2 displays the same hull as `CMHI－282-04` with a fullwidth hyphen (U+FF0D) between the yard prefix and the hull series. A naive `grep "CMHI-282-04"` against page 2 misses this. Either normalize both `－` (U+FF0D) and `-` (U+002D) to a single character before comparing, or build matching regex that accepts both. The `csb_fetch.py` parser should normalize at parse time so downstream comparison logic doesn't have to think about it.

### 6.5 Cross-checks worth running
CSB orderbook rows give us independent values for: owner, capacity (rounded to nearest 1000 cbm), delivery (month precision), contract date (month precision). These often surface backend errors. For Batch 1, CSB cross-check found:
- Capacity discrepancy on H8340/H8341 (backend 174k vs CSB 175k vs trade press 177k)
- Delivery year error on H8341 (backend 2029 vs CSB 2028-11)
- Owner-convention difference on Jiangnan rows (backend legal owner vs CSB commercial operator)

---

## 6a. Alternative hull-source navigation (fallback for Rule A)

When CSB does not yet list a hull, run the recipes below in roughly this order. Stop as soon as ONE source explicitly contains the hull number — that satisfies Rule A and can be cited as the `Hull number [ref]`.

### 6a.1 Targeted search recipes (cheap, run first)

Run 2–4 of these per hull, varying the format because each yard's hull label looks different in trade press vs filings:

```text
"Samsung 2783" Celsius
"SHI 2783" LNG
"Hull 2783" Samsung LNG
"Hanwha Ocean 2625" Maran
"Hanwha 2625" LNG carrier
"Ulsan 3639" NYK Cheniere
"HHI 3639" LNG
"Hyundai Samho H8360" Glovis
"H2014A" Hudong MISC
"Jiangnan H2971" Eastern Pacific
```

Combine the hull label with the owner or charterer name; combine with the contract date or contract value. Search variants for Korean yards include `site:dart.fss.or.kr [hull]`, `site:kind.krx.co.kr [hull]`, and the Korean-language spelling of the yard.

If a generic web search returns a result with the hull number, ALWAYS fetch the page and grep for the exact hull string (including the yard prefix per §6.4) before citing.

### 6a.2 DART — Korean Financial Supervisory Service filings

**URL:** `https://dart.fss.or.kr/dsab007/main.do` (English variant at `https://englishdart.fss.or.kr/`)

Korean-listed shipbuilders are legally required to file material-contract disclosures within hours of contract signing. Companies to search:

| Yard | DART entity name (Korean / English) |
|---|---|
| Samsung HI | 삼성중공업 / Samsung Heavy Industries |
| Hanwha Ocean | 한화오션 / Hanwha Ocean Co., Ltd. |
| HD Hyundai Heavy Industries | HD현대중공업 / HD Hyundai Heavy Industries |
| HD Korea Shipbuilding & Offshore | HD한국조선해양 / HD Korea Shipbuilding & Offshore Engineering |
| HD Hyundai Samho | HD현대삼호 (parent: HD한국조선해양) |

Search the company's filings list (`회사별검색` / "Company Search") for the filing date matching the contract date. The "단일판매ㆍ공급계약체결" ("Single Sales/Supply Contract Conclusion") filing type is the one to look for. URL pattern for individual filings is `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=YYYYMMDD......` and the actual contract body loads via `/report/viewer.do?rcpNo=...&dcmNo=...` (the dcmNo is found in the JavaScript on the main.do page; encoding is EUC-KR — convert with `iconv -f EUC-KR -t UTF-8`).

**Empirical limitation found in the 2026-05 pilot (worth knowing):** DART's "Single Sales/Supply Contract Conclusion" filings use a standardized Korean securities-law template that includes contract value (KRW), counterparty region (e.g. "Americas-region carrier"), contract start/end dates, and contract type (e.g. "LNGC 4척" = "LNGC 4 ships"). **They generally do NOT include hull numbers.** This means DART:
- ✅ Confirms the contract value, parties, date — useful for `Shipowner [ref]`, `Status [ref]`, `Capacity [ref]` (indirectly), `Delivery year [ref]`
- ❌ Does NOT typically satisfy Rule A for `Hull number [ref]` because the hull doesn't appear in the disclosure body
- Worth running anyway because: it's authoritative, free, and corroborates contract metadata at higher confidence than trade press alone

If a DART filing DOES contain a hull number in any free-text section ("9. 기타 투자판단과 관련한 중요사항" / "Other important investment matters"), it satisfies Rule A. Always check the free-text bottom of the filing before concluding DART doesn't have the hull.

### 6a.3 KIND — KRX Investor Disclosure System

**URL:** `https://kind.krx.co.kr/disclosure/details.do` and search at `https://kind.krx.co.kr/disclosure/disclosurefulltext.do`

KIND mirrors many DART disclosures in English. Useful when DART's Korean PDFs are hard to parse. Search by company name + date range.

### 6a.4 Classification society newbuild registries

Class societies publish newbuild data publicly:

- **DNV Vessel Register:** `https://vesselregister.dnv.com/` — search by yard hull number or builder
- **Lloyd's Register Class Direct / RightShip:** `https://www.lr.org/en/class-direct/`
- **ABS Record:** `https://www.eagle.org/en/services/portal-and-applications/abs-record-public-search.html`
- **Korean Register:** `https://www.krs.co.kr/eng/srch/srch_main.aspx`
- **Bureau Veritas Veristar:** `https://www.veristar.com/`
- **NK ClassNK Register:** `https://www.classnk.or.jp/register/regships/regships_e.aspx`

For LNG carriers, DNV, LR, BV, and NK are the dominant classes; Chinese yards often pair with CCS (China Classification Society) plus a foreign co-class.

### 6a.5 Yard and parent-company sources

Press releases and investor materials from the yard or its parent often name hulls:

- Samsung HI investor relations: `https://www.samsungshi.com/eng/`
- Hanwha Ocean newsroom: `https://www.hanwha-ocean.com/en/media/news.do`
- HD Hyundai (parent of HD KSOE, HD HHI, HD Samho, HD Mipo) IR: `https://www.hd.com/en/investors`
- Jiangnan Shipyard (CSSC subsidiary): CSSC press releases at `https://www.cssc.net.cn/en/`
- Hudong-Zhonghua (CSSC subsidiary): CSSC press releases

### 6a.6 Owner / charterer sources

When the owner is publicly listed or has an active newsroom, the press release announcing an order often names hulls:

- Knutsen Group: `https://knutsenoas.com/news/`
- Maran Gas Maritime: limited public PR; check Angelicoussis Group
- Capital Product Partners / Capital Gas Ship Management: `https://www.capitalmaritime.com/`
- MISC Berhad: `https://www.misc.com.my/media-center/news` (Petronas subsidiary, KLSE-listed, files Bursa Malaysia disclosures)
- Cool Company: `https://www.coolcoltd.com/news/`
- Sonangol: `https://www.sonangol.co.ao/`
- Eastern Pacific Shipping: `https://www.epshipping.com.sg/news`
- TMS Cardiff Gas: Hadjioannou group; limited public sourcing
- Celsius Tankers: `https://celsiustankers.com/` (limited PR)
- Purus Marine: `https://purusmarine.com/news/`

### 6a.7 Vessel-database newbuild entries

VesselFinder, MarineTraffic, BalticShipping, and Equasis sometimes catch newbuilds before IMO assignment. Search by hull number, yard + hull, or builder + owner. Equasis (`https://www.equasis.org/`) is IMO-backed and free with registration.

### 6a.8 IMO→marine-vessel-tracker lookup (FINAL fallback for hull citation)

This step was added in 2026-05-18 rev 3 after the user demonstrated it works for several Korean newbuilds (Samsung 2783 / 2791 / 2794, Hanwha Ocean 2625 / 2626). Extended in rev 4 to also cover the case where the backend has an IMO but no hull number, with the Name field implying the yard. **Run this step LAST, before §6a.9 documenting a negative result.**

When the backend has an IMO number for a vessel (even a placeholder-looking 7-digit-starting-with-1 ID from a database shared by SFOC), several marine-vessel-tracker sites publish a per-vessel page keyed off the IMO that contains the yard hull label in the page title and body. These pages satisfy Rule A even when CSB, DART, class societies, and trade press do not have the hull.

Confirmed URL patterns (the yard hull label is `HANWHA-OCEAN-{hull}` or `SAMSUNG-{hull}` etc. — replace dashes with the same convention each site uses):

| Site | URL pattern | Notes |
|---|---|---|
| marinetraffic.org | `https://www.marinetraffic.org/ship-owner-manager-ism-data/{YARD-NAME}-{HULL}/{IMO}/1` | Returns title `{YARD-NAME} {HULL} - LNG Tanker, IMO {IMO}`. Cloudflare-protected; may rate-limit headless scrapers but browser access works. |
| marinetraffic.org alt | `https://www.marinetraffic.org/vessels/{YARD-NAME}-{HULL}/{IMO}/1/current-position` | Alternate path for same vessel. |
| marinevesseltraffic.com | `https://www.marinevesseltraffic.com/vessels/{YARD-NAME}-{HULL}/CURRENT-POSITION/{IMO}/1` | Used by backend for Samsung 2783. |
| marinetraffic.org IMO search | `https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={IMO}` | When the hull is unknown, this endpoint resolves the IMO to the canonical per-vessel page and returns its title with the yard label (and hull, if marinetraffic has it). Useful for rows where the backend has an IMO but the Hull column is blank. The HTML body contains a canonical `href="...ship-owner-manager-ism-data/{YARD-LABEL}/{IMO}/1"` link that can be used directly. |

Verification check for this step: fetch the URL and confirm the page title contains both the yard-hull label AND the IMO number. If a 200 response includes this title, Rule A is satisfied — even though "Knutsen" or "Celsius" (the commercial owner) won't appear (marine-vessel-trackers index by technical/shipyard name).

**Use case extension (rev 4, 2026-05-18):** Run this step when the backend Hull column is BLANK but BOTH of these are true:
  1. The backend has an IMO (any format — real 9XXXXXX, or Clarkson-placeholder 1XXXXXX)
  2. The Name column implies the yard (e.g. "Hudong Zhonghua", "Hyundai Samho HI", "Samsung HI Geoje")

In this case use the IMO search endpoint. If the resolved page's title contains the yard name implied by the row's Name field, it satisfies the entity-level [refs] for which the page is authoritative — most directly Shipbuilder [ref], because the page identifies the builder by name and IMO. It also serves as a Name [ref] when the backend Name field is the yard label (e.g. backend Name = "Hudong Zhonghua" matches the marine tracker page's `HUDONG-ZHONGHUA` label). It does NOT satisfy Rule A for Hull [ref] when the backend has no hull data — there's nothing in the backend's Hull column for the URL to be the [ref] of.

**Surfacing previously-unknown hulls:** if the marine tracker page DOES include a hull number that the backend doesn't have (e.g. backend Name = "Hyundai Samho HI" with blank Hull, but the resolved page is titled `HD HYUNDAI SAMHO 8366 - LNG Tanker, IMO 1176351`), that hull "8366" is a **paired candidate data fill** for the backend per §4.13 (Rule F) — propose BOTH the hull value AND the marinetraffic URL as a candidate Hull / Hull [ref] pair in `QA_review > Candidate data-value fills`. Do NOT auto-edit the backend Hull cell. Cite the marine tracker URL for Shipbuilder [ref] and Name [ref] independently (those entity-level facts ARE confirmed by the page even without the hull being in the backend).

**Rate-limit caveat:** marinetraffic.org gates aggressive headless access behind Cloudflare ("Just a moment..." soft-403). If the verifier flags this, do NOT immediately give up — try (a) a different curl User-Agent, (b) a 30-60 second throttle between requests, (c) the marinevesseltraffic.com alternate site. If still blocked, cite the URL anyway IF the URL pattern was previously confirmed at HTTP 200 in this session, and add a traceability note in the citation log instructing the user to spot-check 1-2 URLs in a browser.

For vessels WITHOUT an IMO in the backend, this step does not apply — leave Hull [ref] blank with the §6a.9 search-attempt log, and note "no IMO available for IMO→tracker lookup."

### 6a.9 Documenting a negative result

If the fallback protocol returns no hit, add a row to `QA_review > Per-cell citation log` with action = "blank — searched and not found", confidence = N/A, and a note listing which recipes were tried and the date. Example:

> Row 1170, Hull number [ref], blank — searched `"Samsung 2783" Celsius`, `"SHI 2783"`, DART (Samsung HI filings Mar 2026), DNV Vessel Register, Celsius Tankers news; no public source containing "Samsung 2783" found as of 2026-05-18. Recommend re-running in 1–3 months.

This makes the blank auditable and prevents the next batch from re-searching the same dead ends without context.

---

## 7. Acceptable source roster

### Tier 1 (preferred, can stand alone for general facts; required to pair with CSB for hull-specific facts)
- LNG Prime (`lngprime.com`) — bodies often paywalled but headlines/leads are public; **entity tag list at the bottom is editorially curated** (a tag means the entity is named in the body, including paywalled bodies). Tag attestation supports yellow per §3.8b/§5; pair with a non-paywalled body source for green.
- Splash247 (`splash247.com`)
- Riviera Maritime Media (`rivieramm.com`)
- Seatrade Maritime (`seatrade-maritime.com`)
- TradeWinds
- ChinaShipBuild (`chinashipbuild.com`) — the canonical source for hull numbers WHEN PRESENT

### Tier 1b (regulatory / official — primary sources for hull confirmation when CSB lacks the hull; see §6a)
- DART (`dart.fss.or.kr`) — Korean contract disclosures
- KIND (`kind.krx.co.kr`) — KRX English disclosures
- Bursa Malaysia disclosures (for MISC / Petronas-linked orders)
- Classification society registries: DNV, Lloyd's Register, ABS, KR, BV, ClassNK, CCS
- Equasis (`equasis.org`) — IMO-backed registry

### Tier 1c (yard / owner / charterer official channels — primary sources when they name the hull)
- Samsung HI, Hanwha Ocean, HD Hyundai investor relations and news pages
- CSSC (`cssc.net.cn`) for Jiangnan, Hudong-Zhonghua, Dalian press releases
- Owner / charterer newsrooms (Knutsen, Capital Gas, MISC, Sonangol, EPS, Cool Co, Celsius, Purus, etc.)

### Tier 2 (acceptable corroborators)
- en.portnews.ru
- Ships Monthly
- iMarine (`imarinenews.com`)
- Hellenic Shipping News / Shipping Telegraph
- Maritime Gateway
- Cyprus Shipping News
- UPI
- Seoul Economic Daily (`en.sedaily.com`) — useful for Korean reg filings
- Offshore Energy

### Tier 3 (vessel databases — useful for vessels with real IMOs AND for newbuild entries that may name the hull pre-IMO)
- VesselFinder
- MarineTraffic / marinetraffic.org (the IMO→tracker fallback in §6a.8 uses marinetraffic.org's per-vessel pages)
- marinevesseltraffic.com
- BalticShipping

### Forbidden
- SFOC (any URL)
- GEM (any URL)
- GTT standalone (always pair with non-GTT)

---

## 8. Conflict-handling conventions

When research turns up a value that differs from the backend:

1. **Do not** modify the backend data cell.
2. **Add an entry** to `QA_review > Data-value conflicts` with: row id, field, backend value, research value, source URLs, and a note explaining the discrepancy and recommending action.
3. **Continue citing the [ref] column** — use the URL that supports the backend's value if possible; if no source supports the backend's value but multiple sources support the research value, leave the `[ref]` blank and flag the entire row.

Categories of conflict seen in Batch 1:
- **1-day contract date drift**: backend Jan 5 vs trade press Jan 6 — typically Korea-time signing date vs disclosure date. Minor; document and move on.
- **Capacity mismatch**: backend 174,000 vs source 177,000 — material; flag for update.
- **Delivery year mismatch**: backend 2029 vs source 2028-11 — material; flag for update.
- **Owner convention difference**: backend legal owner vs source commercial operator — usually both correct; document for transparency.
- **Resolved-on-second-look**: an earlier flag turns out to be wrong (e.g. "by Jan 2029" actually means delivery November 2028). Mark RESOLVED but keep the entry for traceability.

---

## 9. IMO number handling

Real IMO numbers are typically 7 digits starting with **9** (or **8** for very old vessels). The backend ALSO contains IMOs that start with **1** (e.g. `1157109`, `1158696`, `1159195`). **These are not Clarkson placeholders** — they are real, indexed IMOs assigned to newbuilds before delivery. Marine vessel databases (notably marinetraffic.org) index them and serve per-vessel pages keyed off the IMO. (Confirmed 2026-05-18 across rows 1148-1155: all eight 1XXXXXX IMOs in the batch resolved to live per-vessel pages with matching yard-hull labels.)

Procedure for every blank `IMO number [ref]` cell:

1. Run the §6a.8 IMO→marine-vessel-tracker lookup. The simplest entry point is the marinetraffic.org IMO search endpoint:
   ```
   https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={IMO}
   ```
   This page contains a canonical link to the per-vessel page at:
   ```
   https://www.marinetraffic.org/ship-owner-manager-ism-data/{YARD-LABEL}-{HULL}/{IMO}/1
   ```
   The canonical per-vessel URL is the one to cite (not the search endpoint).

2. Verify the page passes §3.8 (HTTP 200 + IMO appears in body) AND Rule E (the page's yard-hull label matches the row's Name / Hull / Shipbuilder fields). If both pass, cite as **Green**.

3. If marinetraffic.org gates the request (Cloudflare soft-403), retry with the alternate sites listed in §6a.8 (marinevesseltraffic.com, marinetraffic.org `/vessels/...` path).

4. If no marine database has the IMO indexed AND no other source (VesselFinder, Equasis, BalticShipping) contains it: only then leave `IMO number [ref]` blank, and document the negative result per §6a.9.

5. **Cross-check the value.** If a database has a DIFFERENT IMO for the same vessel (different number but same yard+hull), flag in `QA_review > Data-value conflicts` — do not overwrite per §4.7.

The previous heuristic ("7 digits starting with 1 = placeholder, leave blank") was wrong. Always look up the IMO before assuming it's a placeholder.

---

## 10. Batch packaging

Per batch:
- Confirm row range with the user
- Confirm batch size (default 20 rows)
- Confirm whether to redo prior batches if rules change

Output: one xlsx per batch, written to `batches/<batch-dir>/`. Each batch is a fresh directory, committed to the repo — the history lives in git, not in a single growing file.

After build, run `recalc.py` to verify zero formula errors, then write `notes.md` and commit the batch directory. Do not `git push` without user approval.

---

## 11. Pause-and-ask triggers

Stop research and ask the user before proceeding when:

- ChinaShipBuild access fails AND the §6a fallback protocol has been exhausted for at least one cluster without success (a single CSB failure is no longer an escalation — run the fallback first)
- A whole class of backend values looks systematically wrong (e.g. all IMOs in a range)
- A new rule could change prior batches — ask whether to redo
- A research finding suggests backend rows may be missing entirely (e.g. Batch 1 surfaced a March 2026 Celsius order that may not be in backend)
- Source corroboration is too thin to support even a yellow citation even after the §6a fallback protocol has been tried

---

## 12. Operational tips

Practical reminders that aren't codified elsewhere as rules.

**`web_fetch` vs `bash + curl`.** `web_fetch` doesn't send a User-Agent that chinashipbuild.com requires. Always use `curl -A "Mozilla/5.0"` for that domain.

**Google Sheets CSV export.** Blocked by robots.txt for `web_fetch`. Use `curl -A "Mozilla/5.0" "URL" -o file.csv`.

**Don't assume non-9XXXXXX IMOs are placeholders.** The backend often has IMOs starting with 1 (e.g. 1157109). Per §9, always look these up via §6a.8 — they are typically real, indexed IMOs for newbuilds.

**Cluster by order, not by row.** One contract announcement covers 2–4 sister hulls. Search once per cluster, not once per row.

**The CSB cross-check is cheap and catches real errors.** One curl per yard = 5–6 curls per typical batch = ~30 seconds of work that surfaced 3 material backend errors in Batch 1. See §6.5 for the cross-check fields (owner, capacity, delivery month, contract month).

---

## 13. Changelog

- **rev 1** (2026-05-16): Initial SOP after Batch 1.
- **rev 2** (2026-05-18): Added §3.8 URL verification gate and Rule D §4.11 after Batch 2 rev 1 shipped with broken URLs.
- **rev 3** (2026-05-18): Added §3.0 BACKEND-PRIORITY workflow step, Rule E §4.12 cluster-coherence, and §6a.8 IMO→marine-vessel-tracker fallback.
- **rev 4** (2026-05-18): Extended §6a.8 to cover rows with IMO but no hull (yard confirmation via tracker title). Applied to TMS Cardiff and Sonangol rows.
- **rev 5** (2026-05-18): Added Rule F §4.13 — refs must explicitly contain the data value, not just describe the cluster. Closed the orphan-citation loophole.
- **rev 6** (2026-05-18): Extended Rule E §4.12 with cluster-split detection (divergent Contract date / Delivery year within shared owner-yard → separate clusters). Added §3.8a 404-sweep for pre-existing backend refs.
- **rev 7** (2026-05-18): Applied rev 6 cluster-split detection to Sonangol rows 1186-1188 (12 cell overrides). No rule changes; defect correction only.
- **rev 8** (2026-05-18): Housekeeping pass — renumbered §6a sections (6a.8 = IMO tracker, 6a.9 = negative-result documentation); updated §2.2/§2.3 to reflect current workbook structure; fixed stale `team_notes` and Hull-specific verification references; tightened document-purpose line. No rule changes.
- **rev 9** (2026-05-18): Consolidation pass — merged Rules A/A.1/C into a single §4.4 with three numbered parts; collapsed Rule D §4.11 to a pointer (failure modes moved into §3.8 where the gate lives); cut §12 lesson restatements that duplicated codified rules, leaving only operational tips not covered by any rule; added this changelog (§13). No rule changes.
- **rev 10** (2026-05-18): Corrected §9 (and the §4.10 pointer) — non-9XXXXXX IMOs are NOT placeholders from a database shared by SFOC, they are real IMOs indexed by marine vessel databases. The previous "leave blank and flag" procedure caused fillable `IMO number [ref]` cells to be incorrectly skipped. New procedure: always run the §6a.8 IMO→marine-vessel-tracker lookup on the IMO itself before concluding it isn't citable. Confirmed empirically against rows 1148-1155 (8/8 IMOs resolved to live per-vessel pages with matching yard-hull labels).
- **rev 11** (2026-05-19): Tightened Rule F §4.13 — a `[ref]` cell is filled ONLY when its paired data cell either already has a value or is being populated in the same change set. The previous version (rev 5) implicitly allowed cases where a URL contained the value but the paired cell stayed blank; this rev closes that loophole. Orphan citations (populated `[ref]` next to a blank data cell) are now prohibited under all circumstances. Surfaced by the candidate-vessel discovery workbook (2026-05-19), which had filled Hull / Name / IMO `[ref]` cells with trade-press URLs even though the paired Hull / Name / IMO data cells were blank for those just-announced vessels. Restatement of Rule F also pulled out the "two sub-rules" structure (cluster coherence + value presence) for clarity. No other rule changes; §4.13 examples were extended with a discovery-workbook example.
- **rev 12** (2026-05-19): Relaxed the sourcing standard in §5 (Confidence labels). The previous version required either "multiple independent sources directly identify the specific vessel" or implied a 3+ source threshold for Green. The new standard: ideally 2 cross-checked URLs that agree AND both contain the data value verbatim, but 1 URL is sufficient when it's explicit (value verbatim + cluster-coherent) and/or primary/regulatory (DART, Bursa, yard PR, owner PR, class society). Added a note on URL count vs source quality — corroborate meaningfully, don't accumulate. Rule F, Rule E, and Rule A are unchanged.
- **rev 13** (2026-05-26): Clarified §4.8 — geolocation columns (lat, lon, plus code, accuracy, lat/lon [ref]) remain out of scope for research (never populate them), but per Discovery SOP §5.2/§6.6 they appear in the candidate_vessels sheet as blank columns to preserve backend column order for paste-compatibility. No change to the [ref]-Fill workflow itself; this is purely a cross-reference clarification.
- **rev 14** (2026-05-27): Added two CSB navigation refinements after a reconciliation false-positive on Hull CMHI-282-04. §6.3 — pagination can split a single owner's cluster across pages, not just split by date; before flagging a hull as missing from CSB (and triggering §6a fallback), sweep every page of the yard, not just page 1. CMHI Haimen verified as concrete case: 8-hull Celsius cluster split with -01/02/03/05/06/07/08 on page 1, -04 on page 2. §6.4 — CSB renders hyphens inconsistently between fullwidth (U+FF0D `－`) and ASCII (U+002D `-`), sometimes mixing both within the same hull label across pages of the same yard; hull-matching needs to normalize both to a single character before comparing. No rule changes; this is parser-level navigation guidance.
- **rev 15** (2026-05-27): Added §3.8b — QA notes quote only publicly-visible content; paywalled body text is never quoted in a QA note. Editorial entity tags on LNG Prime (and any other site whose tags are editorially curated rather than auto-generated) pass §3.8 content verification and support yellow confidence per §5, but support green only when paired with a second source naming the same entity in publicly-visible content. Surfaced by a 2026-05-27 F8 finding that quoted paywalled LNG Prime body text the verifier couldn't see — the underlying Woodside attribution turned out to be correct (corroborated by LNG Prime's editorial Woodside tag), but the quoted body sentence was unverifiable and on its face indistinguishable from fabrication.
- **rev 16** (2026-05-28): Repository migration. Output model changed from a single rolling xlsx at `/mnt/user-data/outputs/` to one committed directory per batch under `batches/` (§2, §10). Scratch-file paths now resolve via `scripts/paths.py` (work directory defaults to `<repo_root>/work/`). `present_files` references replaced with "commit the batch directory" throughout (§3.6, §3.8, §10). No research-rule changes — the §3.8 verification gate, Rules A–F, the §6a fallback protocol, and the §5 confidence labels are byte-for-byte unchanged in substance.
- **rev 17** (2026-06-03): Added three output-formatting rules surfaced during the first production discovery batch (2026-06-03). §4.14 — `Shipowner` / `Operator/charterer` values use the backend's existing stylization, preferring the established short form (write `COSCO`, not `Cosco Shipping Energy Transportation`); recorded in `refdata/owner_charterer_map.md` and `scripts/normalize.py` (`_OWNER_DISPLAY` / `display_owner()`). §4.15 — multiple URLs in one `[ref]` cell join with `", "`, never a newline; enforced in `build_workbook.py` (both modes), QA-narrative fields exempt. §4.8 carve-out — the seven yard-location columns are never *researched* but may be *mirrored* from an existing backend row for the same shipbuilder (a deterministic copy); discovery autofills them automatically (Discovery SOP §6.7), [ref]-fill surfaces them as a paired candidate fill. No research-rule changes — the §3.8 gate, Rules A–F, the §6a fallback, and §5 confidence labels are unchanged.
