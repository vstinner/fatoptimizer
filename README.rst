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

    tox

You may need to install or update tox::

    pip3 install -U tox

Run manually tests::

    python3 test_fatoptimizer.py

There are also integration tests which requires a Python 3.6 with patches PEP
509, PEP 510 and PEP 511. Run integration tests::

    python3.6 -X fat test_fat_config.py
    python3.6 -X fat test_fat_size.py


Changelog
=========

* 2016-01-14: First public release.
