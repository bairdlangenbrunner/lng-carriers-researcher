"""
Rebuild every review page listed in artifacts.json from the shared interface in the sibling gem-review-app repo (review_core/web plus trackers/lng/web), and say which live pages are stale.

    python review_app/build_all.py --check               # fresh / stale (why) / unmarked per page; exit 1 if any is not fresh
    python review_app/build_all.py [--only NAME] [--all] # build the stale or unmarked pages (--all: every page)
    python review_app/build_all.py --list                # the page table: name, reviewer, url, published at
    python review_app/build_all.py --mark-published NAME # after publishing NAME's file to its url
    python review_app/build_all.py --hook EVENT          # Claude Code hook mode (SessionStart, UserPromptSubmit, Stop): one JSON object

Writes one stamped html per page into work/ and prints a table of name, reviewer, url and file, so each file can be published to its url (Artifact tool, work profile, capabilities carried forward), then --mark-published NAME records what that page was built from. A page is stale when its batch files, its batches' decision logs (review_log.jsonl, review_items.jsonl), the backend pull, the review_app builders or the shared interface changed since it was published. Add a page by adding an entry to artifacts.json.

There is no decision store to pull first (no Google ledger): a page's calls come back through import_log.py. The command line itself is review_core.pages.cli and the hook output is the JSON contract in review_core/hooks.py.

Logic: ../gem-review-app/review_core/pages.py; plan: ../gem-review-app/docs/refresh.md.
"""
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (ROOT / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_static  # noqa: E402
import core_store as store  # noqa: E402
import paths  # noqa: E402
from review_core import pages  # noqa: E402

NO_URL = "(not yet published)"
REGISTRY = HERE / "artifacts.json"
LAST_BUILD = ROOT / pages.LAST_BUILD
# apply_batch.py outputs the dataset does not read; the decision logs are hashed as decision files
NOT_INPUTS = {"apply_rows.csv", "apply_patch.csv"}


def batch_files(d):
    """The batch files review_data.py can read: the mode file, the gate and verify reports, the workbook, decisions.csv and conflicts.csv (where calls land too)."""
    return sorted(p.name for p in Path(d).iterdir()
                  if p.is_file() and p.suffix in (".json", ".csv", ".xlsx") and p.name not in NOT_INPUTS)


def adapter(cache=None):
    return pages.PageAdapter(
        root=ROOT,
        resolve_dirs=lambda e: [ROOT / d for d in e.get("dirs", [])],
        staged_files=batch_files,
        decision_files=("review_log.jsonl", "review_items.jsonl"),
        extra_inputs=lambda e: {"backend": pages.sha_file(paths.backend_csv_path(), cache)},
        builder_files=("review_app/review_data.py", "review_app/build_static.py", "review_app/core_store.py",
                       "review_app/store.py"),
        cache=cache)


def main(argv=None):
    stamp = datetime.now(store.ET).strftime("%Y%m%d_%H%M")

    def build_page(pg, args):
        dirs = [ROOT / d for d in pg.get("dirs", [])]
        html, data = build_static.build(dirs, pg.get("reviewer", ""), pg.get("title"))
        out = paths.work_dir() / f"lng_review_{pg['name']}_{stamp}_ET.html"
        out.write_text(html, encoding="utf-8")
        return out, data.get("built") or datetime.now(store.ET).isoformat(timespec="seconds")

    cache = pages.FileCache(paths.work_dir() / pages.CACHE)
    return pages.cli(adapter(cache), REGISTRY, build_page, argv, config=store.CONFIG, last_build=LAST_BUILD,
                     work=paths.work_dir(), description=__doc__.split("\n\n")[0],
                     columns=(("reviewer", lambda p: p.get("reviewer", "")), ("url", lambda p: p.get("url") or NO_URL)))


if __name__ == "__main__":
    main()
