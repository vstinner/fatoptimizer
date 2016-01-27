.. _fat:

++++++++++
fat module
++++++++++

The ``fat`` module is a Python extension module (written in C) implementing
fast guards. The :ref:`fatoptimizer optimizer <fatoptimizer>` uses ``fat``
guards to specialize functions. ``fat`` guards are used to verify assumptions
used to specialize the code. If an assumption is no more true, the specialized
code is not used.

The ``fat`` module is required to run code optimized by ``fatoptimizer`` if at
least one function is specialized.

* `fat project at GitHub
  <https://github.com/haypo/fat>`_
* `fat project at the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/fat>`_

The ``fat`` module requires a Python 3.6 patched with PEP 510 patch.


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


.. _guard:

Guard types
-----------

.. class:: GuardArgType(arg_index, arg_types)

    Check the type of the nth argument, *arg_types* must be a sequence of
    types.

    Attributes:

    .. attribute:: arg_index

       Index of the argument (``int``). Read-only attribute.

    .. attribute:: arg_types

       List of accepted types for the argument: list of types.
       Read-only property.

    Keep a strong reference to *arg_types* types.


.. class:: GuardBuiltins(names)

   Subtype of :class:`GuardDict`.

   Watch for:

   * globals of the current frame (``frame.f_globals``)
   * ``globals()[name]`` for all *names*.
   * builtins of the current frame (``frame.f_builtins``)
   * ``builtins.__dict__[name]`` for all *names*

   The guard initialization fails if ``builtins.__dict__[name]`` was replaced
   after ``fat`` was imported, or if ``globals()[name]`` already exists.

   Attributes:

   .. attribute:: guard_globals

      The :class:`GuardGlobals` used to watch for the global variables.
      Read-only attribute.

   Keep a strong references to the builtin namespace (``builtins.__dict__``
   dictionary), to the global namespace (``globals()`` dictionary), to *names*
   and to existing builtin symbols called *names* (``builtins.__dict__[name]``
   for all *names*).


.. class:: GuardDict(dict, keys)

   Watch for ``dict[key]`` for all *keys*.

   Attributes:

   .. attribute:: dict

      Watched dictionary (``dict``). Read-only attribute.

   .. attribute:: keys

      List of watched dictionary keys: list of ``str``. Read-only property.

   Keep a strong references to *dict*, to *keys* and to existing dictionary
   values (``dict[key]`` for all keys).


.. class:: GuardFunc(func)

   Watch for the code object (``func.__code__``) of a Python function.

   Attributes:

   .. attribute:: code

      Watched code object. Read-only attribute.

   .. attribute:: func

      Watched function. Read-only attribute.

   Keep a strong references to *func* and to ``func.__code__``.


.. class:: GuardGlobals(names)

   Subtype of :class:`GuardDict`.

   Watch for:

   * globals of the current frame (``frame.f_globals``)
   * ``globals()[name]`` for all *names*.

   Keep a strong references to the global namespace (``globals()`` dictionary),
   to *names* and to existing global variables called *names*
   (``globals()[name]`` for all *names*).


Guard helper functions
----------------------

.. function:: guard_type_dict(type, attrs)

   Create ``GuardDict(type.__dict__, attrs)`` but access the real type
   dictionary, not ``type.__dict`` which is a read-only proxy.

   Watch for ``type.attr`` (``type.__dict__[attr]``) for all *attrs*.


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

* 2016-01-22: Version 0.2

 * :class:`GuardBuiltins` now also checks the builtins and the globals of the
   current frame. In practice, the guard fails if it creates in a namespace
   and checked in a different namespace.
 * Add a new :class:`GuardGlobals` type which replaces the previous
   :func:`guard_globals()` helper function (removed). The guard check checks if
   the frame globals changed or not.
 * Guards are now tracked by the garbage collector to handle correctly a
   reference cycle with GuardGlobals which keeps a reference to the module
   namespace (``globals()``).
 * Fix type of dictionary version for 32-bit platforms: ``PY_UINT64_T``, not
   ``size_t``.
 * Fix :class:`GuardFunc` traverse method: visit also the ``code`` attribute.
 * Implement a traverse method to :class:`GuardBuiltins` to detect correctly
   reference cycles.

* 2016-01-18: Version 0.1

  * GuardBuiltins check remembers if guard init failed
  * Rename :class:`GuardGlobals` to :func:`guard_globals`
  * Rename :class:`GuardTypeDict` to :func:`guard_dict_type`

* 2016-01-13: First public release, version 0.0.
