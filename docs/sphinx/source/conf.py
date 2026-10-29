from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

for src in [
    ROOT / "src",
    *ROOT.glob("packages/*/src"),
    ROOT / "apps/space-pv-api/src",
    ROOT / "apps/space-pv-cli/src",
]:
    sys.path.insert(0, str(src))

with (ROOT / "pyproject.toml").open("rb") as file:
    _project = tomllib.load(file)["project"]

project = "OrbitalPV"
author = "OrbitalPV contributors"
release = _project["version"]
version = release
copyright = "2026, OrbitalPV contributors"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_gallery.gen_gallery",
]

autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "astropy": ("https://docs.astropy.org/en/stable/", None),
    "pvlib": ("https://pvlib-python.readthedocs.io/en/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = []
source_suffix = ".rst"
master_doc = "index"

html_theme = "pydata_sphinx_theme"
html_title = "OrbitalPV"
html_static_path = ["_static"]
html_show_sourcelink = False

html_theme_options = {
    "github_url": "https://github.com/julianascencio/orbital-pv",
    "use_edit_page_button": True,
    "show_toc_level": 2,
    "show_prev_next": False,
    "navbar_align": "left",
}

html_context = {
    "github_user": "julianascencio",
    "github_repo": "orbital-pv",
    "github_version": "main",
    "doc_path": "docs/sphinx/source",
}

sphinx_gallery_conf = {
    "examples_dirs": str(ROOT / "examples"),
    "gallery_dirs": "gallery",
    "filename_pattern": r"/plot_",
    "download_all_examples": False,
    "remove_config_comments": True,
}


def setup(app):
    app.add_css_file("orbitalpv.css")
