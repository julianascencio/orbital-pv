from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike


def load_kernels(paths: Iterable[str]) -> None:
    import spiceypy as spice

    for path in paths:
        spice.furnsh(path)


def clear_kernels() -> None:
    import spiceypy as spice

    spice.kclear()


def positions_m(
    target: str,
    ets: Sequence[float],
    *,
    frame: str = "J2000",
    observer: str = "EARTH",
    aberration: str = "NONE",
) -> np.ndarray:
    import spiceypy as spice

    positions = []
    for et in ets:
        pos_km, _ = spice.spkpos(target, float(et), frame, aberration, observer)
        positions.append(np.asarray(pos_km, dtype=float) * 1000.0)
    return np.asarray(positions, dtype=float)


def utc_to_ephemeris_seconds(timestamps: Sequence[str]) -> np.ndarray:
    """Convert explicit UTC strings to SPICE ET using the loaded leap-second kernel.

    SPICE errors for missing kernels or invalid dates propagate; no approximate
    UTC/TDB conversion is substituted. A loaded LSK is normally required.
    """
    import spiceypy as spice

    values = list(timestamps)
    if any(
        not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value)
        for value in values
    ):
        raise ValueError("Use explicit ISO UTC strings, YYYY-MM-DDTHH:MM:SS[.fraction]Z")
    return np.asarray([spice.str2et(value) for value in values], dtype=float)


def frame_rotation_matrices(
    from_frame: str,
    to_frame: str,
    ets: ArrayLike,
) -> np.ndarray:
    """Return rotations mapping column vectors from one SPICE frame to another.

    CK attitude frames require the relevant CK, FK, SCLK and time kernels, with
    coverage at every requested epoch. An unavailable transformation raises the
    original SPICE error. These are position rotations, not 6D state transforms.

    Source: https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/pxform_c.html
    """
    import spiceypy as spice

    times = np.asarray(ets, dtype=float)
    if times.ndim != 1 or not np.isfinite(times).all():
        raise ValueError("ets must be a finite one-dimensional sequence")
    if not from_frame.strip() or not to_frame.strip():
        raise ValueError("Both SPICE frame names are required")
    if times.size == 0:
        return np.empty((0, 3, 3), dtype=float)
    return np.asarray([spice.pxform(from_frame, to_frame, float(et)) for et in times])


def transform_vectors(
    vectors: ArrayLike,
    from_frame: str,
    to_frame: str,
    ets: ArrayLike,
) -> np.ndarray:
    """Rotate a fixed vector or a time-aligned (n, 3) array using SPICE attitude."""
    matrices = frame_rotation_matrices(from_frame, to_frame, ets)
    values = np.asarray(vectors, dtype=float)
    if values.shape not in {(3,), (len(matrices), 3)} or not np.isfinite(values).all():
        raise ValueError("vectors must be finite with shape (3,) or (len(ets), 3)")
    return np.einsum("nij,nj->ni", matrices, np.broadcast_to(values, (len(matrices), 3)))
