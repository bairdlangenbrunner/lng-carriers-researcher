# Source roster (quick reference)

Authoritative version: [ref]-Fill SOP §7. This file is for picking sources at query time without re-reading the whole SOP.

## Tier 1 — Preferred (stand-alone for general facts; pair with CSB for hull-specific facts)

| Source | Domain | Strongest at |
|---|---|---|
| LNG Prime | `lngprime.com` | Most comprehensive LNG-specific coverage; many paywalled bodies but headlines/leads usually public. **Editorial entity tags** — the tag list at the bottom of each article is editorially curated, not auto-generated; an entity tag means LNG Prime's newsroom asserts the entity is named in the body (even when the body is paywalled). Supports yellow confidence per [ref]-Fill SOP §3.8b/§5; pair with a second source naming the entity in publicly-visible content for green. Never quote LNG Prime paywalled body text in QA notes (§3.8b). |
| Splash247 | `splash247.com` | Cluster-level wrap-up reporting; one article often covers 3-5 orders |
| Riviera Maritime Media | `rivieramm.com` | Technical detail; **watch for 200-soft-error 429 pages** (verifier catches this) |
| Seatrade Maritime | `seatrade-maritime.com` | Broad maritime coverage |
| TradeWinds | (paywall, but headlines + Google previews public) | Strong on shipbroker attribution — identifies "Oceania-region buyer" → actual entity |
| ChinaShipBuild | `chinashipbuild.com` | **Canonical** for hull numbers when CSB has them indexed |

## Tier 1b — Regulatory / official (primary; satisfies Rule A when they name the hull)

| Source | URL | Notes |
|---|---|---|
| DART | `dart.fss.or.kr` | Korean reg filings. Standardized template often omits hull numbers — check free-text section |
| KIND | `kind.krx.co.kr` | KRX English mirror of DART |
| Bursa Malaysia | direct filings | For MISC / Petronas-linked orders |
| DNV Vessel Register | `vesselregister.dnv.com` | Class society newbuild entries |
| Lloyd's Register | `lr.org/en/class-direct/` | Class society |
| ABS Record | `eagle.org/.../abs-record-public-search.html` | Class society |
| Korean Register | `krs.co.kr/eng/srch/srch_main.aspx` | Class society |
| ClassNK | `classnk.or.jp/register/regships/regships_e.aspx` | Class society |
| Equasis | `equasis.org` | IMO-backed registry; free with registration |

## Tier 1c — Yard / owner / charterer official channels (primary when they name the hull)

| Type | Sources |
|---|---|
| Yards | Samsung HI IR, Hanwha Ocean newsroom, HD Hyundai IR, CSSC press (for Jiangnan, Hudong-Zhonghua, Dalian) |
| Owners | Knutsen, Capital Gas, MISC, Sonangol, EPS, Cool Co, Celsius, Purus newsrooms |

## Tier 2 — Acceptable corroborators

`en.portnews.ru`, Ships Monthly, `imarinenews.com`, Hellenic Shipping News / Shipping Telegraph, Maritime Gateway, Cyprus Shipping News, UPI, `en.sedaily.com` (Korean reg-filing English coverage), Offshore Energy, Marine Link, Maritime Executive, IndexBox.

## Tier 3 — Vessel databases (real IMOs and newbuilds pre-IMO)

- VesselFinder
- MarineTraffic / **marinetraffic.org** (the §6a.8 IMO tracker fallback uses this — see `scripts/imo_tracker.py`)
- marinevesseltraffic.com
- BalticShipping

## Forbidden

- **SFOC** (any URL) — project's data origin, not a citable URL
- **GEM** (any URL, incl. `gem.wiki`) — excluded entirely (GEM is downstream of this tracker; citing it is circular)
- **GTT standalone** — pair with non-GTT source; GTT alone fails Rule 4.3

## English-language proxies for Korean reg filings (faster than parsing DART)

- **Seoul Economic Daily** (`en.sedaily.com`) — fastest English coverage, usually within hours of DART filings
- **Asia Business Daily**
- **iMarine**, **BigGo Finance** — Asia-focused

## Most productive search query patterns

For new orders:
- `LNG carrier newbuild order [month] [year]`
- `[Yard name] LNG carrier order [month] [year]`
- `[Charterer name] LNG carrier program [year]`
- `[Yard] [Owner] LNG newbuild`

For hull lookups (§6a fallback):
- `"Samsung 2783" Celsius`
- `"Hull 8340" Samsung LNG`
- `site:dart.fss.or.kr [hull]`
