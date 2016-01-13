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

.. warning::
   The API is not stable yet.


fat module API
==============

Functions:

* replace_consts(code, mapping): create a new code object and replacing
  constants with a mapping:
  ``new_consts = tuple(mapping.get(const, const) for const in consts)``
* specialize(func, code, guards): specialize the *func* function, add a
  specialize code with guards.  *code* must be a callable or code object,
  *guards* must be a non-empty sequence of guards.
* get_specialized(func): get the list of specialized codes with guards as
  (code, guards) tuples.

Guards:

* GuardArgType(arg_index, arg_types): check the type of the nth argument,
  arg_types must be a sequence of types
* GuardBuiltins(dict, names): watch for builtins.__dict__[name] for all names
* GuardDict(dict, keys): watch for dict[key] for all keys
* GuardFunc(func): watch for func.__code__
* GuardGlobals(names): watch for globals()[name] for all keys
* GuardTypeDict(type, attrs): watch for type.__dict__[attr] for all attrs

Note: GuardGlobals and GuardTypeDict are not types, but helper functions.

``fat.__version__`` is the version string.


Installation
============

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
