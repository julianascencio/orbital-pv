from __future__ import annotations

import numpy as np


def quaternion_wxyz_to_matrix(
    quaternion_wxyz: tuple[float, float, float, float] | np.ndarray,
) -> np.ndarray:
    """Rotation matrix for a normalized active quaternion in (w, x, y, z) order.

    The repository convention is explicit: attitude quaternions used by this function rotate
    vectors from the spacecraft body frame into the stated inertial/reference frame.
    Mission connectors must convert source conventions before calling it.
    """
    q = np.asarray(quaternion_wxyz, dtype=float)
    if q.shape != (4,):
        raise ValueError(f"Expected quaternion shape (4,), got {q.shape}")
    norm = float(np.linalg.norm(q))
    if norm == 0.0:
        raise ValueError("Quaternion norm cannot be zero")
    w, x, y, z = q / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def body_vector_to_reference(
    body_vector: tuple[float, float, float] | np.ndarray,
    quaternion_wxyz: tuple[float, float, float, float] | np.ndarray,
) -> np.ndarray:
    vector = np.asarray(body_vector, dtype=float)
    if vector.shape != (3,):
        raise ValueError(f"Expected body vector shape (3,), got {vector.shape}")
    return quaternion_wxyz_to_matrix(quaternion_wxyz) @ vector
