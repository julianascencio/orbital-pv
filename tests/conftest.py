from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for src in list((ROOT / "packages").glob("*/src")) + list((ROOT / "apps").glob("*/src")):
    sys.path.insert(0, str(src))
