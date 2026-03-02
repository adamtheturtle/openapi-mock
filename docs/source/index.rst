|project|
=========

|project| serves an OpenAPI spec as a mock with `respx`_.

Installation
------------

Requires Python |minimum-python-version|\+.

.. code-block:: shell

   pip install openapi-mock

Usage
-----

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
       add_openapi_to_respx(
           mock_obj=m,
           spec=spec,
           base_url="https://api.example.com",
       )
       response = httpx.get(url="https://api.example.com/pets")
   assert response.status_code == HTTPStatus.OK
   assert response.json() == {}

Reference
---------

.. toctree::
   :maxdepth: 3

   api-reference
   release-process
   changelog
   contributing

.. _respx: https://lundberg.github.io/respx/
