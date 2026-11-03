# Original research API snapshots

These small, unmodified JSON responses were retrieved on 3 November 2026 through
the public OrbitalPV connectors. Sidecars retain exact query URLs, retrieval
times, SHA-256 checksums and interface documentation. `access-check.json` records
the successful seven-provider live run. Paths in sidecars are repository-relative
for portability. No tokens or authenticated responses are included.

| Snapshot | Source and scope | Attribution / usage |
|---|---|---|
| `ntrs.json` | Five NASA Technical Reports Server search results about array end-of-life performance; not a complete literature corpus | NASA NTRS, https://ntrs.nasa.gov/api/openapi/ ; each record retains its original copyright/distribution metadata. Full papers are not bundled. |
| `zenodo.json` | Metadata for the fixed OPS-SAT-AD release, DOI 10.5281/zenodo.15108715 | Original authors/title/license retained. Dataset metadata states CC BY 4.0; review file-specific licenses before reuse. No measurement files bundled here. |
| `dataverse.json` | Flying Laptop packet description, DOI 10.18419/darus-456, version 1.0 | University of Stuttgart / DaRUS; authors, license and file checksums retained. The document is not bundled. |
| `horizons.json` | Juno vectors, 1–4 January 2024, Sun center, ICRF axes, TDB, AU/day | NASA/JPL Solar System Dynamics, https://ssd-api.jpl.nasa.gov/doc/horizons.html . Geometry, not measured PV output. |
| `pds.json` | Two Product_Bundle search results | NASA PDS, https://nasa-pds.github.io/pds-api/guides/search.html . Product labels and provider metadata retained; no science data files bundled. |
| `psa.json` | Two Mars Express product metadata rows | ESA PSA team, https://meetingorganizer.copernicus.org/EPSC2024/EPSC2024-105.html . No instrument measurement files bundled. |
| `donki.json` | 28 flare records on 10–11 May 2024 | NASA CCMC / Moon-to-Mars Space Weather Analysis Office, https://ccmc.gsfc.nasa.gov/tools/DONKI/ . Research context; follow CCMC's rules-of-the-road for event studies. |

DISCOS is excluded from the anonymous snapshots: free registration and the
user's own API token are required. The connector's authentication, request
format, identity mapping and failures are covered by offline contract tests.

Do not treat historical snapshots as live data or their counts as complete
catalogue coverage. To refresh queries intentionally, run
`python scripts/check_research_connectors.py --cache-dir data/research-connectors`.
Check licensing and review changes before replacing committed fixtures.
