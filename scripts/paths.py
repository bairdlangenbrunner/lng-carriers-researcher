"""
Shared path resolution for the LNG Carrier Tracker scripts.

All scripts in this directory share a small convention:
- Scratch artifacts (backend.csv, CSB HTML, dedup indexes, etc.) go in
  the "work" directory, which defaults to `<repo_root>/work/`. The repo
  root is determined by walking up from this file's location.
- The work directory can be overridden by setting LNGCT_WORK_DIR in the
  environment, or by passing --work-dir to scripts that accept it.
- Final batch outputs (xlsx files) go to `<repo_root>/batches/<batch_dir>/`,
  passed explicitly to build_workbook.py via --out.

This keeps the scripts portable: they work from `scripts/`, from repo root,
or invoked by Claude Code from anywhere in the tree.
"""
import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def work_dir() -> Path:
    """
    Return the work directory.
    Precedence: $LNGCT_WORK_DIR > <repo_root>/work/.
    Creates the directory if it doesn't exist.
    """
    env = os.environ.get("LNGCT_WORK_DIR")
    p = Path(env).expanduser().resolve() if env else (repo_root() / "work")
    p.mkdir(parents=True, exist_ok=True)
    return p


def backend_csv_path() -> Path:
    """Default location for the pulled backend CSV."""
    return work_dir() / "backend.csv"


def csb_dir() -> Path:
    """Directory for cached ChinaShipBuild HTML and parsed JSON."""
    p = work_dir() / "csb"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dedup_index_path() -> Path:
    """Default location for the dedup index JSON."""
    return work_dir() / "dedup_index.json"
