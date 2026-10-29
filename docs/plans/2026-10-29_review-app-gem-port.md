# Review app: port onto gem-review-app (phase 3)

Asked by Baird on 2026-10-29: make the LNG carriers review app look and work like the shared app in `../gem-review-app`, and publish it as a claude.ai artifact page. `gem-review-app/docs/plan.md` already names this as its phase 3. Status: built 2026-10-29 on the `baird` branch of both repos, and the sep-17-pass page is published (https://claude.ai/artifact/RKK3eVeTvuLRyYdrXDWuzn).

## What the port is

The port follows the same pattern as gogpt and pipelines. Pipelines is the closer model, because it also has a backend sync, push routes and machine reviewers.

- **gem-review-app, `trackers/lng/`**: `config.py` (a `TrackerConfig`: line kinds `fill`, `ref`, `new_row`; item kinds conflict, manual review, proposed, duplicate, discovery flag; machine reviewers `backend sync` and `§5 regrade`; push and refresh routes like pipelines) and `web/ext.js` and `web/ext.css` (the LNG card body, chips, filters).
- **lng-carriers-researcher, `review_app/`**: `review_data.py` is kept and gains an adapter to the core dataset contract. `store.py`, `server.py` and `build_static.py` become thin shims over the core. The repo also gains `build_all.py`, `artifacts.json` and `import_log.py`. It does not gain `.claude/settings.json` staleness hooks, because `.claude/README.md` says this repo commits no `settings.json` (settled 2026-07-16). Run `python review_app/build_all.py --check` by hand instead. `gem-review-app/scripts/check_consumers.py` also runs it. `push.py`, `suggestions.py` and `living.py` stay as they are, behind the loopback server's routes. `web/` is removed once the shared page covers it.

## Dataset mapping

| LNG today | Core contract |
|---|---|
| `vessels[]` | `cards` (`cards_key = "vessels"`) |
| vessel id (`row_id`, or `c:<batch>:<cluster_id>` for a new row) | `pid` |
| `proposals` dict | each card's `lines` list; the key `<batch dir>::<id>` is kept |
| `id`, `batch` | `record_id`, `dir` |
| confidence G / Y / R | `tier` high / medium / low, with the grade sentence kept |
| no severity | `severity`: a ref-only line is minor, everything else major (to confirm) |
| `refs [{url, verdict}]` | `verifications` for the core's check marks, or an LNG `vmark` hook |
| items with `row_ids` | a home card: the first row's vessel, or an "items with no vessel" card |

## Where decisions are stored

There is no Google ledger. `review_app/core_store.py` binds the core store to the LNG config and gives it its own `sink`. A line decision goes to `review_log.jsonl` and to the `decision` cell of `decisions.csv`. An item call goes to `review_items.jsonl`, in the shape that file has always had. A conflict's call also goes to the `decision` cell of `conflicts.csv`. Each write is one transaction across the batch dirs it touches. Calls made on the artifact page come back through `import_log.py`, which writes the same files through the same `sink`. The old `review_app/store.py` stays, because `push.py`, `living.py` and `suggestions.py` read the raw dataset through it.

## What the artifact page can and cannot do

The artifact page can decide, suggest, call items and download its log. It cannot sync the backend, push changes or update the living workbook, because those run `gws` on this machine. They stay on the loopback server, which serves the same shared page. A push still needs a person's accept. An imported artifact accept is a person's click, so it counts for push like a click on the loopback page.

## Features the core does not have yet

The LNG page has six things the shared core lacks:

1. A suggest form with a value or cosmetic kind, several source links and a required note.
2. Click a vessel name, builder or owner on the card to filter to it.
3. Linked pairs. Deciding one of `Name` and `Other names`, `Price` and `Price currency`, `Capacity` and `Capacity units`, or a value and its `[ref]` asks about the other. For `Name` and `Other names` the answer is both or neither.
4. More than one level of undo.
5. Accept, hold or reject every line the filter shows, with a confirmation.
6. A whole-batch Items tab and a session summary tab.

Items 1 to 5 go into the core, so gogpt and pipelines can use them too. Item 6 is decided below.

## Decided by Baird, 2026-10-29

- Full port: the artifact page and the loopback server both use the shared page.
- No Google ledger. `import_log.py` writes artifact decisions into each batch's `review_log.jsonl` and `decisions.csv`.
- Items sit on their vessel's card, with one "items with no vessel" card for the rest. The session summary moves into the progress dialog. No top-level tab bar in the core.
- The gem-review-app question-card work was finished. It was committed on gem-review-app's `baird` branch.
- All work goes on the `baird` branch in both repos. Nothing reaches `main` until Baird asks.

## Order of work

1. Done: the decisions above.
2. Done: the gem-review-app question-card commit.
3. Done: core additions 1 to 5 (gem-review-app `b95108a`). Undo keeps a history, so `U` steps back one action at a time.
4. Done: `trackers/lng/` config and extension, the dataset adapter and the shims; `tests/test_review_app.py` and `tests/test_review_data.py` pass, adjusted only for file paths and the new dataset shape.
5. Done: loopback check in a headless browser: render a vessel, decide a line, see `decisions.csv` change, run sync and a push plan without confirming it.
6. Done: build the single-file page, publish it from the work profile, record it in `artifacts.json`, mark it published.
7. Done: update `review_app/README.md`, `CLAUDE.md` (the review router) and `gem-review-app/docs/plan.md`.
