.. _optim:

+++++++++++++
Optimizations
+++++++++++++

Implementated optimizations:

* :ref:`Call pure builtins <call-pure>`
* :ref:`Loop unrolling <loop-unroll>`
* :ref:`Constant propagation <const-prop>`
* :ref:`Constant folding <const-fold>`
* :ref:`Replace builtin constants <replace-builtin-constant>`
* :ref:`Dead code elimination <dead-code>`
* :ref:`Copy builtin functions to constants <copy-builtin-to-constant>`
* :ref:`Simplify iterable <simplify-iterable>`


.. _call-pure:

Call pure builtins
------------------

Call pure builtin functions at compilation: replace the call with the result in
the specialized bytecode, add guards on the called builtin functions.

The optimization is disabled when the builtin function is modified or if
a variable with the same name is added to the global namespace of the function.

The optimization on the builtin ``NAME`` requires two guards:

* ``NAME`` key in builtin namespace
* ``NAME`` key in global namespace

Example:

+------------------------+---------------+
| Original               | Specialized   |
+========================+===============+
| ::                     | ::            |
|                        |               |
|  def func():           |  def func():  |
|      return len("abc") |      return 3 |
+------------------------+---------------+


.. _loop-unroll:

Loop unrolling
--------------

``for i in range(3): ...`` and ``for i in (1, 2, 3): ...`` are unrolled.
By default, only loops with 16 iterations or less are optimized.

.. note::
   If ``break`` and/or ``continue`` instructions are used in the loop body,
   the loop is not unrolled.

:ref:`Configuration option <config>`: ``unroll_loops``.


tuple example
^^^^^^^^^^^^^

Example with a tuple.

+---------------------------+--------------------------+
| Original                  | Loop unrolled            |
+===========================+==========================+
| ::                        | ::                       |
|                           |                          |
|  def func():              |  def func():             |
|      for i in ("a", "b"): |      i = "a"             |
|          print(i)         |      print(i)            |
|                           |                          |
|                           |      i = "b"             |
|                           |      print(i)            |
+---------------------------+--------------------------+

No guard is required. The function has no specialized bytecode, the
optimization is done directly on the function.

Original bytecode::

    .     0 SETUP_LOOP              14 (to 17)
          3 LOAD_CONST               3 (('hello', 'world'))
          6 GET_ITER

    >>    7 FOR_ITER                 6 (to 16)
         10 STORE_FAST               0 (i)

         13 JUMP_ABSOLUTE            7
    >>   16 POP_BLOCK

    >>   17 LOAD_CONST               0 (None)
         20 RETURN_VALUE

FAT Python bytecode::

    LOAD_CONST   1 ("hello")
    STORE_FAST   0 (i)

    LOAD_CONST   2 ("world")
    STORE_FAST   0 (i)

    LOAD_CONST   0 (None)
    RETURN_VALUE


range example
^^^^^^^^^^^^^

Example of a loop using ``range()``.

+--------------------------+--------------------------+
| Original                 | Loop unrolled            |
+==========================+==========================+
| ::                       | ::                       |
|                          |                          |
|  def func():             |  def func():             |
|      for i in range(2):  |      i = 0               |
|          print(i)        |      print(i)            |
|                          |                          |
|                          |      i = 1               |
|                          |      print(i)            |
+--------------------------+--------------------------+

The specialized bytecode requires two :ref:`guards <guard>`:

* ``range`` builtin variable
* ``range`` global variable

Combined with :ref:`constant propagation <const-prop>`, the code becomes
even more interesting::

    def func():
        i = 0
        print(0)

        i = 1
        print(1)


.. _const-prop:

Constant propagation
--------------------

Propagate constant values of variables.

+----------------+----------------------+
| Original       | Constant propagation |
+================+======================+
| ::             | ::                   |
|                |                      |
|   def func()   |   def func()         |
|       x = 1    |       x = 1          |
|       y = x    |       y = 1          |
|       return y |       return 1       |
+----------------+----------------------+

:ref:`Configuration option <config>`: ``constant_propagation``.


.. _const-fold:

Constant folding
----------------

Compute simple operations at the compilation:

* arithmetic operations:

  - ``a+b``, ``a-b``, ``a*b``, ``a/b``: int, float, complex
  - ``+x``, ``-x``, ``~x``: int, float, complex
  - ``a//b``, ``a%b``, ``a**b``: int, float
  - ``a<<b``, ``a>>b``, ``a&b``, ``a|b``, ``a^b``: int

* comparison, tests:

  - ``a < b``, ``a <= b``, ``a >= b``, ``a > b``
  - ``a == b``, ``a != b``: don't optimize bytes == str
  - ``obj in seq``, ``obj not in seq``: for bytes, str, tuple ``seq``
  - ``not x``: int

* str: ``str + str``, ``str * int``
* bytes: ``bytes + bytes``, ``bytes * int``
* tuple: ``tuple + tuple``, ``tuple * int``
* str, bytes, tuple, list: ``obj[index]``, ``obj[a:b:c]``
* dict: ``obj[index]``
* replace ``x in list`` with ``x in tuple`` if list only contains constants
* replace ``x in set`` with ``x in frozenset`` if set only contains constants
* simplify tests:

===================  ===========================
Code                 Constant folding
===================  ===========================
not(x is y)          x is not y
not(x is not y)      x is y
not(obj in seq)      obj not in seq
not(obj not in seq)  obj in seq
===================  ===========================

Note: ``not (x == y)`` is not replaced with ``x != y`` because ``not
x.__eq__(y)`` can be different than ``x.__ne__(y)`` for deliberate reason Same
rationale for not replacing ``not(x < y)`` with ``x >= y``.  For example,
``math.nan`` overrides comparison operators to always return ``False``.

Examples of optimizations:

===================  ===========================
Code                 Constant folding
===================  ===========================
-(5)                 -5
+5                   5
x in [1, 2, 3]       x in (1, 2, 3)
x in {1, 2, 3}       x in frozenset({1, 2, 3})
'Python' * 2         'PythonPython'
3 * (5,)             (5, 5, 5)
'python2.7'[:-2]     'python2'
'P' in 'Python'      True
9 not in (1, 2, 3)   True
[5, 9, 20][1]        9
===================  ===========================

:ref:`Configuration option <config>`: ``constant_folding``.


.. _replace-builtin-constant:

Replace builtin constants
-------------------------

Replace ``__debug__`` constant with its value.

:ref:`Configuration option <config>`: ``replace_builtin_constant``.


.. _dead-code:

Dead code elimination
---------------------

Remove the dead code.

Examples:

+--------------------------+--------------------------+
| Code                     | Dead code removed        |
+==========================+==========================+
| ::                       | ::                       |
|                          |                          |
|  if test:                |  if not test:            |
|      pass                |      else_block          |
|  else:                   |                          |
|      else_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  if 1:                   |  body_block              |
|      body_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  if 0:                   |  pass                    |
|      body_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  if False:               |  else_block              |
|      body_block          |                          |
|  else:                   |                          |
|      else_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  while 0:                |  pass                    |
|      body_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  while 0:                |  else_block              |
|      body_block          |                          |
|  else:                   |                          |
|      else_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  ...                     |  ...                     |
|  return ...              |  return ...              |
|  dead_code_block         |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  ...                     |  ...                     |
|  raise ...               |  raise ...               |
|  dead_code_block         |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  try:                    |  pass                    |
|      pass                |                          |
|  except ...:             |                          |
|      ...                 |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  try:                    |  else_block              |
|      pass                |                          |
|  except ...:             |                          |
|      ...                 |                          |
|  else:                   |                          |
|      else_block          |                          |
+--------------------------+--------------------------+
| ::                       | ::                       |
|                          |                          |
|  try:                    |  try:                    |
|      pass                |     else_block           |
|  except ...:             |  finally:                |
|      ...                 |     final_block          |
|  else:                   |                          |
|      else_block          |                          |
|  finally:                |                          |
|      final_block         |                          |
+--------------------------+--------------------------+

.. note::
   If a code block contains ``continue``, ``global``, ``nonlocal``, ``yield``
   or ``yield from``, it is not removed.

:ref:`Configuration option <config>`: ``remove_dead_code``.


.. _copy-builtin-to-constant:

Copy builtin functions to constants
-----------------------------------

Opt-in optimization (disabled by default) to copy builtin functions to
constants.

Example with a function simple::

    def log(message):
        print(message)

+--------------------------------------------------+----------------------------------------------------+
| Bytecode                                         | Specialized bytecode                               |
+==================================================+====================================================+
| ::                                               | ::                                                 |
|                                                  |                                                    |
|   LOAD_GLOBAL   0 (print)                        |   LOAD_CONST      1 (<built-in function print>)    |
|   LOAD_FAST     0 (message)                      |   LOAD_FAST       0 (message)                      |
|   CALL_FUNCTION 1 (1 positional, 0 keyword pair) |   CALL_FUNCTION   1 (1 positional, 0 keyword pair) |
|   POP_TOP                                        |   POP_TOP                                          |
|   LOAD_CONST    0 (None)                         |   LOAD_CONST      0 (None)                         |
|   RETURN_VALUE                                   |   RETURN_VALUE                                     |
+--------------------------------------------------+----------------------------------------------------+

The first ``LOAD_GLOBAL`` instruction is replaced with ``LOAD_CONST``.
``LOAD_GLOBAL`` requires to lookup in the global namespace and then in the
builtin namespaces, two dictionary lookups. ``LOAD_CONST`` gets the value from
a C array, O(1) lookup.

The specialized bytecode requires two :ref:`guards <guard>`:

* ``print`` builtin variable
* ``print`` global variable

The ``print()`` function is injected in the constants with the
``func.patch_constants()`` method.

The optimization on the builtin ``NAME`` requires two guards:

* ``NAME`` key in builtin namespace
* ``NAME`` key in global namespace

This optimization is disabled by default because it changes the :ref:`Python
semantics <semantics>`: if the copied builtin function is replaced
in the middle of the function, the specialized bytecode still uses the old
builtin function. To use the optimization on a project, you may have to add the
following :ref:`configuration <config>` at the top of the file::

    __astoptimizer__ = {'copy_builtin_to_constant': False}

:ref:`Configuration option <config>`: ``copy_builtin_to_constant``.


See also:

* `codetransformer <https://pypi.python.org/pypi/codetransformer>`_:
  ``@asconstants(len=len)`` decorator replaces lookups to the ``len`` name
  with the builtin ``len()`` function
* Thread on python-ideas mailing list: `Specifying constants for functions
  <https://mail.python.org/pipermail/python-ideas/2015-October/037028.html>`_
  by Serhiy Storchaka, propose to add ``const len=len`` (or alternatives)
  to declare a constant (and indirectly copy a builtin functions to constants)


.. _simplify-iterable:

Simplify iterable
-----------------

Try to replace literals built at runtime with constants. Replace also
range(start, stop, step) with a tuple if the range fits in the
:ref:`configuration <config>`.

When ``range(n)`` is replaced, two guards are required on ``range`` in builtin
and global namespaces and the function is specialized.

This optimization helps :ref:`loop unrolling <loop-unroll>`.

Examples:

===========================   ===========================
Code                          Simplified iterable
===========================   ===========================
``for x in range(3): ...``    ``for x in (0, 1, 2): ...``
``for x in {}: ...``          ``for x in (): ...``
``for x in [4, 5. 6]: ...``   ``for x in (4, 5, 6): ...``
===========================   ===========================

:ref:`Configuration option <config>`: ``simplify_iterable``.


Comparison with the peephole optimizer
--------------------------------------

The `CPython peephole optimizer
<https://faster-cpython.readthedocs.org/bytecode.html#cpython-peephole-optimizer>`_
only implements a few optimizations: :ref:`constant folding <const-fold>` and
:ref:`dead code elimination <dead-code>`. FAT Python implements more
:ref:`optimizations <optim>`.

The peephole optimizer doesn't support :ref:`constant propagation
<const-prop>`. Example::

    def f():
        x = 333
        return x

+----------------------------------+------------------------------------+
| Regular bytecode                 | FAT mode bytecode                  |
+==================================+====================================+
| ::                               | ::                                 |
|                                  |                                    |
|   LOAD_CONST               1 (1) |   LOAD_CONST               1 (333) |
|   STORE_FAST               0 (x) |   STORE_FAST               0 (x)   |
|   LOAD_FAST                0 (x) |   LOAD_CONST               1 (333) |
|   RETURN_VALUE                   |   RETURN_VALUE                     |
|                                  |                                    |
|                                  |                                    |
+----------------------------------+------------------------------------+

The :ref:`constant folding optimization <const-fold>` of the peephole optimizer
keeps original constants. For example, ``"x" + "y"`` is replaced with ``"xy"``
but ``"x"`` and ``"y"`` are kept. Example::

    def f():
        return "x" + "y"

+-----------------------------+------------------------+
| Regular constants           | FAT mode constants     |
+=============================+========================+
| ``(None, 'x', 'y', 'xy')``: | ``(None, 'xy')``:      |
| 4 constants                 | 2 constants            |
+-----------------------------+------------------------+

The peephole optimizer has a similar limitation even when building tuple
constants. The compiler produces AST nodes of type ``ast.Tuple``, the tuple
items are kept in code constants.


