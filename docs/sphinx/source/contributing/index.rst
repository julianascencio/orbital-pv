Contributing
============

OrbitalPV welcomes reproducible improvements to models, connectors, analytics,
tests, examples, and documentation.

Development setup
-----------------

.. code-block:: bash

   git clone https://github.com/julianascencio/orbital-pv.git
   cd orbital-pv
   uv sync --all-packages --group dev --group lab --group docs

Before opening a pull request
-----------------------------

.. code-block:: bash

   uv run ruff format .
   uv run ruff check .
   uv run ty check
   uv run pytest
   make docs

AI-assisted contribution policy
-------------------------------

OrbitalPV is intentionally AI-assisted. A substantial share of repository
content may be generated or drafted with AI, including code, documentation,
tests, examples, and research synthesis.

AI assistance does not replace scientific provenance. Contributors should:

* select and cite the specific literature, datasets, standards, or technical
  reports that motivate a method or parameterization;
* distinguish literature-backed values from engineering assumptions,
  placeholders, or illustrative defaults;
* review AI-generated implementations for physical validity, numerical
  correctness, units, edge cases, and reproducibility;
* add tests and validation evidence appropriate to the claimed fidelity;
* avoid presenting AI-generated text or code as independent scientific
  validation;
* update the literature library when new sources materially influence the
  repository.

The intended workflow is **developer-selected evidence -> AI-assisted
implementation -> human review, testing, and progressive validation**. Some
parts of the repository remain early-stage and may contain AI-generated errors
or imperfect interpretations, so deeper validation should grow alongside the
project.

Scientific contributions
------------------------

Model or analysis changes should state:

* the physical or statistical assumptions;
* reference frame and time convention where relevant;
* units;
* source data and provenance;
* validation evidence;
* known limitations;
* deterministic seeds for stochastic experiments.

Documentation
-------------

User-facing functionality should include both conceptual documentation and API
docstrings. Add an executable gallery example when a visual or end-to-end
workflow is the clearest way to teach the feature.

Public repository hygiene
-------------------------

Keep documentation and examples focused on OrbitalPV and public technical
sources. Do not include private employer, client, credential, or proprietary
system information.
