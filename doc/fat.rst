.. _fat:

++++++++++
fat module
++++++++++

FAT Python is a static optimizer for Python 3.6 using function specialization
with guards.

The ``fat`` module is the runtime part of the optimizer. It implements guards
used to specialize functions.

The ``fat`` module is required to run code optimized by the ``fatoptimizer``
module.

* `fat project at GitHub
  <https://github.com/haypo/fat>`_
* `fat project at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/fat>`_


fat module API
==============

.. warning::
   The API is not stable yet.

``fat.__version__`` is the version string.

Functions
---------

.. function:: replace_consts(code, mapping)

   Create a copy of the code object with replaced constants::

       new_consts = tuple(mapping.get(const, const) for const in consts)


.. function:: specialize(func, code, guards)

   Specialize a Python function: add a specialized code with guards.

   *code* must be a callable or code object, *guards* must be a non-empty
   sequence of guards.


.. function:: get_specialized(func)

   Get the list of specialized codes with guards as ``(code, guards)`` tuples.


See the PEP 510 for the API of ``specialize()`` and ``get_specialized()``.


Guard types
-----------

.. class:: GuardArgType(arg_index, arg_types)

    Check the type of the nth argument, *arg_types* must be a sequence of
    types.

    Keep a strong reference to *arg_types* types.


.. class:: GuardBuiltins(names)

   Watch for ``builtins.__dict__[name]`` and ``globals()[name]`` for all
   *names*.

   The guard initialization fails if ``builtins.__dict__[name]`` was replaced
   after ``fat`` was imported, or if ``globals()[name]`` already exists.

   Keep a strong references to the builtin dictionary (``builtins.__dict__``),
   to the dictionary of the global namespace (``globals()``), to *names* and to
   builtins of *names* (``builtins.__dict__[name]`` for all *names*).


.. class:: GuardDict(dict, keys)

   Watch for ``dict[key]`` for all *keys*.

   Keep a strong references to *dict*, to *keys* and to dictionary values
   (``dict[key]`` for all keys).


.. class:: GuardFunc(func)``

   Watch for ``func.__code__``.

   Keep a strong references to *func* and to ``func.__code__``.


Guard helper functions
----------------------

.. function:: GuardGlobals(names)

   Create ``GuardDict(globals), names)``.


.. function:: GuardTypeDict(type, attrs)

   Create ``GuardDict(type.__dict__, attrs)`` but access the real type
   dictionary, not ``type.__dict`` which is a read-only proxy.


Installation
============

A Python 3.6 patched with PEP 510 patch is required.

Type::

    pip install fat

Manual installation::

    python3.6 setup.py install


Run tests
=========

Type::

    ./runtests.sh


Changelog
=========

* 2016-01-13: First public release.
