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
