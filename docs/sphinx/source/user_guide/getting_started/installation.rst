.. _installation:

Installation
============

Install OrbitalPV from PyPI
---------------------------

OrbitalPV targets **Python 3.13 or newer**. For normal use, install the public
distribution from PyPI:

.. code-block:: bash

   python -m pip install orbital-pv

Then import the package as:

.. code-block:: python

   import orbitalpv as opv

Optional extras
---------------

For plotting the documentation examples:

.. code-block:: bash

   python -m pip install "orbital-pv[examples]"

For advanced orbit/ephemeris adapters:

.. code-block:: bash

   python -m pip install "orbital-pv[orbit]"

For the broader optional stack:

.. code-block:: bash

   python -m pip install "orbital-pv[full]"

The research expansion in the source tree adds ``netcdf`` for CERES and
POES/MetOp files and ``ground-research`` for optional vector-inventory readers
and the official EUMETSAT SDK. Install them from a checkout containing that
expansion:

.. code-block:: bash

   python -m pip install ".[netcdf,ground-research,orbit,examples]"

The numerical flight and spacecraft physics APIs use the base NumPy/pandas
stack. Provider credentials and externally supplied neural-model weights are
runtime inputs, not installation dependencies.

Development installation
------------------------

Contributors should clone the repository and use the uv workspace:

.. code-block:: bash

   git clone https://github.com/julianascencio/orbital-pv.git
   cd orbital-pv
   uv sync --all-packages --group dev --group lab --group ground

Documentation development:

.. code-block:: bash

   uv sync --all-packages --group docs --group ground
   make docs

Verify the development environment
----------------------------------

.. code-block:: bash

   uv run ruff format --check .
   uv run ruff check .
   uv run ty check
   uv run pytest
