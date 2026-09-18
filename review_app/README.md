# review_app — decide a batch's proposals

The review surface for accept / hold / reject decisions, replacing the combined xlsx.
Build spec: `docs/plans/2026-09-18_review-app.md`. Run everything from the repo root.

The app never touches the backend. It writes only the `decision` column of each batch's
`decisions.csv` plus an append-only audit log (`review_log.jsonl`). Accepted proposals reach the
sheet through the Apply SOP (`docs/sops/apply.md`), unchanged.

## Entry points

1. `review_data.py` builds `work/review_data.json` (gitignored — it holds backend data):

   ```bash
   python scripts/pull_backend.py                      # fresh pull first (refuses without one)
   python review_app/review_data.py --batches batches/<dir> [<dir> ...]
   ```

   Labels, apply order and the applied marker come from a `review_batches.json` in a
   `batches/*/` dir that names the batches (the sep-17-pass one lives in its combined dir);
   without one, label = dir name, order = dir sort order, applied = `verify_report.csv` exists.
