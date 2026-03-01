openapi-mock
============

|Build Status| |PyPI|

Serve an OpenAPI spec as a mock with `respx`_.

.. |Build Status| image:: https://github.com/adamtheturtle/openapi-mock/actions/workflows/ci.yml/badge.svg?branch=main
   :target: https://github.com/adamtheturtle/openapi-mock/actions/workflows/ci.yml
.. |PyPI| image:: https://badge.fury.io/py/openapi-mock.svg
   :target: https://badge.fury.io/py/openapi-mock

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

   spec = {
       "openapi": "3.0.0",
       "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK"}}}}},
   }
   with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
       add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
       response = httpx.get("https://api.example.com/pets")
   assert response.status_code == 200

.. _respx: https://lundberg.github.io/respx/
