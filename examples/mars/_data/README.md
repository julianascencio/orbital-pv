# InSight observations used by the offline examples

These are source measurements/operational estimates, not synthetic fixtures.
See `provenance.json` for exact URLs, transformations and SHA-256 checksums.

- `insight-energy.csv`: all 200 published estimated daily array energies. Original bytes; energy is in Wh per Martian sol. Lorenz et al. dataset DOI [10.7281/T1EPKRKR](https://doi.org/10.7281/T1EPKRKR), JHU repository v1.0, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The companion paper is [Lorenz et al. 2020](https://doi.org/10.1029/2019EA000992).
- `Solar_00004-00004.txt`, `Solar_00052-00052.txt`: original files extracted unchanged from the same licensed source's sols 0–99 ZIP. East/west hardwired DBR string currents in amperes, not total array power. Sleep gaps remain missing.
- `nsyt_tau.csv`, `nsyt_tau.xml`: original [NASA PDS Atmospheres InSight camera product](https://atmos.nmsu.edu/data_and_services/atmospheres_data/INSIGHT/insight_opacity.html), 758 records, logical identifier `urn:nasa:pds:insight_cameras_tau:data_derived:nsyt_tau::1.0`. Retain NASA/PDS and InSight camera-team attribution. The source landing page links a **review directory**, not an asserted final archive. Optical depth is at 600 nm with reported uncertainty; neither irradiance nor electrical power. Source data retain their provider terms and are not relicensed as MIT code.

The analysis uses bounded retrospective interpolation of the opacity. This is a derived model input, separately named in exported results; source records remain unchanged. No paper PDFs are redistributed.

Live archive inspection found corrupted source files on sols 169 and 192 and explicit NA placeholders on sols 916 and 941. The connector raises by default. `invalid_files="report"` excludes whole invalid files and returns their names and reasons in frame attributes. It never repairs measured values or bridges current gaps.
