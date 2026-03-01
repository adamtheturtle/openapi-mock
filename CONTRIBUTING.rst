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
