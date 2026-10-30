Constellations: imaging, communications, and space computing
===============================================================================

Use the public ``orbitalpv`` API to inspect constellation geometry, sunlight,
and illustrative spacecraft solar generation. The Earth-observation examples
use published nominal mission geometry. The data-center examples investigate
published concepts and explicitly chosen design scenarios.

.. list-table:: Choose a constellation workflow
   :header-rows: 1
   :widths: 35 65

   * - Example
     - What it demonstrates
   * - :doc:`/gallery/constellations/plot_geo_irradiance_imaging_constellation`
     - GOES, Meteosat, and Himawari viewing geometry, overlap, and eclipse seasons.
   * - :doc:`/gallery/constellations/plot_polar_earth_observation_constellation`
     - Sentinel-2B/2C design orbits, ground tracks, daylight, and onboard solar power.
   * - :doc:`/gallery/constellations/plot_space_data_center_orbits`
     - Suncatcher- and ASCEND-motivated orbit scenarios, seasonal illumination,
       finite-Sun penumbra, and an explicit load/storage budget.
   * - :doc:`/gallery/constellations/plot_compact_data_center_constellation`
     - Correlated eclipses in a compact compute cluster versus a hypothetical
       dispersed ring, including each node's local power deficit.
   * - :doc:`/gallery/constellations/plot_starlink_gen1_solar_generation`
     - Fleet solar generation for an illustrative Starlink Gen1 shell.

Install plotting support with ``pip install "orbital-pv[examples]>=0.6.0"``.
All five examples run offline, without TLE downloads or additional GIS packages.

The imagery examples distinguish reflected radiance and retrieved surface
irradiance from the spacecraft's own incoming sunlight and electrical power.
Geometric visibility does not guarantee an available image or a valid irradiance
retrieval. The data-center studies distinguish proposed constellation layouts
from flown hardware and test seasonal shadow instead of assuming constant Sun.

The Starlink example uses the FCC-authorized first-generation 550 km shell
geometry: 1,584 satellites at 53° inclination in 72 planes with 22
satellites per plane.

Power-system assumptions throughout the gallery are stated explicitly and are
not manufacturer specifications. Arithmetic fleet power is not electrical
power sharing between satellites. Each page provides its primary references,
time/frame conventions, modelling assumptions, and step-by-step plots.
