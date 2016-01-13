**********
FAT Python
**********

FAT Python
==========

FAT Python is a static optimizer for Python 3.6 using function specialization
with guards.

The ``fat`` module is the runtime part of the optimizer. It is required to run
optimized code. The optimizer is the ``fatoptimizer`` module.

* FAT Python: http://faster-cpython.readthedocs.org/fat_python.html
* fat module: https://github.com/haypo/fat
* fatoptimizer module: https://github.com/haypo/fatoptimizer

fatoptimizer requires Python 3.6 patched with the PEP 511 (ast.Constant,
sys.ast_tranformers).

.. warning::
   The API is not stable yet.


fatoptimizer module API
=======================

* Config()
* pretty_dump()
* OptimizerError
* optimize(tree, filename, config)


Installation
============

Type::

    pip install fatoptimizer

Manual installation::

    python3.6 setup.py install


Run tests
=========

Type::

    python3.6 test_fatoptimizer.py


Changelog
=========

* 2016-01-13: First public release.
