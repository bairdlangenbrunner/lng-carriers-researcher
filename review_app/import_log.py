"""
Bring the calls made on the artifact page (build_static.py) into the batch dirs.

    python review_app/import_log.py FILE --dry-run
    python review_app/import_log.py FILE [FILE ...] [--batches <dir> ...] --reviewer EMAIL [--reviewer XX=EMAIL ...]

FILE is what the page's "download decisions" button saves, or the artifact's shared `logs` collection saved as JSON (an ArtifactData list or get result). Either way it holds one or more log documents, each {reviewer, records: [...]}. --batches names the batch dirs the page was built from (default: every dir the records name); the dataset is rebuilt from them, against the current backend pull, so each record can be checked against the current batch.

Every new record is written the way the local server writes a call (core_store.sink): a line decision to review_log.jsonl and the `decision` cell of decisions.csv, an item call to review_items.jsonl and, for a conflict, the `decision` cell of conflicts.csv. Each record keeps the id and the time the page gave it, and is marked origin 'artifact'. There is no Google ledger for LNG. Rules:

  - a record whose id is already in a batch's review_log.jsonl or review_items.jsonl is skipped, so importing the same file twice, or a later download that repeats an earlier one, is safe
  - a record is skipped as superseded when a batch already holds a later call by a person on the same line or item (someone decided it on the local server afterwards)
  - a record whose key is not in the current dataset, or whose batch dir is not, stops the import before anything is written (the batch was rebuilt since the page was made: rebuild the page and publish it again)
  - the record fields the files need (the decisions.csv id, a conflict's conflicts.csv index) come from the current dataset, not from the page
  - the page is not given reviewers' addresses, only their names, so name each one: --reviewer EMAIL (matched to its initials), or --reviewer XX=EMAIL

This writes the batch files only. The backend sheet is written by the server's push changes (AP §2b) and nothing else here.

The plan and report code is shared with the other researcher repos in ../gem-review-app/review_core/import_log.py. This file holds the LNG rules (Rules), the --batches dataset and the write.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (ROOT / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import core_store  # noqa: E402
import review_data  # noqa: E402
from review_core import import_log as core  # noqa: E402
from trackers.lng.config import record_fields  # noqa: E402


class StoreError(Exception):
    """A batch file could not be written (the sink rolled the run back)."""


class _Store(types.SimpleNamespace):
    """core_store as the shared import code sees it, with read_log covering both logs: item calls live in review_items.jsonl, so the id and time checks must read it too."""

    def read_log(self, d):
        items = [dict(r, key=r.get("key") or r.get("item_id")) for r in core_store.read_item_log(d)]
        return core_store.read_log(d) + items


store = _Store(**{k: getattr(core_store, k) for k in dir(core_store) if not k.startswith("__") and k != "read_log"})
ledger = types.SimpleNamespace(StoreError=StoreError)


def dataset(dirs, backend_path=None, root=None):
    """The current dataset for these batch dirs, overlaid with their calls, and {label: Path} (labels are relative to `root`, default batches/)."""
    ds = review_data.adapt(review_data.build([Path(d) for d in dirs], backend_path))
    paths = core_store.dir_paths(ds, root or core_store.BATCHES)
    core_store.overlay(ds, paths)
    return ds, paths


class Rules:
    """What an LNG record must match in the current dataset: its own key, a line decision on a line and an item call on an item, a call from the vocabulary, and a batch dir of the dataset. The record fields the batch files need are taken from the dataset. Anything else stops the import."""

    def __init__(self, ds, dirs):
        self.dirs = dirs
        self.idx = core_store.index(ds)

    def place(self, r, where, email):
        key = str(r["key"])
        if key not in self.idx:
            raise SystemExit(f"{where}: {key} is not in the current dataset "
                             "(rebuilt since the page was made? rebuild the page and publish it again)")
        card, obj, grp = self.idx[key][:3]
        if ("call" in r) != (grp == "items"):
            raise SystemExit(f"{where}: {key} is {'an item' if grp == 'items' else 'a line'} "
                             f"but the record is {'an item call' if 'call' in r else 'a line decision'}")
        if grp == "lines" and r.get("decision") not in core_store.DECISIONS:
            raise SystemExit(f"{where}: decision {r.get('decision')!r} is not one of {sorted(core_store.DECISIONS)}")
        if grp == "items" and not r.get("undecided"):
            vocab = core_store.ITEM_CALLS.get(obj.get("kind"), core_store.OTHER_CALLS)
            if r["call"] not in vocab:
                raise SystemExit(f"{where}: call {r['call']!r} is not one of {list(vocab)} for a {obj.get('kind')} item")
        if r["dir"] not in self.dirs or r["dir"] != obj["dir"]:
            raise SystemExit(f"{where}: batch dir {r['dir']} is not this record's batch in the current dataset")
        return dict(r, **record_fields(card, obj, grp))

    def extra(self):
        return {}


def _add_args(ap):
    ap.add_argument("--batches", nargs="*", default=[], help="the batch dirs the page was built from (default: the dirs the records name)")


def _dataset_for(a, docs):
    names = list(a.batches) or sorted({str(r.get("dir")) for d in docs for r in d["records"] if isinstance(r, dict) and r.get("dir")})
    return dataset(review_data.resolve_dirs(names))


core.bind(sys.modules[__name__], required=("key", "reviewer", "dir"), rules=Rules, add_args=_add_args,
          dataset_for=_dataset_for, next_step="Then: python scripts/apply_batch.py --batch batches/<dir> for each batch.")


def write(pl, ds, dirs, cfg=None, gws=None):  # noqa: F811  (the bound write needs a Google ledger)
    """Append the planned records through the server's sink. Returns the saved records."""
    recs = [dict(r, origin=ORIGIN) for _, r in pl["new"]]  # noqa: F821  (bound above)
    try:
        return core_store.append_records(recs, dirs, sink=core_store.sink)
    except OSError as e:
        raise StoreError(f"a batch file could not be written ({e}); nothing from this run was kept")


def main(argv=None):  # noqa: F811  (the bound main reports Google store rows)
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("file", nargs="+", help="the page's download, or the artifact's `logs` collection saved as JSON")
    _add_args(ap)
    ap.add_argument("--reviewer", action="append", default=[], metavar="EMAIL or XX=EMAIL",
                    help="a reviewer's address (the page is not given addresses); repeat per reviewer")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    a = ap.parse_args(argv)
    docs = [d for f in a.file for d in read_docs(f)]  # noqa: F821
    if not any(d["records"] for d in docs):
        raise SystemExit("no records in " + ", ".join(a.file))
    ds, dirs = _dataset_for(a, docs)
    pl = plan(docs, ds, dirs, emails=core.parse_emails(a.reviewer, store))  # noqa: F821
    print(report(pl))  # noqa: F821
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    if not pl["new"]:
        return 0
    try:
        saved = write(pl, ds, dirs)
    except StoreError as e:
        sys.exit(f"{e}\nrun the import again (records already written are skipped by id)")
    print(f"{len(saved)} records written to {len({r['dir'] for r in saved})} batch dir(s). "
          "Then: python scripts/apply_batch.py --batch batches/<dir> for each batch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
