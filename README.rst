************
fatoptimizer
************

.. image:: https://travis-ci.org/vstinner/fatoptimizer.svg?branch=master
   :alt: Build status of fatoptimizer on Travis CI
   :target: https://travis-ci.org/vstinner/fatoptimizer

.. image:: http://unmaintained.tech/badge.svg
   :target: http://unmaintained.tech/
   :alt: No Maintenance Intended

``fatoptimizer`` is a static optimizer for Python 3.6 using function
specialization with guards. It is implemented as an AST optimizer.

Optimized code requires the ``fat`` module at runtime if at least one
function was specialized.

* `fatoptimizer documentation
  <https://fatoptimizer.readthedocs.io/en/latest/>`_
* `fatoptimizer project at GitHub
  <https://github.com/vstinner/fatoptimizer>`_ (code, bug tracker)
* `fat module <https://fatoptimizer.readthedocs.io/en/latest/fat.html>`_
* `FAT Python
  <https://faster-cpython.readthedocs.io/fat_python.html#fat-python>`_
* `fatoptimizer tests running on the Travis-CI
  <https://travis-ci.org/vstinner/fatoptimizer>`_
