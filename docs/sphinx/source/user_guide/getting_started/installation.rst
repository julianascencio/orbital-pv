.. _installation:

Installation
============

OrbitalPV currently targets **Python 3.13 or newer** and uses `uv
<https://docs.astral.sh/uv/>`_ for workspace and dependency management.

Install from source
-------------------

Clone the repository and create the development environment:

.. code-block:: bash

   git clone https://github.com/julianascencio/orbital-pv.git
   cd orbital-pv
   uv sync --all-packages --group dev --group lab

For the full scientific stack:

.. code-block:: bash

   uv sync --all-packages --group dev --group lab --group pv --group orbit --group space

For application development:

.. code-block:: bash

   uv sync --all-packages --group app

For documentation development:

.. code-block:: bash

   uv sync --all-packages --group docs
   make docs

Verify the installation
-----------------------

.. code-block:: bash

   uv run ruff format --check .
   uv run ruff check .
   uv run ty check
   uv run pytest

Optional services
-----------------

The full application stack uses PostgreSQL/PostGIS and Redis. Start the local
development services with:

.. code-block:: bash

   docker compose up --build
