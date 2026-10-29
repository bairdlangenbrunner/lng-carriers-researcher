"""
Puts the shared review app on sys.path. It lives in the sibling checkout ../gem-review-app (the same convention as gogpt-researcher and pipelines-researcher); GEM_REVIEW_APP in the environment overrides the location.

    import gem_core  # noqa: F401  (before any review_core / trackers import)
"""
import os
import sys
from pathlib import Path

GEM_REVIEW_APP = Path(os.environ.get("GEM_REVIEW_APP") or Path(__file__).resolve().parent.parent.parent / "gem-review-app").resolve()

if not (GEM_REVIEW_APP / "review_core" / "store.py").is_file():
    raise ImportError(f"the shared review app is not at {GEM_REVIEW_APP}: clone gem-review-app next to this repo, "
                      "or set GEM_REVIEW_APP to its folder")
if str(GEM_REVIEW_APP) not in sys.path:
    sys.path.append(str(GEM_REVIEW_APP))
