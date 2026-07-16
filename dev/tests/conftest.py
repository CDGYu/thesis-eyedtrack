import sys
from pathlib import Path

DEV_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DEV_DIR.parent
for p in (str(DEV_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
