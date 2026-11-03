Satellite and space-power catalogue
===================================

The catalogue follows the Energy Data Insights pattern: reviewable JSONL records,
stable identities, field-level evidence and reproducible typed Parquet snapshots.
It lives entirely in OrbitalPV. The initial batch contains **27 spacecraft and 20
components** from agency, mission-team and manufacturer sources. It is deliberately
an initial research sample, not a global completeness claim.

Explore the viewer, executable examples and public API:

* :doc:`/database-viewer`
* :doc:`/gallery/database/index`
* :doc:`/reference/catalogue`

Install and query
-----------------

These additions are in the source tree until a release includes them. From a
checkout, install the analytical extra:

.. code-block:: bash

   python -m pip install ".[catalogue,examples]"
   python -m orbitalpv.catalogue validate
   python -m orbitalpv.catalogue build --output outputs/satellite-snapshot

Each build requires a new output directory. Canonical records are included in the
wheel, so basic queries work offline after installation without a repository path:

.. code-block:: python

   import pandas as pd
   from orbitalpv import catalogue

   satellites = pd.DataFrame(catalogue.load_records("satellites"))
   components = pd.DataFrame(catalogue.load_records("components"))
   print(satellites[["name", "pv_power_w", "power_basis", "power_conditions"]])
   print(catalogue.coverage())

   # Flat typed columns; nested evidence remains serialized JSON in Parquet.
   frame = pd.read_parquet("outputs/satellite-snapshot/satellites.parquet")
   print(frame[["name", "pv_power_w", "reference_distance_au"]])

Inputs, methods and outputs
---------------------------

**Inputs:** selected public agency mission pages and exact OEM datasheets, retained
in the source registry with access dates and revision information where available.
Sources were read online; ``sha256=null`` means raw document bytes were not archived,
not that a document checksum was verified.

**Methods:** explicit unit conversions, identity checks, source-to-field mapping,
qualified rating validation, conflict-preserving merges and completeness counts.
No capacity is estimated from satellite mass, photos, cell efficiency, orbital
elements or a constellation-wide total. No internet call occurs during validation,
Python queries, tests or documentation builds.

**Outputs:** ``satellites.parquet``, ``components.parquet``, browser JSON projections
read back from those Parquet files, ``sources.json``, ``schema.json``, attribution
notice and a manifest with hashes and field-completeness counts. Parquet floats,
64-bit integers and lists have explicit types, including all-null columns. Nested
``*_json`` fields use canonical JSON strings in Parquet and objects in browser JSON.

The manifest pins the canonical content and every generated file, and records
PyArrow's version. Identical inputs and exporter version reproduce the same bytes.
Browser checksums detect mismatched assets, not a maliciously replaced manifest.

Power semantics
---------------

``pv_power_w`` is a preferred, directly supported array-output assertion with its
qualifier, life basis and conditions. It can be approximate, a lower bound or an
upper bound; it is never automatically a measured maximum-power-point value.
``power_ratings_json`` keeps alternate conditions, ranges and conflicting assertions.
When no preferred scalar is justified, it stays null even if alternate ratings exist.

* **BOL/EOL** mean beginning/end of life only when the source says so.
* **Mission reference** preserves the mission phase or operating condition. It
  does not assert an explicit BOL/EOL qualification.
* ``reference_distance_au`` is the reference for a power statement, not the
  spacecraft's present location. Temperature and irradiance remain nullable.
* ``reported_spacecraft_power_w`` holds ambiguous spacecraft/bus power separately.
  Payload consumption, EPS throughput and battery energy are never PV watts.
* ``cell_efficiency_pct`` travels with its conditions and whether the value is a
  minimum average, production average or typical value. Bare cells and CICs with
  coverglass are distinct configurations. AM0 irradiance conventions differ.
* Batteries retain Wh and Ah separately. Array area is not inferred from panel
  envelope dimensions or silently replaced by active cell/coverglass area.

There is no global PV-wattage total. For example, Rosetta's 850 W at 3.4 AU and
395 W at 5.25 AU describe the same arrays in different conditions. Psyche's Earth
and asteroid ratings must not be counted as separate installed systems. Design
specifications do not establish present spacecraft health or live generation.

Connected catalogues
--------------------

The ``satellites`` table covers an individual spacecraft or independently documented
module, including Earth satellites, planetary orbiters and deep-space probes.
No parent mission is counted again when a module is catalogued. The component table
covers exact OEM models or explicitly documented configurations of solar cells,
CICs, panels, arrays, EPS electronics and batteries.

``component_ids`` records only direct installation/configuration evidence. Current
examples are DART/ROSA, Europa Clipper/Airbus arrays and SPACE HAUC's documented
EnduroSat/GomSpace hardware. Matching manufacturers is not proof of installation.
No exact AZUR cell model is assigned to Europa Clipper without evidence.

Identity and update contract
----------------------------

The canonical directory is ``src/orbitalpv/catalogue/data``. Packaging the single
source of truth here makes the same records available in wheels and source checkouts;
there is no second editable copy under ``catalogues/`` or in the viewer.

Records use UUID5 over an immutable identity key. Preserve an existing identity when
adding a NORAD/COSPAR identifier later. Exact OEM model case and punctuation matter.
One JSONL line is one record, sorted by ID in a two-character identity shard.
Creation, content-update and source-verification timestamps are separate UTC fields.

Register evidence in ``sources.json`` first; add exact URLs, publisher, revision and
reuse notes. Every populated factual field needs source IDs in
``field_sources_json``. Every cited source needs a concise locator and evidence
summary. Unknown data stays absent/null, never zero or a guessed nominal value.

``merge_records(existing, incoming, now=...)`` is a pure conservative merge helper.
It fills unknown fields. Any conflicting existing assertion keeps the entire record
unchanged and emits the incoming assertion to a review list. It does not overwrite
nested ratings, old evidence or timestamps on identical observations. Validate the
complete proposed catalogue before writing canonical JSONL in a reviewed branch.
It is not a multi-writer database transaction.

The schema is versioned in ``schema.json``. Add new nullable columns through a
reviewed minor schema revision; changes to meaning, units, removals or renames need
a major revision and migration. Preserve source-specific fields in namespaced
``extensions_json`` until a common column is justified.

Orbital identifiers and future expansion
----------------------------------------

``stage_omm`` accepts an already downloaded CCSDS OMM/CelesTrak JSON list and stages
identity candidates with NORAD/COSPAR IDs, including six-digit NORAD numbers:

.. code-block:: bash

   python -m orbitalpv.catalogue stage-omm \
     --input downloaded-omm.json --source-id reviewed_celestrak_snapshot \
     --now 2026-11-02T23:00:00Z --output candidates.jsonl

It neither downloads nor admits records automatically. Before admission, register
the exact source, hash the downloaded bytes, respect provider terms, and check aliases
against existing mission identities. OMM lacks PV capacity and does not prove current
operating status. Orbital tracking stays in the existing orbit/connectors APIs.

The first batch does not provide a full satellite identity inventory, live positions,
constellation-wide PV totals or comprehensive operator/manufacturer geography. Its
open backlog prioritizes Starlink, OneWeb, Kuiper, navigation, GEO telecom, Chinese
missions, additional JAXA/ISRO missions and qualified EOL/temperature data. OEM model
and spacecraft linkage needs independent evidence; constellation-level ratings must
never be copied indiscriminately to individual satellites.
