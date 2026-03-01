.. _openapi-parser-evaluation:

OpenAPI Parser Evaluation
=========================

This document evaluates whether openapi-mock should use `openapi-parser`_ or a
similar library for parsing OpenAPI specs, instead of the current approach of
loading JSON/YAML and iterating over the spec dict directly.

Current Approach
----------------

openapi-mock currently:

- Loads specs via ``load_spec`` (JSON or YAML to dict)
- Iterates over ``paths`` and operations manually
- Extracts response examples/schemas from operations

This is minimal and has no external OpenAPI parsing dependencies beyond PyYAML.

Evaluated Libraries
-------------------

openapi-parser (PyPI)
  - **Status**: Pre-alpha (0.2.6, July 2021)
  - **Focus**: Client/server code generation from OpenAPI 3.0
  - **Fit**: Poor. Designed for codegen, not mock routing. No recent updates.

openapi-core
  - **Status**: Active (python-openapi/openapi-core)
  - **Focus**: Validation, request/response unmarshalling, framework integration
  - **Fit**: Overkill for mock routing. Adds validation and full spec handling
    we do not need. Could help with ``$ref`` resolution if we add that later.

prance
  - **Status**: Active
  - **Focus**: Resolving Swagger/OpenAPI 2.0 and 3.0 specs (``$ref``, etc.)
  - **Fit**: Useful if we need ``$ref`` resolution. Heavier dependency.

openapi-spec-validator
  - **Status**: Active
  - **Focus**: Validation only
  - **Fit**: Validation only; we do not validate specs today.

Recommendation
--------------

**Do not adopt openapi-parser or similar for now.**

Reasons:

1. **openapi-parser** is outdated and pre-alpha, with a different purpose
   (code generation).

2. **Current approach is sufficient** for the library's scope: adding mock
   routes from paths and operations. We do not need validation, ``$ref``
   resolution, or full spec modeling.

3. **Minimal dependencies** keep the package lightweight and easy to
   maintain.

4. **Future consideration**: If we add ``$ref`` support or validation,
   `prance`_ or `openapi-core`_ would be better candidates than
   openapi-parser.

.. _openapi-parser: https://pypi.org/project/openapi-parser/
.. _prance: https://pypi.org/project/prance/
.. _openapi-core: https://github.com/python-openapi/openapi-core
