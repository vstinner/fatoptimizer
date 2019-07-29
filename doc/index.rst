.. _fatoptimizer:

++++++++++++
fatoptimizer
++++++++++++

.. image:: https://travis-ci.org/vstinner/fatoptimizer.svg?branch=master
   :alt: Build status of fatoptimizer on Travis CI
   :target: https://travis-ci.org/vstinner/fatoptimizer

``fatoptimizer`` is a static optimizer for Python 3.6 using function
specialization with guards. It is implemented as an AST optimizer.

Optimized code requires the :ref:`fat module <fat>` at runtime if at least one
function is specialized.

Links:

* `fatoptimizer documentation
  <https://fatoptimizer.readthedocs.io/en/latest/>`_ (this documentation)
* `fatoptimizer project at GitHub
  <https://github.com/vstinner/fatoptimizer>`_ (code, bug tracker)
* `FAT Python
  <https://faster-cpython.readthedocs.io/fat_python.html>`_
* `fatoptimizer tests running on the Travis-CI
  <https://travis-ci.org/vstinner/fatoptimizer>`_

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
