Contributing
============

Development setup
----------------

.. code-block:: console

   uv sync --all-extras

Running tests
-------------

.. code-block:: console

   uv run pytest

Linting
-------

.. code-block:: console

   uv run ruff check .
   uv run ruff format --check .

Type checking
-------------

.. code-block:: console

   uv run pyright --ignoreexternal --verifytypes openapi_mock

Documentation (manual hooks)
----------------------------

Before releases, run linkcheck, spelling, and docs build:

.. code-block:: console

   pre-commit run --hook-stage manual linkcheck --all-files
   pre-commit run --hook-stage manual spelling --all-files
   pre-commit run --hook-stage manual docs --all-files
