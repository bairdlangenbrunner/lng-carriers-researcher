"""Make the flat scripts/ modules importable from tests.

The scripts import each other with flat names (`from normalize import ...`,
`from paths import ...`) because they're run from inside scripts/ at batch time.
The package isn't installed as an importable distribution, so put scripts/ on
sys.path here rather than requiring `pip install -e .` to expose the modules.
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# The review app (review_app/) imports from scripts/, never the reverse; its tests
# import its modules by flat name too.
REVIEW_APP = Path(__file__).resolve().parent.parent / "review_app"
if str(REVIEW_APP) not in sys.path:
    sys.path.insert(0, str(REVIEW_APP))
