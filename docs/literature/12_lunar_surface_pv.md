# Lunar surface PV: literature, data and implementation

Reviewed 2026-11-03. These references motivate the implementation; the examples
do not claim to reproduce the papers or validate a flight design.

| Primary source | Evidence and relevance | Implemented connection / boundary |
| --- | --- | --- |
| [Gläser et al. 2014, Icarus](https://doi.org/10.1016/j.icarus.2014.08.013) | LOLA terrain-based polar illumination; data-resolution sensitivity and long-period illumination studies. | Spherical sector horizons, finite Sun visibility, height and resolution sweeps. No reproduction of published site percentages. |
| [Ross et al. 2023, Acta Astronautica](https://doi.org/10.1016/j.actaastro.2023.06.040) | Height-dependent solar availability and the importance of tower/array overshadowing. | Explicit 2/5/20 m comparisons and PV/storage/tower scenario mass. Mutual shading and structural engineering are omitted. |
| [NASA PGDA 78](https://pgda.gsfc.nasa.gov/products/78) | 5 m site DEMs, interpolation and published elevation uncertainties. | Site DEM/error-map connector, native windows. Error fields are available but not propagated as independent pixel noise. |
| [NASA PGDA 90](https://pgda.gsfc.nasa.gov/products/90) | Broader polar DEMs in MOON_ME_DE421. | 80 m terrain source and explicitly strided distant horizon layer. |
| [Schorghofer & Williams 2020, PSJ](https://doi.org/10.3847/PSJ/abb6ff) and [PDS Diviner archive](https://pds-geosciences.wustl.edu/missions/lro/diviner.htm) | Bolometric temperature observations binned by location, solar longitude and season. | Label-driven PCP parser, byte-preserving subsets and fixed radiometric boundary scenarios. No fabricated temporal interpolation. |
| [NAIF lunar frame kernel](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf) | DE421 lunar frame definitions and differences from IAU_MOON. | Pinned kernel downloader and common terrain/ephemeris frame. Geometric positions; missing coverage raises. |
| [Dhere & Santiago 1993, NASA NTRS](https://ntrs.nasa.gov/citations/19940006939) | Cell temperature changes lunar photovoltaic performance; more detailed models go beyond linear coefficients. | Existing transient thermal/PV solver reused with lunar radiative boundaries; scalar temperature law remains a screening approximation. |
| [NASA SVS 4930](https://svs.gsfc.nasa.gov/4930/) | Rendered two-hour polar illumination references for 2023--2030. | Public metadata and explicit asset downloads; qualitative gallery only. |

The storage sweep and rover route planner use explicit energy balances and
discrete numerical algorithms implemented here, not an attributed replication
of a cited optimisation study. Equipment parameters are engineering scenarios.
Validation consists of limiting cases, invariants, conservation checks, source
checksums and reproducible example execution. Lunar PV telemetry calibration,
correlated terrain uncertainty, battery cold-performance calibration, shadow
validation against mapped images and full-precession mission studies remain open.
