openapi-mock
============

Serve an OpenAPI spec as a mock with `respx`_.

Installation
------------

.. code-block:: console

   uv pip install openapi-mock

Or with pip:

.. code-block:: console

   pip install openapi-mock

Usage
-----

.. code-block:: python

   from openapi_mock import add_openapi_to_respx
   import httpx, respx

   with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
       add_openapi_to_respx(m, spec, base_url="https://api.example.com")
       httpx.get("https://api.example.com/pets")

.. _respx: https://lundberg.github.io/respx/
