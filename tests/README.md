# Tests

Regression tests for the scripts. Run with `pytest tests/` from the repo root (after `pip install -e ".[dev]"`). `conftest.py` puts `scripts/` on `sys.path`, so the flat module names (`import normalize`, `import url_verifier`) resolve without installing the package.

## Current coverage

| Module | Status | File |
|---|---|---|
| `normalize.py` | ✅ covered — builder/owner/hull canonicalization, `display_owner`, `owner_country` sibling-copy | `test_normalize.py` |
| `url_verifier.py` | ✅ covered — the §3.8 gate (banned URL shapes, HTTP status grades, soft-error vs bot-wall titles/body markers, Wayback fallback, redirect re-check incl. slug drift, PDF text, normalised/numeric-boundary matching, §3.8c corroboration, audit log, shipvault / marinetraffic.com host adapters), offline via seeded `_CACHE` + a fetch stub that fails loudly on any network call | `test_url_verifier.py` |
| `fetch.py` + `cf_clearance.py` | ✅ covered — the bot-wall escalation ladder (wall detection for Cloudflare / AWS WAF / Imperva incl. the empty 202, `curl_cffi` impersonation, clearance-cookie retry with the cookie's own UA and the real status behind the wall, one Chrome launch per host, `LNGCT_NO_BROWSER`), the cookie store (multi-cookie header, domain join, legacy single-value entries, expiry, forget, `merge_cookies` keeping only wall cookies), ZIP bundles and the empty-PDF re-fetch, with `_curl` / `_cffi_get` / `refresh` stubbed and the store in a temp dir | `test_fetch.py` |
| `sweep.py` | ✅ covered — per-host pacing (tracker floors, jitter, elapsed time counted), the circuit breaker (consecutive `000`/429/403, fetch exceptions, the 404s-after-200s soft-block trip, per-host isolation, re-trip after an earlier run's trip), skipped-URL records, `--max`, resume (latest record wins), CLI input parsing — with a scripted fetch and injected sleep / clock / jitter | `test_sweep.py` |
| `ais_static.py` | ✅ covered — `ShipStaticData` parsing against canned messages shaped like a real aisstream capture (padding cleanup, ship-type labels, IMO 0 / non-integer never matching), the client-side IMO filter, write-once-per-identity + rename re-write, error frames, the listen loop (subscription, deadline, early stop, reconnect, give-up) over a fake websocket with injected clock / sleep, backend watch list with live sheet rows, key lookup (env, keychain stubbed) | `test_ais_static.py` |
| `igu_fleet.py` + `igu_reconcile.py` | ✅ covered — extractor row assembly from synthetic word coordinates (wrapped cells, `Unknown` IMOs opening a row, the last row stopping at a gap, hyphen wraps, IMO check digit), field comparison (name `(ex-…)` tails, owner tokens, learned builder pairs, capacity tolerance), diff `kind` + pending-batch agreement, status findings incl. the delivery-year conflict, every bucket of `reconcile()` (no-IMO rows get cluster hints, never pairs), leads loading + the review-IMO list, and the `--mode igu` workbook's sheet set — no PDF and no network | `test_igu_reconcile.py` |
| `pull_backend.py` | ⬜ planned — needs `fixtures/backend_csv/` schema snapshots | — |
| `csb_fetch.py` | ⬜ planned — needs `fixtures/csb/` HTML snapshots | — |

The ✅ modules are pure logic / network-free, so they're tested directly. The two ⬜ modules need captured fixtures (below) before they can be tested without hitting the network — add those when CSB or the backend schema next changes under you and you have a fresh snapshot to freeze.

## Why tests exist for this project

The fragile parts of the tooling are exactly the parts where the external world changes out from under us:

- **`pull_backend.py`** — the backend schema drifts (columns get added/renamed); the column-index map derivation has to keep working. Test against fixture CSVs that capture each known schema variant.
- **`csb_fetch.py`** — ChinaShipBuild changes their HTML layout occasionally. Test against cached HTML snapshots in `fixtures/csb/`. When CSB breaks the parser, save the new HTML as a new fixture and update the parser.
- **`url_verifier.py`** — the §3.8 verification gate's soft-error detection has caught Riviera's 200-with-429-body pages and similar. New patterns surface over time. Each pattern should get a fixture.
- **`normalize.py`** — when we add a new owner/charterer, the canonical name resolution shouldn't break existing clusters. Test the variant-to-canonical mapping exhaustively.

## What NOT to test

- Live HTTP. Tests should never hit the network. If a test calls out to chinashipbuild.com directly it's flaky and slow — use a fixture.
- The xlsx output byte-for-byte. Test structure (sheet names, cell colors, frozen panes, expected formulas) not exact bytes — openpyxl output isn't deterministic across versions.

## Fixture organization

```
tests/fixtures/
├── backend_csv/
│   ├── 2026-01-15_pre_may_column.csv     # before "checked for May update" column
│   ├── 2026-05-20_post_may_column.csv    # after the column was added
│   └── ...
├── csb/
│   ├── samsung_2026-05-15.html           # snapshot per yard per date
│   ├── samsung_2026-05-15.expected.json  # what the parser should produce
│   └── ...
└── verifier/
    ├── lngprime_paywalled.html           # public lead visible, body gated
    ├── riviera_429_softerror.html        # 200 status, body says rate-limited
    └── ...
```

When you add a new fixture, give it a date-stamped name so the chronological order is obvious.
