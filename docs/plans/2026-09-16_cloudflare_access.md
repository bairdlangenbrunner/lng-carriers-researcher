# Cloudflare and bot-wall access — plan

**Date:** 2026-09-16. **Status (evening):** tiers 0–3 landed in
`scripts/fetch.py` + `scripts/cf_clearance.py` with tests; tier 4 (rendered
DOM) was **not built** — the two SPA hosts turned out to expose the JSON the
shell loads, and `url_verifier.py` host adapters read that instead
(shipvault `/api/units/{id}`, marinetraffic.com `vesselInfo/shipid:{id}`),
which is cheaper and gives the verifier structured fields to match.
`imo_tracker.py` now resolves IMOs through shipvault's open search API first.
Steps 1, 2, 5 and 6 below are done; 3 is superseded; 4 and 7 remain.

## What the probes established today

Every blocked host from the Stream 0 rot sweep (`work/citation_qc.csv`,
129 `blocked` URLs) was probed with each candidate route. Results:

| route | clears | does not clear |
|---|---|---|
| `curl -A <Chrome UA>` (tier 0, existing) | ordinary sites | every wall below |
| `curl_cffi impersonate="chrome"` (TLS/JA4 fingerprint) | shipvault.com, seatrade-maritime.com, bairdmaritime.com, marinetraffic.com (SPA shell only) | the JS managed challenge ("Just a moment…") |
| Playwright / patchright Chromium or real Chrome, headless **or headed**, automation flags stripped | dnv.com (headless), chantiers-atlantique (headed) | managed challenge: Turnstile switches to an interactive checkbox, rejects the synthetic click, and issues a loop token (`cf_chl_rc_ni`) whose `cf_clearance` is invalid even in the same browser |
| real Chrome, fresh scratch profile, driven over CDP **without** `Runtime.enable` (nodriver; the in-flight `cf_clearance.py` does the same by hand) | **marinetraffic.org, marinevesseltraffic.com, trusteddocks.com, businesstoday.com.my, dnb.com, dnv.com** — auto-passes in ~5 s, no click | nothing on the list |
| same, headless | — | everything (Turnstile detects headless) |
| `cf_clearance` cookie earned above, replayed by plain `curl` with the earning Chrome's UA | marinetraffic.org, marinevesseltraffic.com (verified through `fetch_page`, note `cf_clearance`) | chantiers-atlantique (its 418 check sets no replayable cookie) |

Two blocked verdicts are not walls at all:

- **investors.seatrium.com** (row 11): Imperva returns an empty HTTP 202 to
  curl, but a real browser lands on a genuine `404 Not Found`. This is
  **dead**, not blocked — it belongs in the Stream 5 fix batch.
- **hls.co.kr**: TLS name mismatch, then HTTP 200 whose body is a "403
  Forbidden" page. Geo/WAF block; keep as blocked.

Alternative sources for the marinetraffic.org lookups (§6a.8): vesselfinder
resolves 9XXXXXX IMOs (404 on 1XXXXXX), shipspotting's IMO search resolves
9XXXXXX through curl_cffi, balticshipping / myshiptracking / fleetmon do not
help, equasis needs a login.

## Design: one escalation ladder inside `fetch_page`

Every script already fetches through `scripts/fetch.py`, so the ladder lives
there and nothing upstream changes. Order is cheapest-first; each step is
recorded in `Page.notes` so the verifier log shows the route.

1. **curl + Chrome UA** (existing).
2. **curl_cffi impersonation** on a Cloudflare firewall page — in-process,
   no window. In flight.
3. **cf_clearance cookie** on a JS managed challenge — earned once per host
   by launching real Chrome with a scratch profile (`work/chrome_profile/`)
   and waiting for the title to change; stored in `work/cf_clearance.json`
   (gitignored — it is a credential-like token bound to this egress IP and
   UA, valid ~1 year). Replayed through plain curl. In flight.
4. **Rendered fetch** — same Chrome + CDP client, but return the rendered DOM
   (`DOM.getDocument` + `DOM.getOuterHTML`, still no `Runtime.enable`).
   Only for content the cookie tier cannot get: marinetraffic.com vessel
   pages (SPA; the curl body is a 3 KB shell, the rendered DOM carries name,
   IMO and particulars) and chantiers-atlantique's 418 check. **To build.**
5. **Route around** — vesselfinder / shipspotting for 9XXXXXX IMOs, Wayback
   for anything with a capture. Existing SOP practice; unchanged.

Unattended runs (CI, cloud agents, `LNGCT_NO_BROWSER=1`) stop at tier 2 and
grade the URL `blocked`. Headless never passes and the cookie is IP-bound, so
there is no unattended route; refresh from the laptop.

## Steps

1. ~~**Land tiers 0–2**~~ — done (committed with tiers 3 and the adapters). Before commit:
   - `pyproject.toml`: add `curl_cffi` and `websocket-client` as an optional
     `[fetch]` extra; note Google Chrome as a system dependency next to curl.
   - Tests: `_is_cf_wall` on the four wall bodies captured today; `cookie_for`
     domain matching and expiry; a fetch_page test that a wall + stored cookie
     replays with the stored UA (mock curl). No live tests.
   - Fix: once a host is in `_IMPERSONATE_HOSTS`, `fetch_page` accepts the
     curl_cffi result even when it is itself a wall (`if got:` should be
     `if got and not _is_cf_wall(...)`, else fall through to the cookie tier).
   - Confirm a stale cookie (network change) falls through to a fresh
     `refresh()` rather than returning the wall.
2. ~~**Refresh clearance for the whole blocked list**~~ — done via the regrade itself (`fetch_page` earns the cookie per host as it meets the wall); counts in the full-pass plan, Stream 0., not just the two
   vessel-tracker hosts: `python scripts/cf_clearance.py <one URL per host>`
   for trusteddocks, businesstoday, dnb, dnv, then
   `python scripts/citation_qc.py --resume --regrade blocked --delay 3`.
   Expected: `blocked` drops from 129 URLs to roughly a dozen (marinetraffic.com
   SPA pages, chantiers-atlantique, hls.co.kr, the .cn outages), and seatrium
   regrades `dead`.
3. ~~**Build tier 4**~~ — superseded by the verifier host adapters (see status). Revisit only if a wall host appears whose data is not reachable as JSON. Original plan: `fetch_rendered(url, wait) ->
   (title, html)` reusing `_launch_chrome`/`_CDP`. Wire into `fetch_page` as
   the step after the cookie retry, only when the body is a known SPA shell
   or a non-Cloudflare JS check (`Checking you are not a bot`, empty body
   with a `<script>`-only head). Note `cf_rendered`. Same `LNGCT_NO_BROWSER`
   gate. Verify marinetraffic.com and chantiers-atlantique through the §3.8
   gate afterwards.
4. **Verifier grading**: a browser-rendered 404 behind a wall grades `dead`
   (seatrium case); a wall that never clears stays `blocked`. Add the
   seatrium row to the Stream 5 fix batch.
5. ~~**A CLI for ad-hoc fetches**~~ — done: `python scripts/fetch.py <url> [--text]`
   printing status, notes and the (text) body, so a Claude session reaches
   any page through the full ladder instead of WebFetch or hand-rolled curl.
6. ~~**Docs**~~ — done (SOP §6a.8 rev 20, roster, CLAUDE.md, README, tests/README):
   - `docs/sops/ref_fill.md` §6a.8 caveat: replace "no scripted workaround"
     with the ladder; marinetraffic.org is scriptable again via tier 3.
   - `docs/plans/2026-09-16_full_research_pass.md` "Blocked (keep)" section:
     supersede with the regrade counts from step 2.
   - `CLAUDE.md` scripts table: add `cf_clearance.py`; add a router line —
     "URL blocked? never conclude from WebFetch/curl alone; run it through
     `scripts/fetch.py` (ladder) before grading it blocked".
   - Consider the same line in the user-global CLAUDE.md escalation ladder
     ("in the researcher repos, use the repo fetch ladder first") — user's
     call, it lives in the `machine` repo.
7. **Port** `fetch.py` + `cf_clearance.py` to lng-terminals-researcher and
   pipelines-researcher once stable (the verifier parity pass went the other
   way on 2026-09-16; keep the three fetch layers identical).

## Conduct

These are public pages cited as `[ref]`s, fetched one at a time with the
existing 3 s delay for verification, never bulk-scraped. Keep the delay,
keep the scratch profile separate from the personal Chrome profile (never
point `--user-data-dir` at it), and never commit the cookie store.
