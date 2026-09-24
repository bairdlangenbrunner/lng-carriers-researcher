# fix — Mozambique builder/owner + BW three-tank capacity

Built 2026-09-23 17:07 ET. Mode: `fix`. 19 rows / 28 cells, 0 refs dropped by the §3.8c gate.

Companion to `batches/2026-09-23_1546ET_discovery_comprehensive/`. That batch shipped with its
Ring B/C/D sweeps incomplete — the session exhausted the shared 200-call WebSearch budget (see
Discovery SOP §4.1a, rev 9). This batch is the product of the re-run that closed that gap.

## The re-run found zero new vessels

All three re-swept rings came back empty of discovery candidates. Recording the *reason* for each,
because an unqualified null is what the first pass wrongly shipped:

| ring | result | why |
|---|---|---|
| B — regulatory | no candidates | DART / KIND / Bursa / HKEX primary portals are JS/POST-driven and unreachable through the GET-only fetch ladder; sedaily used as an English proxy. Nearest miss: Samsung HI's $1.2bn 4×LNGC + 2 tanker order, dated **2026-09-14**, three days outside the window. |
| C — trade press | no *new* vessels | One in-window story (BW LNG, below) resolved to a **dedup hit** on four rows already in the backend. |
| D — charterer programmes | no candidates | All three named vessels already in the backend — `Clean Energy` (sheet 153, IMO 9323687), `Arctic Aurora` (sheet 304, IMO 9645970), `Clean Rio Grande` (sheet 1005, IMO 9994034). Commonwealth LNG (now "Caturus") and Argent LNG do not meet the proposed-bucket threshold. |

Ring B and C portal/paywall walls are **reachability limits, not evidence of absence** (RF §3.8a).

### The BW LNG "new order" was already in the backend

new-ships.com (2026-09-18) reports BW LNG contracting HD Hyundai for **four** three-tank LNG
carriers, ~176,800–177,000 cbm, deliveries Q4 2028 → Q3 2029. That is not a new order — it is
coverage of the four hulls the backend already holds as two pairs:

| hull | sheet | row_id | contract | CSB delivery |
|---|---|---|---|---|
| H8340 | 1089 | 1148 | 2025-11 | 2028-09 |
| H8341 | 1090 | 1149 | 2025-11 | 2028-11 |
| 8358 | 1165 | 1212 | 2026-05 | 2029-04 |
| 8359 | 1166 | 1213 | 2026-05 | 2029-07 |

CSB's HD Hyundai Samho orderbook carries exactly these four BW hulls and no fifth — confirming the
article's "four" is the combined programme, not an addition. Sheet 1165's own Notes already
identified 8358/8359 as the three-tank pair.

Caveat on the source: `new-ships.com` is **not in `data/source_roster.md`**, and its technical
detail is attributed to a LinkedIn post. It is used here only as a second corroborator behind CSB.

## Corrections in this batch

**1. Mozambique builder — 9 cells, G.** Sheets 1184–1192 (row_ids 888–896) carried Shipbuilder
`HD Hyundai Heavy Industries`. iMarine (2026-07-17) states the 2020 LOIs went to "HD Hyundai Samho
and Samsung Heavy Industries ... for nine and eight vessels, respectively" → the nine are **Samho**.
Sheets 1193–1200's `Samsung Heavy Industries` is correct and untouched. The prior ref
(`imarinenews.com/28729.html`) supported the wrong builder, so it is replaced, not appended.

**2. Mozambique owner — 17 cells, Y (capped).** All 17 rows carried `MOL, NYK`. Source:
"HD Hyundai Samho's orders involve contracts with Mitsui O.S.K. Lines (five vessels) and Kawasaki
Kisen Kaisha (four vessels), while Samsung Heavy Industries' eight vessels are contracted to NYK
Line (four vessels) and Greece's Maran Gas Maritime (four vessels)."

- sheets 1184–1192 → `MOL, K Line`
- sheets 1193–1200 → `NYK Line, Maran Gas Maritime`

Maran Gas Maritime was **absent from the backend entirely** for this cluster. Capped at Y by
`cap_reason`: the source gives the group composition but never assigns individual hulls, so the
MOL(5)/K Line(4) and NYK(4)/Maran(4) splits are not resolvable per row.

Corroborating defect: `imarinenews.com/28729.html`, the ref cited on all 17 rows, contains the
string "NYK" **zero times**. The existing value was not supported by its own citation.

**3. BW three-tank capacity — 2 cells, G.** Sheets 1165/1166 (row_ids 1212/1213) carried
`174000` cbm, the standard four-tank figure carried over from the May-2026 order coverage. CSB's
per-hull ship pages for 8358/8359 both state "LNG Tanker, 177,000 cbm"; new-ships.com corroborates
~176,800–177,000 for the three-tank design. → `177000`.

Sheets 1089/1090 are **not** touched: they already carry 177000 (lngprime + riviera), against CSB's
175,000. Minor unresolved discrepancy, flagged not changed.

## Script fix shipped with this batch

`scripts/url_verifier.py` — the §3.8c gate could not corroborate a **comma-separated multi-owner
cell whose components need aliasing**. `normalize._OWNER_ALIASES` is keyed by single owner name, so
the whole-cell lookup for `"MOL, K Line"` found nothing; the multi-word token fallback then split it
to `["MOL","Line"]` (the `K` dropped as <3 chars) and failed on the literal `MOL`. Net effect:
`corroborates(url, "MOL")` → True and `corroborates(url, "K Line")` → True, but
`corroborates(url, "MOL, K Line")` → False. That is what dropped these 9 refs on the first build.

Fix: a comma-separated value is now corroborated **per component**, each through its own
`value_variants` (so per-owner aliases apply). **Every** component must be present, which makes this
narrower than the token fallback it precedes, not a loosening of it. Numeric values are excluded.
Test added: `tests/test_url_verifier.py::test_multi_owner_cell_corroborates_per_component`, covering
the positive case and two negative controls. Full suite: 580 → 581 passing.

## For Baird

1. **The owner correction is a 17-row rewrite on one trade-press source.** Builder (defect 1) is
   clear-cut; the owner split is well-evidenced but group-level only, hence the Y cap. Worth your
   call before it goes to the sheet.
2. **The gate change** above touches the repo's core safety mechanism. Narrow and tested, but
   flagging it rather than burying it in a batch commit.
3. **Ring B remains structurally unreachable.** DART/KIND/Bursa/HKEX need a POST-capable or
   headless fetch path; the GET-only ladder cannot sweep them. Recurring gap, not a one-off.
4. Ring D surfaced a **data-fill** item, not a discovery one: `Operator/charterer` is blank on
   sheets 153, 304 and 1005, and the sources name Rio Grande LNG. Not included here (fix batches
   carry corrections, not blank-fills) — belongs in a data-fill batch.
5. Open lead still unresolved: no post-July Mozambique slot-reservation update found. TradeWinds
   returns an HTTP 200 shell behind a Zephr subscriber wall — a genuine subscription wall, not a
   clearable bot-block.

## Apply — done 2026-09-23 22:0x ET, directed session write (AP §2d)

Baird, in session: *"go ahead and replae the proposed owner changes in the backend and make sure it
lines up with the living-workbook-for-update. and replace those capacities for 1165 and 1166 too."*
Claude wrote the sheet itself under AP §2d — not a review-app push, and `push_log.jsonl` attributes
every line to `claude session (directed)` with the directive quoted. There is no `review_log.jsonl`
record and §2b will count these lines `unclicked`; that is correct and was not papered over.

**Written: 38 cells / 19 rows** — the 17 Shipowner values (sheets 1184–1200) and the 2 Capacity
values (sheets 1165/1166), each with its paired `[ref]` cell. Fresh pull immediately before the
plan; plan printed cell by cell; revert file `directed_2026-09-23_revert.csv` holds every
pre-write value keyed by A1. `verify_apply.py --pull`: **38 landed, 0 mismatch, 0 missing.**

The Shipowner `[ref]` moves off `imarinenews.com/28729.html` (which never names NYK) and the
Capacity `[ref]` off the sedaily May-2026 order story (which carries the 174,000 four-tank figure)
— both are replacements, not appends, because the outgoing ref does not support the new value.

**The 9 Shipbuilder cells were NOT written.** Baird named the owner and capacity changes; scope
under §2d is exactly what he named, so `HD Hyundai Heavy Industries → HD Hyundai Samho` on sheets
1184–1192 stays a hold in `decisions.csv`. Note the standing oddity this leaves: the owner split
written above is derived from those nine being the *Samho* nine, while the Shipbuilder cell still
says HHI. One word from Baird applies it.

Living workbook aligned the same session: this batch registered as **B17 / apply order 17** in
`build_combined.py` + `review_batches.json`, combined workbook rebuilt
(`lng_carrier_sep-17-pass_results_2026-09-23_2158ET.xlsx`, 2,362 proposals, new `b17_mozambique_bw_rows`
sheet), `living.py --rebuild` in place (same file id / URL). The live sheet now reads
`processed - incorporated` on all 19 written lines, blank on the 9 held Shipbuilder lines, and
`partly processed - 1 of 2` on sheets 1184–1192.

Gotcha found: `living.py --rebuild --xlsx <relative path>` crashes on `Path.relative_to` *after*
the Drive upload has already gone through. Pass an absolute path.
