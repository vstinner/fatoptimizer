.. _fatoptimizer:

++++++++++++
fatoptimizer
++++++++++++

FAT Python is a static optimizer for Python 3.6 using function specialization
with guards.

The optimizer is the ``fatoptimizer`` module. The ``fat`` module is the runtime
part of the optimizer, required to run optimized code.

Links:

* `fatoptimizer documentation
  <https://fatoptimizer.readthedocs.org/en/latest/>`_ (this documentation)
* `fatoptimizer project at GitHub
  <https://github.com/haypo/fatoptimizer>`_ (code, bug tracker)
* `fatoptimizer project at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/fatoptimizer>`_ (download releases)
* `fat project <https://faster-cpython.readthedocs.org/fat.html>`_
* `FAT Python
  <https://faster-cpython.readthedocs.org/fat_python.html#fat-python>`_


fatoptimizer module API
=======================

.. warning::
   The API is not stable yet.


.. function:: optimize(tree, filename, config)

   Optimize an AST tree. Return the optimized AST tree.


.. class:: Config

   Configuration of the optimizer.


.. class:: OptimizerError

   Exception raised on bugs in the optimizer.


Installation
============

fatoptimizer requires Python 3.6 patched with the PEP 511 (ast.Constant,
sys.ast_tranformers).

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


Constants
=========

FAT Python introduced a new AST type: ``ast.Constant``. The optimizer starts by
converting ``ast.NameConstant``, ``ast.Num``, ``ast.Str``, ``ast.Bytes`` and
``ast.Tuple`` to ``ast.Constant``. Later, it can create constant of other
types. For example, ``frozenset('abc')`` creates a ``frozenset`` constant.

Supported constants:

* ``None`` singleton
* ``bool``: ``True`` and ``False``
* numbers: ``int``, ``float``, ``complex``
* strings: ``bytes``, ``str``
* containers:  ``tuple``, ``frozenset``


Literals
========

Literals are a superset of constants.

Supported literal types:

* (all constant types)
* containers: ``list``, ``dict``, ``set``


.. _fatoptimizer-limits:

Limitations
===========

* Decorators are not supported (yet?)
* Keywords are not supported yet

See also the `fatoptimizer TODO file
<https://github.com/haypo/fatoptimizer/blob/master/TODO.rst>`_.


FunctionOptimizer
=================

``FunctionOptimizer`` handles ``ast.FunctionDef`` and emits a specialized
function if a call to a builtin function can be replaced with its result.

For example, this simple function::

    def func():
        return chr(65)

is optimized to::

    def func():
        return chr(65)

    _ast_optimized = func

    def func():
        return "A"
    _ast_optimized.specialize(func,
                              [{'guard_type': 'builtins', 'names': ('chr',)}])

    func = _ast_optimized
    del _ast_optimized


Detection of free variables
===========================

VariableVisitor detects local and global variables of an ``ast.FunctionDef``
node. It is used by the ``FunctionOptimizer`` to detect free variables.


Corner cases
============

Calling the ``super()`` function requires a cell variables.
