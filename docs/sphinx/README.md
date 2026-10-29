# OrbitalPV documentation

The public documentation uses Sphinx, PyData Sphinx Theme, and Sphinx-Gallery,
following the general scientific-Python documentation pattern used by pvlib.

Build locally from the repository root:

    uv sync --all-packages --group docs
    make docs

The generated site is written to `docs/sphinx/build/html`.

Documentation pull requests are validated with warnings treated as errors.
