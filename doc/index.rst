.. _fatoptimizer:

++++++++++++
fatoptimizer
++++++++++++

.. image:: https://img.shields.io/pypi/v/fatoptimizer.svg
   :alt: Latest release on the Python Cheeseshop (PyPI)
   :target: https://pypi.python.org/pypi/fatoptimizer

.. image:: https://travis-ci.org/haypo/fatoptimizer.svg?branch=master
   :alt: Build status of fatoptimizer on Travis CI
   :target: https://travis-ci.org/haypo/fatoptimizer

``fatoptimizer`` is a static optimizer for Python 3.6 using function
specialization with guards. It is implemented as an AST optimizer.

Optimized code requires the :ref:`fat module <fat>` at runtime if at least one
function is specialized.

Links:

* `fatoptimizer documentation
  <https://fatoptimizer.readthedocs.org/en/latest/>`_ (this documentation)
* `fatoptimizer project at GitHub
  <https://github.com/haypo/fatoptimizer>`_ (code, bug tracker)
* `fatoptimizer project at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/fatoptimizer>`_ (download releases)
* `FAT Python
  <https://faster-cpython.readthedocs.org/fat_python.html>`_
* `fatoptimizer tests running on the Travis-CI
  <https://travis-ci.org/haypo/fatoptimizer>`_

The ``fatoptimizer`` module requires a Python 3.6 patched with `PEP 510
"Specialize functions with guards"
<https://www.python.org/dev/peps/pep-0510/>`_ and `PEP 511 "API for code
transformers" <https://www.python.org/dev/peps/pep-0511/>`_ patches.


Table Of Contents
=================

.. toctree::
   :maxdepth: 1

   fatoptimizer
   fat
   optimizations
   semantics
   benchmarks
   microbenchmarks
   changelog
   todo
   gsoc
   misc
