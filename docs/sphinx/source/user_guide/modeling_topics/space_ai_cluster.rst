Solar-powered AI satellite clusters
==================================

This study adds the supplied arXiv:2511.19468v2 paper to OrbitalPV with a
version-pinned arXiv connector, curated numerical evidence, reusable optical,
formation, radiation and launch-economics methods, and an offline trade study.
It reuses the existing solar, eclipse, battery and radiator screening models.

Run from the source checkout::

   python -m pip install -e ".[examples]"
   python analysis/space_ai_cluster/run.py --output outputs/space_ai_cluster
   python examples/space_business/plot_space_ai_cluster.py

See the :doc:`runnable gallery </gallery/space_business/plot_space_ai_cluster>`
and `full equations, evidence, limitations and reference results
<https://github.com/julianascencio/orbital-pv/tree/main/analysis/space_ai_cluster>`_.
The `paper version <https://arxiv.org/abs/2511.19468v2>`_ is dated June 17, 2026.

Connectors and reproducibility
-----------------------------

``orbitalpv.data.ArxivConnector`` fetches an explicit paper version and records
the original response hash, request URL and retrieval time. Its offline cache
rejects mismatched versions and modified bytes. The numerical evidence snapshot
is separately curated from the PDF; live bibliographic metadata never silently
changes engineering inputs. Both the source hash and page locators are retained.

Optional metadata refresh::

   python analysis/space_ai_cluster/fetch_metadata.py

The runner writes nine CSV tables and input provenance. Pass ``--input`` to use
a modified copy of the packaged JSON. The default runner and gallery are offline;
the snapshot is also included in the installed wheel.

What the models establish
------------------------

* Far-field Friis power, photon and electronics ceilings, receiver margin and
  propagation latency. Near-field confocal geometry is reported separately.
* An independent 81-satellite HCW formation at the paper's 650 km / 1 km scale,
  with sampled clearances and neighbor distances, without J2 control claims.
* Conditional radiation event counts and TID context; distinct SDC, HBM UECC,
  TPU SEFI and host CPU/RAM events are never combined into a measured failure rate.
* Launch-only cost and learning-curve sensitivities, with reported Table 1 costs
  kept beside calculations from rounded inputs.
* Explicit synthetic compute scenarios constrained by power, storage and heat,
  followed by a partial launch-cost/electricity comparison.

The paper's 800 Gbps one-way optical result is a short-path bench demonstration.
Its 9.6 Tbps DWDM wording uses a different direction convention; the model
explicitly assumes 400 Gbps per channel per direction, without doubling the
paper's claim. A screen is not observed orbital throughput.

Electrical compute capacity is not AI throughput. Annual radiation dose is an
input, not inferred from shielding or a weather index. J2 formation control,
transport-based radiation analysis, training performance, ground-network
availability, full spacecraft mass closure and total cost of ownership remain
outside this implementation.
