openapi-mock
============

|Build Status| |PyPI|

Serve an OpenAPI spec as a mock with `respx`_ or `responses`_.
Uses `openapi-core`_ for spec validation and $ref resolution.

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

With respx (httpx)
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from http import HTTPStatus

   import httpx
   import respx

   from openapi_mock import add_openapi_to_respx

   spec = {
       "openapi": "3.0.0",
       "info": {"title": "API", "version": "1.0.0"},
       "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK"}}}}},
   }
   with respx.mock(base_url="https://api.example.com", assert_all_called=False) as m:
       add_openapi_to_respx(mock_obj=m, spec=spec, base_url="https://api.example.com")
       response = httpx.get(url="https://api.example.com/pets")
   assert response.status_code == HTTPStatus.OK

With responses (requests)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from http import HTTPStatus

   import requests
   import responses

   from openapi_mock import add_openapi_to_responses

   spec = {
       "openapi": "3.0.0",
       "info": {"title": "API", "version": "1.0.0"},
       "paths": {"/pets": {"get": {"responses": {"200": {"description": "OK"}}}}},
   }
   with responses.RequestsMock() as rsps:
       add_openapi_to_responses(spec=spec, base_url="https://api.example.com", mock=rsps)
       response = requests.get(url="https://api.example.com/pets", timeout=30)
   assert response.status_code == HTTPStatus.OK

.. _respx: https://lundberg.github.io/respx/
.. _responses: https://github.com/getsentry/responses
.. _openapi-core: https://github.com/python-openapi/openapi-core
