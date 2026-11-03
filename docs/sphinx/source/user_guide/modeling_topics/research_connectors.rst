Free spacecraft and PV research APIs
====================================

Eight connectors extend the orbit, irradiance and flight-telemetry sources.
They discover technical evidence, mission products and geometry for the
satellite/component catalogue and subsequent power analysis. They are included
in the base ``orbital-pv`` installation and need no additional dependencies.

Access and scope
----------------

.. list-table:: Available adapters
   :header-rows: 1
   :widths: 24 20 56

   * - Public class
     - Access
     - Data and interpretation
   * - ``NtrsConnector``
     - Anonymous
     - NASA report metadata and available documents. PV specifications must
       be extracted and reviewed; some records contain metadata only.
   * - ``DiscosConnector``
     - Free account/token
     - ESA object mass, dimensions, identity and mission/launch relationships.
       No ephemerides or standardized PV-capacity field.
   * - ``ZenodoConnector``
     - Anonymous public records
     - Published datasets, DOI/version/license metadata and open file downloads.
       Restricted files are not unlocked by this connector.
   * - ``DataverseConnector``
     - Anonymous public datasets
     - Dataset search, published versions and original file downloads.
       Defaults to the University of Stuttgart's DaRUS installation.
   * - ``HorizonsConnector``
     - Anonymous
     - JPL vectors for supported spacecraft and other targets, including
       Sun-relative geometry. These are ephemerides, not measured PV power.
   * - ``PdsConnector``
     - Anonymous
     - NASA PDS mission product discovery, labels and data links.
       Archive coverage and engineering-product availability vary.
   * - ``PsaConnector``
     - Anonymous public products
     - ESA PSA ADQL queries with column metadata and download links.
       Scientific and housekeeping products have different meanings.
   * - ``DonkiConnector``
     - Anonymous CCMC endpoint
     - Space-weather event records and links. These provide context,
       not satellite-specific radiation dose or proven degradation causes.

Seven anonymous services were exercised with real requests on 3 November 2026.
DISCOS was tested with mocked responses because no user token was available.
Access checks are snapshots, not uptime or permanent access guarantees. Free
access does not give every dataset the same redistribution license; retain
the record's license, copyright and attribution requirements.

Response and caching contract
-----------------------------

Every query returns ``ResearchResponse``:

* ``data``: the original provider JSON structure, preserving pagination,
  identifiers, units, quality fields, licenses and version metadata;
* ``receipt``: source, response URL, retrieval time, SHA-256 and byte count;
* ``request_url``: the exact query URL, without authentication headers;
* ``documentation``: the provider's interface documentation.

``cache_path`` writes the original response and a ``.provenance.json`` sidecar.
Reusing that path verifies both the query and checksum. A different query,
missing sidecar or corrupted file raises an error. Use ``refresh=True`` to
explicitly replace a snapshot. Caches do not expire automatically; inspect
``receipt.retrieved_at`` when freshness matters. HTTP failures, including
401/403/429, are raised rather than returned as empty datasets. The original
HTTP response exposes ``Retry-After`` to the caller; there is no automatic
retry loop. Pagination is explicit and bounded to one requested page.

Discover PV specifications in NASA reports
------------------------------------------

.. code-block:: python

   import orbitalpv as opv

   with opv.NtrsConnector() as api:
       page = api.search(
           '"solar array" "end of life"', offset=0, page_size=25,
           cache_path="data/research/ntrs-page-0.json",
       )
       for record in page.data["results"]:
           print(record["id"], record["title"], record.get("downloadsAvailable"))
       report = api.citation(20200000669)
       receipt = api.download_document(
           20200000669, "20200000669.pdf", "data/research/20200000669.pdf",
       )

NTRS offsets are zero-based record positions: the next page above starts at
25, not 1. The currently supported GET search interface is marked deprecated
in NASA's OpenAPI schema; the adapter's endpoint should be rechecked if NASA
removes that interface. No entire report corpus is crawled automatically.

When proposing catalogue fields, distinguish measured output, rated capacity,
design requirements and simulations. Record beginning/end-of-life state,
temperature, distance from the Sun, array versus bus/payload power, units and
the exact supporting passage. An abstract is a discovery lead, not automatic
authorization to fill a satellite's power rating. Follow
:doc:`satellite_catalogue` for evidence review and conservative merging.

Complete satellite metadata with DISCOS
---------------------------------------

Create a free ESA Space Debris User account, accept the DISCOSweb terms and
obtain an API token. The library never creates an account or reads environment
variables implicitly. Pass the token explicitly:

.. code-block:: python

   import os
   import orbitalpv as opv

   with opv.DiscosConnector(token=os.environ["DISCOS_TOKEN"]) as api:
       matches = api.by_norad(25544, cache_path="data/research/discos-iss.json")
       print(matches.data["data"])
       # For a known DISCOS internal ID, use api.object(discos_id).

NORAD numbers and DISCOS internal IDs must not be interchanged. Empty and
multiple matches remain visible. Token headers are not written to receipts.
Respect ESA's account terms before redistributing metadata.

Discover and download published research datasets
-------------------------------------------------

.. code-block:: python

   import orbitalpv as opv

   with opv.ZenodoConnector() as api:
       found = api.search("OPSSAT", page=1, page_size=10)
       dataset = api.record(15108715)  # Fixed OPS-SAT-AD release
       print(dataset.data["metadata"]["license"])
       api.download_file(15108715, "requirements.txt", "data/research/requirements.txt")

   with opv.DataverseConnector() as api:
       found = api.search("Flying Laptop", start=0, page_size=10)
       description = api.dataset("doi:10.18419/darus-456", version="1.0")
       api.download_file(
           "doi:10.18419/darus-456", "FLP_TM.pdf", "data/research/FLP_TM.pdf",
           version="1.0",
       )

Zenodo pages start at 1 and anonymous page size is capped at 25. Dataverse's
``start`` is a zero-based record offset; supply ``base_url`` for another
Dataverse installation. Pin published numeric versions for reproducibility.
Downloads verify provider checksums, preserve license/version context in
sidecars, and default to a 100 MB limit. Inspect metadata before deliberately
raising ``max_bytes``. Dataverse requests original files so tabular conversion
does not silently invalidate the provider checksum. Files are never executed
or extracted. These generic adapters complement the specialized Flying Laptop
and OPS-SAT loaders, which already know their measurement formats.

Retrieve geometry and mission products
--------------------------------------

.. code-block:: python

   import orbitalpv as opv

   with opv.HorizonsConnector() as api:
       ephemeris = api.vectors(
           "-61", start="2024-01-01", stop="2024-01-04", step="1 d",
           cache_path="data/research/juno-vectors.json",
       )
       print(ephemeris.data["result"])

   with opv.PdsConnector() as api:
       bundles = api.search('(product_class eq "Product_Bundle")', limit=10)
       if bundles.data["data"]:
           product = api.product(bundles.data["data"][0]["id"])

   with opv.PsaConnector() as api:
       products = api.query(
           "SELECT TOP 10 granule_uid, instrument_host_name, access_url "
           "FROM psa.epn_core WHERE instrument_host_name = 'Mars Express'",
           max_records=10,
       )
       print(products.data["metadata"], products.data["data"])

Horizons defaults are Sun-centered geometric vectors, ICRF axes, AU/day units
and **TDB** dates; they must not be relabeled as UTC. The returned text contains
the provider's original headers and ephemeris. Ambiguous targets or unavailable
coverage raise an error. These vectors do not supply array attitude or shading.

PDS uses its own ``q`` expression syntax. For cursor pagination, pass both
``sort`` and ``search_after``. Its documented ``keywords`` parameter returned
unfiltered records during live verification, so this connector deliberately
exposes explicit expressions instead. Empty results can mean incomplete
archive coverage. PSA is a bounded SELECT interface; a result reaching
``max_records`` may be truncated. For both archives, inspect product labels,
calibration, units and access terms before downloading or interpreting data.

Add space-weather event context
-------------------------------

.. code-block:: python

   import orbitalpv as opv

   with opv.DonkiConnector() as api:
       events = api.events(
           "FLR", start="2024-05-10", stop="2024-05-11",
           cache_path="data/research/flares.json",
       )
       for event in events.data or []:
           print(event["beginTime"], event["classType"], event["link"])

Supported event types are CME, FLR, SEP, GST, IPS, MPC, RBE and HSS. UTC date
endpoints are inclusive under DONKI's convention. The raw empty response may
be null or a list. This uses CCMC's direct free endpoint and does not need an
api.nasa.gov key. The base host follows the September 2026 migration to
``ccmc.gsfc.nasa.gov``. Follow CCMC's research-use and attribution policy.

Reproduce the access check
--------------------------

The :doc:`../../gallery/real_data/plot_research_connectors` example runs offline
against small original responses captured from all seven anonymous APIs.
From an installed checkout, explicitly refresh real queries with:

.. code-block:: bash

   python scripts/check_research_connectors.py --cache-dir data/research-connectors
   # Optional, after configuring a free DISCOS account/token:
   python scripts/check_research_connectors.py --cache-dir data/research-connectors --discos

The script writes a machine-readable access report and exits nonzero if any
selected provider fails. These new connector examples use committed snapshots
during CI and documentation builds.

Primary interface references
----------------------------

* `NASA NTRS OpenAPI <https://ntrs.nasa.gov/api/openapi/>`_.
* `ESA DISCOSweb <https://discosweb.esoc.esa.int/>`_ and
  `ESA's access/API paper <https://conference.sdo.esoc.esa.int/proceedings/sdc8/paper/204/SDC8-paper204.pdf>`_.
* `Zenodo REST API <https://developers.zenodo.org/>`_.
* `Dataverse Search API <https://guides.dataverse.org/en/latest/api/search.html>`_
  and `Data Access API <https://guides.dataverse.org/en/latest/api/dataaccess.html>`_.
* `JPL Horizons API <https://ssd-api.jpl.nasa.gov/doc/horizons.html>`_.
* `NASA PDS Search API <https://nasa-pds.github.io/pds-api/guides/search.html>`_.
* `ESA PSA team's TAP access paper <https://meetingorganizer.copernicus.org/EPSC2024/EPSC2024-105.html>`_.
* `NASA CCMC DONKI, migration notice and policies <https://ccmc.gsfc.nasa.gov/tools/DONKI/>`_.
