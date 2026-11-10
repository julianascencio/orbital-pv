Research Library
================

OrbitalPV includes a curated research library that drives the software roadmap.
The library is maintained as Markdown in the repository so papers, datasets,
technical targets, and product implications can evolve independently from the
API documentation.

Current areas
-------------

* current 2026 space-PV state of the art;
* cells, arrays, flexible PV, and specific power;
* expected-power modelling and digital twins;
* radiation environment and degradation;
* telemetry, anomaly detection, and physics-informed ML;
* open datasets and reproducible data sources;
* research gaps translated into repository backlog;
* space-based solar power and datacenter use cases;
* IESO 2026 workshop targets and product implications.

Browse the complete library
---------------------------

`Open the literature library on GitHub
<https://github.com/julianascencio/orbital-pv/tree/main/docs/literature>`_.

The research library is evidence and roadmap material. Implemented API behavior
is documented in the :doc:`../reference/index`.

Implemented 2026 expansion
--------------------------

The `implementation matrix
<https://github.com/julianascencio/orbital-pv/blob/main/docs/literature/10_2026_implementation_matrix.md>`_
maps selected 2024–2026 research to executable methods, data access and evidence
limits. It distinguishes real-observation benchmarks, independent analytic
checks, constructed scenarios and optional pretrained-model adapters.

See :doc:`../reference/research` and the corresponding modeling guides for the
implemented interfaces. Each new analysis directory contains a runner,
reproduction instructions and an executed reference result.

News-driven business cases
--------------------------

The :doc:`tandem procurement example <../gallery/space_business/plot_tandem_procurement>`
turns a November 2026 supplier announcement into an EOL power and procurement
price-ceiling study. All absolute inputs and economics are explicitly modeled;
source claims are separated from flight qualification evidence. See the
`reproduction and evidence notes
<https://github.com/julianascencio/orbital-pv/tree/main/analysis/tandem_procurement>`_.

The :doc:`array augmentation example <../gallery/space_business/plot_array_upgrade_firm_power>`
examines how eclipse storage can limit the continuous-load benefit of additional
solar generation. NASA's November 2026 announcement motivates explicitly modeled
scenarios; no ISS telemetry or actual payload allocation is inferred.

The :doc:`lunar utility example <../gallery/space_business/plot_lunar_utility_service>`
screens customer commitments against housekeeping, delivery losses, dark-interval
storage and recharge. Its source-linked scenarios are modeled, not verified
commercial node performance.

The :doc:`perovskite monitoring example <../gallery/space_business/plot_perovskite_monitoring>`
compares acquisition cadence, campaign duration and calibration stability after
JAXA's October 2026 bus-power demonstration announcement. It models detection
capability under declared noise assumptions; it does not infer flight degradation.
See the `campaign equations and reproduction notes
<https://github.com/julianascencio/orbital-pv/tree/main/analysis/perovskite_monitoring>`_.

The :doc:`SBSP delivery example <../gallery/space_business/plot_sbsp_delivery>`
separates annual energy targets from continuous power service and ideal backup
requirements. It implements the source-backed P7.3 backlog with explicitly
constructed profiles, not operational orbital-power data.

The :doc:`deployment evidence example <../gallery/space_business/plot_deployment_evidence>`
uses ESA's October 2026 CRISTAL testing update to motivate exact binomial
confidence bounds and fixed zero-failure sample plans. All trial records are
synthetic; neither test success nor statistical bounds replace qualification.

The :doc:`Mars pointing reserve example <../gallery/space_business/plot_mars_pointing>`
uses NASA's November 9, 2026 ESCAPADE update to motivate seasonal array pointing
and bus-reserve constraints. It reuses NASA Mars24 geometry and compares a
fixed-distance baselines with 36 assumed sizing/load/retention cases. Results are
modeled, not ESCAPADE telemetry or specifications. See the
`inputs, equations and reproduction notes
<https://github.com/julianascencio/orbital-pv/tree/main/analysis/mars_pointing>`_.
