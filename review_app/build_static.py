"""
Build the review app as ONE html file: the page to publish as a claude.ai artifact, or to send to a colleague who does not run the repo.

    python review_app/build_static.py --batches <dir> [<dir> ...] --reviewer "Baird Langenbrunner" [--out PATH]

The page is built by the shared builder in ../gem-review-app (review_core/build_static.py): the shared page and the LNG extension (trackers/lng/web), with the dataset review_data.py builds from the batch dirs (the calls already in each batch's decisions.csv, review_log.jsonl and review_items.jsonl laid over it) gzipped into one block, and the browser-side store (review_core/web/static_store.js). Published as an artifact the page saves every call to the artifact's database; opened from disk the calls stay in the browser and "download decisions" hands them over as a file. Either way review_app/import_log.py brings them into the batch dirs.

The page decides only: sync and push need the loopback server (server.py), which can pull and write the backend. It needs a fresh backend pull like the server does (review_data.py refuses without one); it does not pull itself.

Default output: work/lng_review_<batches>_<YYYYMMDD>_<HHMM>_ET.html (work/ is not tracked). Every build gets a fresh stamp; an existing file is never overwritten.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (ROOT / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import core_store as store  # noqa: E402
import paths  # noqa: E402
import review_data  # noqa: E402
from review_core import build_static as core  # noqa: E402


def render(data, reviewer, title=None):
    """The page as one html string, from the shared builder with the LNG config. No ledger: the page's calls come back by import_log.py."""
    return core.render(data, reviewer, store.CONFIG, title=title, ledger_url="", root=store.BATCHES)


def dataset(dirs, backend_path=None):
    """The shared-form dataset for these batch dirs, every batch's decisions laid over it."""
    data = review_data.adapt(review_data.build(dirs, backend_path))
    store.overlay(data, store.dir_paths(data, store.BATCHES))
    return data


def build(dirs, reviewer, title=None, backend_path=None):
    """-> (html, data)."""
    data = dataset(dirs, backend_path)
    return render(data, store.initials(reviewer), title), data


def counts(data):
    cards = data["vessels"]
    return (f"{sum(1 for c in cards if c['pid'] != store.ITEMS_PID)} vessels, "
            f"{sum(len(c['lines']) for c in cards)} changes, {sum(len(c['items']) for c in cards)} items")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batches", nargs="+", required=True, help="batch dirs (names under batches/, or paths)")
    ap.add_argument("--reviewer", required=True, help="who will review; recorded by initials")
    ap.add_argument("--title", default=None, help="page title (default: the config's)")
    ap.add_argument("--out", default=None, help="output html (default work/lng_review_<batches>_<stamp>_ET.html)")
    args = ap.parse_args(argv)
    dirs = review_data.resolve_dirs(args.batches)
    html, data = build(dirs, args.reviewer, args.title)
    if args.out:
        out = Path(args.out)
    else:
        stamp = datetime.now(store.ET).strftime("%Y%m%d_%H%M")
        slug = "+".join(d.name.split("_", 2)[-1] if d.name.count("_") >= 2 else d.name for d in dirs)
        out = paths.work_dir() / f"lng_review_{slug[:80]}_{stamp}_ET.html"
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out}; pass a new --out or wait a minute for a fresh stamp")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB: {counts(data)}, reviewer {store.initials(args.reviewer)})")
    print("publish it as a claude.ai artifact from the work profile (review_app/README.md), or send the file; "
          "the calls come back through: python review_app/import_log.py <file> --reviewer EMAIL")
    return out


if __name__ == "__main__":
    main()
