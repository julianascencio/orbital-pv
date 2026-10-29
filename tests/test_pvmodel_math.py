import numpy as np

from space_pv_pvmodel.model import effective_irradiance_w_m2


def test_effective_irradiance_combines_geometry():
    result = effective_irradiance_w_m2(1361.0, 0.5, 0.8, spectral_factor=0.9, optical_factor=0.95)
    assert np.isclose(float(result), 1361.0 * 0.5 * 0.8 * 0.9 * 0.95)
