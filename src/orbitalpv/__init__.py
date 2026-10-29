"""Public OrbitalPV API.

Install with ``pip install orbital-pv`` and import this package as ``orbitalpv``.
"""

from importlib.metadata import PackageNotFoundError, version

from .analytics import (
    add_power,
    add_robust_baseline,
    daily_health,
    detect_persistent_loss,
    estimate_degradation,
    summarize_case0,
)
from .data import (
    CelesTrakConnector,
    fetch_celestrak_omm,
    load_table,
    make_demo_telemetry,
    normalize_birds_like,
)
from .environment import am0_irradiance, incidence_factor
from .orbit import (
    ASTRONOMICAL_UNIT_M,
    EARTH_EQUATORIAL_RADIUS_M,
    EARTH_ROTATION_RATE_RAD_S,
    EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2,
    SolarGeometry,
    body_vector_to_reference,
    circular_orbit_positions_m,
    cosine_incidence,
    earth_occultation_fraction,
    geocentric_sun_positions_m,
    ground_track_deg_from_eci,
    keplerian_orbit_positions_m,
    propagate_geocentric_m,
    quaternion_wxyz_to_matrix,
    satellite_from_omm,
    satellite_from_tle,
    solar_geometry,
)
from .pv import (
    DeSotoParameters,
    PvwattsReference,
    effective_irradiance_w_m2,
    pvwatts_dc_space,
    single_diode_points,
)

try:
    __version__ = version("orbital-pv")
except PackageNotFoundError:
    __version__ = "0.3.1"

__all__ = [
    "ASTRONOMICAL_UNIT_M",
    "EARTH_EQUATORIAL_RADIUS_M",
    "EARTH_ROTATION_RATE_RAD_S",
    "EARTH_STANDARD_GRAVITATIONAL_PARAMETER_M3_S2",
    "CelesTrakConnector",
    "DeSotoParameters",
    "PvwattsReference",
    "SolarGeometry",
    "__version__",
    "add_power",
    "add_robust_baseline",
    "am0_irradiance",
    "body_vector_to_reference",
    "circular_orbit_positions_m",
    "cosine_incidence",
    "daily_health",
    "detect_persistent_loss",
    "earth_occultation_fraction",
    "effective_irradiance_w_m2",
    "estimate_degradation",
    "fetch_celestrak_omm",
    "geocentric_sun_positions_m",
    "ground_track_deg_from_eci",
    "incidence_factor",
    "keplerian_orbit_positions_m",
    "load_table",
    "make_demo_telemetry",
    "normalize_birds_like",
    "propagate_geocentric_m",
    "pvwatts_dc_space",
    "quaternion_wxyz_to_matrix",
    "satellite_from_omm",
    "satellite_from_tle",
    "single_diode_points",
    "solar_geometry",
    "summarize_case0",
]
