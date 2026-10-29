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

Development installation
------------------------

Contributors should clone the repository and use the uv workspace:

.. code-block:: bash

   git clone https://github.com/julianascencio/orbital-pv.git
   cd orbital-pv
   uv sync --all-packages --group dev --group lab

Documentation development:

.. code-block:: bash

   uv sync --all-packages --group docs
   make docs

Verify the development environment
----------------------------------

.. code-block:: bash

   uv run ruff format --check .
   uv run ruff check .
   uv run ty check
   uv run pytest
