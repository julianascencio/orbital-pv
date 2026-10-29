import math

import numpy as np

from space_pv_orbit.attitude import body_vector_to_reference


def test_quaternion_rotates_body_x_to_reference_y():
    half = math.sqrt(0.5)
    q = (half, 0.0, 0.0, half)
    result = body_vector_to_reference((1.0, 0.0, 0.0), q)
    assert np.allclose(result, [0.0, 1.0, 0.0], atol=1e-12)
