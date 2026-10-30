Environmental inputs and attitude
=================================

The ``orbitalpv.environment_data`` API connects environmental measurements to
explicit physical models. Every file download returns a checksum receipt;
local readers preserve source units and metadata. Live catalog checks and one
public NOAA day underpin ``analysis/environmental_inputs``. The gallery runs
offline using a checked, reduced observation snapshot.

Install ``orbital-pv[netcdf]`` for netCDF readers and ``orbital-pv[orbit]`` for
SPICE. These dependencies are imported only when their functions are called.

CERES: choose a collection and edition
--------------------------------------

NASA's current CMR cloud catalog separates short name from version. Discover
the exact current identifiers before requesting a bounded interval:

.. code-block:: python

   from orbitalpv import environment_data as env

   with env.CeresConnector() as ceres:
       collections = ceres.collections(short_name_pattern="CER_SYN1deg*")
       granules = ceres.search(
           short_name="CER_SYN1deg-1Hour_Terra-Aqua-NOAA20",
           version="Edition4B",
           start="2023-01-01T00:00:00Z",
           end="2023-01-01T23:59:59Z",
       )

The checked catalog result contains one daily file with hourly fields for this
interval. Discovery is public; file retrieval may require an Earthdata token.
Pass an authorized token through ``download(..., bearer_token=token)``. It is
not written to receipts. Query strings are redacted, but a digest of the full
request URL preserves cache identity so different subsets cannot be confused.
An existing file with incompatible provenance raises instead of being reused.

Use ``inspect_environment_netcdf`` to identify an exported file's exact
variables. ``read_ceres_toa`` requires explicit shortwave and longwave names,
checks W/m² units and decoded time, and applies optional ``isel`` selectors
before loading. It reads CF-netCDF; HDF4 is not silently interpreted as netCDF.
Missing or invalid flux remains missing. Edition-specific quality flags should
be screened before using values as model forcing.

Top-of-atmosphere hemispheric flux is not panel irradiance. The
``earth_flux_to_panel`` integration applies the emission angle, receiver angle,
patch area and inverse distance squared, assuming Lambertian radiance
:math:`L=F/\pi`. Spacecraft position, panel normal and geographic patches must
share the same Earth-fixed frame. ``earth_grid_cell_areas`` computes exact
spherical cell areas from edges.

Missing visible supplied cells produce NaN by default. ``allow_partial=True``
returns only the measured portion and its view-weight coverage; it does not
extrapolate missing Earth radiation. ``valid_view_fraction`` measures finite
values among supplied patches, not completeness of the whole Earth disk.
``geometric_view_factor`` exposes the projected quadrature weight; values above
1.01 are rejected as physically impossible, requiring finer or nonoverlapping
patches. Anisotropic reflection, atmospheric limb effects and grid resolution
remain model discrepancy. Thermal IR is thermal forcing and
must not be passed to a solar photon-conversion model as ordinary sunlight.

POES/MetOp: retain instrument definitions
-----------------------------------------

.. code-block:: python

   with env.PoesMetopConnector() as noaa:
       receipt = noaa.fetch_day("metop01", "2023-01-01", "data/metop.nc")
   variables = env.inspect_environment_netcdf(receipt.path)
   particles = env.read_poes_metop(
       receipt.path,
       channels=["mep_pro_tel0_flux_p1", "mep_ele_tel0_flux_e1"],
       quality_variables=["mep_pro_tel0_flux_p1_err"],
   )

The real source contains 43,199 approximately two-second observations. Its
native time metadata specifies milliseconds since 1970 in ``long_name`` while
``units`` is simply ``time``. The reader recognizes this exact NOAA format,
including its independent, same-length record dimensions, and also accepts
ordinary CF epoch time. It rejects ambiguous numeric time from other files.

The proton channel is differential near 39 keV; the electron channel is integral
above 40 keV. They have different units and cannot be added. Provider metadata
reports known contamination and a calibrated-flux processing level even though
the archive path contains ``l1b``; both remain visible. The loader preserves
negative provider sentinel values. Explicit filtering, valid-count reporting
and instrument-specific contamination correction belong to the analysis.

These are measurements at the detector's location and orientation. Using them
for another mission requires environment mapping and energy/angular response;
solar-cell degradation additionally needs exposure duration, shielding and
calibrated damage response. ``physics.radiation_equivalent_fluence`` requires
those physical inputs and never takes a raw integral channel as NIEL dose.

SPENVIS and IRENE exports
-------------------------

``read_spenvis(path)`` and ``parse_spenvis(text)`` implement the documented
SPENVIS/UNIRAD block-CSV format: comments, metadata, reserved annotations,
scalar/vector variable descriptions, numeric records and block footers.
FORTRAN D exponents and escaped apostrophes are supported. Header/column/row
inconsistency, truncation and provider error markers raise exceptions.

Returned ``SpenvisBlock`` objects retain exact units, metadata and vector-energy
associations; no keV/MeV, integral/differential, confidence percentile, shielding
or model-version assumptions are inferred. Select and convert those explicitly
before a radiation model. The importer can read SPENVIS-formatted IRENE output;
arbitrary IRENE text/JSON formats are not claimed to be supported. It does not
log in to or run a remote SPENVIS service.

Historical orbit and SPICE attitude
-----------------------------------

``SpaceTrackConnector.gp_history`` retrieves a bounded UTC EPOCH interval for
one NORAD identifier and sorts returned records by epoch. It checks satellite
identity and date bounds and rejects truncated results. A caller-provided disk
cache is mandatory, respecting Space-Track's instruction to download history
once and reuse it. Authentication is needed on cache misses; year/bulk archives
are appropriate for larger requests. EPOCH is the element epoch, not the date
the provider published the elements, so causal retrospective studies need to
account separately for availability time.

``load_kernels``, ``utc_to_ephemeris_seconds``, ``frame_rotation_matrices`` and
``transform_vectors`` expose SPICE time/frame operations. Rotations map column
vectors from ``from_frame`` to ``to_frame``. CK attitude needs suitable CK, FK,
SCLK and time kernels covering every epoch. Missing coverage or unknown frames
raise the SPICE error; no synthetic attitude fills the gap. Call
``clear_kernels`` after an isolated calculation. The global SPICE kernel pool
must be coordinated by callers sharing a process.

Evidence and reproduction
-------------------------

* `NOAA SEM-2 product documentation <https://www.ncei.noaa.gov/products/poes-metop-space-environment-monitor>`_
* `NASA CERES products <https://ceres.larc.nasa.gov/data/>`_
* `NASA CMR API <https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html>`_
* `ESA SPENVIS/UNIRAD interchange format <https://space-env.esa.int/Manuals/Mulassis/ml-v02-00/OutputFiles.html>`_
* `Space-Track API and usage policy <https://www.space-track.org/documentation>`_
* `NAIF frame transformations <https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/pxform_c.html>`_

The default Earth-view reference is a declared uniform 240 W/m² Lambertian
Earth. Its independent nadir result is :math:`F(R/r)^2`. The netCDF and
SPENVIS tests use explicitly constructed fixtures, while the NOAA gallery
uses an actual public observation snapshot. Protected CERES observations are
not bundled. See ``analysis/environmental_inputs/README.md`` for exact
commands, checksums and the executed reference results.
