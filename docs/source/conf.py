"""Configuration for Sphinx."""

import importlib.metadata
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from sphinx_pyproject import SphinxConfig

_pyproject_file = Path(__file__).parent.parent.parent / "pyproject.toml"
_pyproject_config = SphinxConfig(
    pyproject_file=_pyproject_file,
    config_overrides={"version": None},
)

project = _pyproject_config.name
author = _pyproject_config.author

# Validate version - reject 0.x (indicates missing git tags)
_version_string = importlib.metadata.version(distribution_name=project)
_version = Version(version=_version_string)
if _version.release[0] == 0:
    msg = (
        f"The version is {_version_string}. "
        "This indicates that the version is not set correctly. "
        "This is likely because the project was built without having all "
        "Git tags available."
    )
    raise ValueError(msg)

# Format release string for Calver (YYYY.MM.DD)
_num_date_parts = 3
release = ".".join(
    [
        f"{part:02d}" if index < _num_date_parts else str(object=part)
        for index, part in enumerate(iterable=_version.release)
    ]
)

extensions = [
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinxcontrib.spelling",
    "sphinx_substitution_extensions",
]

templates_path = ["_templates"]

project_copyright = f"%Y, {author}"

copybutton_exclude = ".linenos, .gp"

project_metadata = importlib.metadata.metadata(distribution_name=project)
requires_python = project_metadata["Requires-Python"]
specifiers = SpecifierSet(specifiers=requires_python)
(specifier,) = specifiers
if specifier.operator != ">=":
    msg = f"We only support '>=' for Requires-Python, got {specifier.operator}."
    raise ValueError(msg)
minimum_python_version = specifier.version

html_theme = "furo"
html_title = project
html_show_copyright = False
html_show_sphinx = False
html_show_sourcelink = False
html_theme_options = {
    "sidebar_hide_name": False,
    "source_repository": "https://github.com/adamtheturtle/openapi-mock/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}

htmlhelp_basename = "openapimockdoc"

intersphinx_mapping = {
    "python": (f"https://docs.python.org/{minimum_python_version}", None),
}

nitpicky = True
# respx/httpx don't publish intersphinx inventories; ignore refs to their types.
# See https://github.com/encode/httpx/discussions/3091 and
# https://github.com/lundberg/respx/issues/305
nitpick_ignore = [
    ("py:class", "respx.router.MockRouter"),
    ("py:class", "respx.router.Router"),
]

spelling_word_list_filename = "../../spelling_private_dict.txt"

rst_prolog = f"""
.. |project| replace:: {project}
.. |release| replace:: {release}
.. |minimum-python-version| replace:: {minimum_python_version}
.. |github-owner| replace:: adamtheturtle
.. |github-repository| replace:: openapi-mock
"""
