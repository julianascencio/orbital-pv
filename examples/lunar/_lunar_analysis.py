"""Load the shared offline analysis without requiring a package for examples."""

import importlib.util
import sys
from pathlib import Path

from orbitalpv import __version__

name = "orbitalpv_lunar_example_analysis"
if name not in sys.modules:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(name, root / "analysis/lunar_surface_pv/run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
analysis = sys.modules[name]

version = __version__
