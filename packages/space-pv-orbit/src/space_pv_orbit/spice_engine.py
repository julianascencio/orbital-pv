from __future__ import annotations

from collections.abc import Iterable, Sequence
import numpy as np


def load_kernels(paths: Iterable[str]) -> None:
    import spiceypy as spice
    for path in paths: spice.furnsh(path)


def clear_kernels() -> None:
    import spiceypy as spice
    spice.kclear()


def positions_m(target: str, ets: Sequence[float], *, frame: str = "J2000", observer: str = "EARTH", aberration: str = "NONE") -> np.ndarray:
    import spiceypy as spice
    positions=[]
    for et in ets:
        pos_km,_=spice.spkpos(target,float(et),frame,aberration,observer); positions.append(np.asarray(pos_km,dtype=float)*1000.0)
    return np.asarray(positions,dtype=float)
