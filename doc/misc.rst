++++
Misc
++++

Implementation
==============

Steps and stages
----------------

The optimizer is splitted into multiple steps. Each optimization has its own
step: fatoptimizer.const_fold.ConstantFolding implements for example constant
folding.

The function optimizer is splitted into two stages:

* stage 1: run steps which don't require function specialization
* stage 2: run steps which can add guard and specialize the function

Main classes:

* ModuleOptimizer: Optimizer for ast.Module nodes. It starts by looking for
  :ref:`__fatoptimizer__ configuration <config>`.
* FunctionOptimizer: Optimizer for ast.FunctionDef nodes. It starts by running
  FunctionOptimizerStage1.
* Optimizer: Optimizer for other AST nodes.

Steps used by ModuleOptimizer, Optimizer and FunctionOptimizerStage1:

* NamespaceStep: populate a Namespace object which tracks the local variables,
  used by ConstantPropagation
* ReplaceBuiltinConstant: replace builtin optimization
* ConstantPropagation: constant propagation optimization
* ConstantFolding: constant folding optimization
* RemoveDeadCode: dead code elimitation optimization

Steps used by FunctionOptimizer:

* NamespaceStep: populate a Namespace object which tracks the local variables
* UnrollStep: loop unrolling optimization
* CallPureBuiltin: call builtin optimization
* CopyBuiltinToConstantStep: copy builtins to constants optimization

Some optimizations produce a new AST tree which must be optimized again. For
example, loop unrolling produces new nodes like "i = 0" and duplicates the loop
body which uses "i". We need to rerun the optimizer on this new AST tree to run
optimizations like constant propagation or constant folding.


Possible optimizations
======================

Short term:

* Function func2() calls func1() if func1() is pure: inline func1()
  into func2()
* Call builtin pure functions during compilation. Example: replace len("abc")
  with 3 or range(3) with (0, 1, 2).
* Constant folding: replace a variable with its value. We may do that for
  optimal parameters with default value if these parameters are not set.
  Example: replace app.DEBUG with False.

Using types:

* Detect the exact type of parameters and function local variables
* Specialized code relying on the types. For example, move invariant out of
  loops (ex: obj.append for list).
* x + 0 gives a TypeError for str, but can be replaced with x for int and
  float. Same optimization for x*0.
* See astoptimizer for more ideas.

Longer term:

* Compile to machine code using Cython, Numba, PyPy, etc. Maybe only for
  numeric types at the beginning? Release the GIL if possible, but check
  "sometimes" if we got UNIX signals.


Pure functions
==============

A "pure" function is a function with no side effect.

Example of pure operators:

* x+y, x-y, x*y, x/y, x//y, x**y for types int, float, complex, bytes, str,
  and also tuple and list for x+y

Example of instructions with side effect:

* "global var"

Example of pure function::

    def mysum(x, y):
        return x + y

Example of function with side effect::

    global _last_sum

    def mysum(x, y):
        global _last_sum
        s = x + y
        _last_sum = s
        return s


Limitations and Python semantic
===============================

FAT Python bets that the Python code is not modified when modules are loaded,
but only later, when functions and classes are executed. If this assumption is
wrong, FAT Python changes the semantics of Python.

.. _semantics:

Python semantics
----------------

It is very hard, to not say impossible, to implementation and keep the exact
behaviour of regular CPython. CPython implementation is used as the Python
"standard". Since CPython is the most popular implementation, a Python
implementation must do its best to mimic CPython behaviour. We will call it the
Python semantics.

FAT Python should not change the Python semantics with the default
configuration.  Optimizations modifting the Python semantics must be disabled
by default: opt-in options.

As written above, it's really hard to mimic exactly CPython behaviour. For
example, in CPython, it's technically possible to modify local variables of a
function from anywhere, a function can modify its caller, or a thread B can
modify a thread A (just for fun). See `Everything in Python is mutable
<https://faster-cpython.readthedocs.org/mutable.html>`_ for more information.
It's also hard to support all introspections features like ``locals()``
(``vars()``, ``dir()``), ``globals()`` and
``sys._getframe()``.

Builtin functions replaced in the middle of a function
------------------------------------------------------

FAT Python uses :ref:`guards <guard>` to disable specialized function when
assumptions made to optimize the function are no more true. The problem is that
guard are only called at the entry of a function. For example, if a specialized
function ensures that the builtin function ``chr()`` was not modified, but
``chr()`` is modified during the call of the function, the specialized function
will continue to call the old ``chr()`` function.

The :ref:`copy builtin functions to constants <copy-builtin-to-constant>`
optimization changes the Python semantics. If a builtin function is replaced
while the specialized function is optimized, the specialized function will
continue to use the old builtin function. For this reason, the optimization
is disabled by default.

Example::

    def func(arg):
        x = chr(arg)

        with unittest.mock.patch('builtins.chr', result='mock'):
            y = chr(arg)

        return (x == y)

If the :ref:`copy builtin functions to constants
<copy-builtin-to-constant>` optimization is used on this function, the
specialized function returns ``True``, whereas the original function returns
``False``.

It is possible to work around this limitation by adding the following
:ref:`configuration <config>` at the top of the file::

    __fatoptimizer__ = {'copy_builtin_to_constant': False}

But the following use cases works as expected in FAT mode::

    import unittest.mock

    def func():
        return chr(65)

    def test():
        print(func())
        with unittest.mock.patch('builtins.chr', return_value="mock"):
            print(func())

Output::

    A
    mock

The ``test()`` function doesn't use the builtin ``chr()`` function.
The ``func()`` function checks its guard on the builtin ``chr()`` function only
when it's called, so it doesn't use the specialized function when ``chr()``
is mocked.


Guards on builtin functions
---------------------------

When a function is specialized, the specialization is ignored if a builtin
function was replaced after the end of the Python initialization. Typically,
the end of the Python initialization occurs just after the execution of the
``site`` module. It means that if a builtin is replaced during Python
initialization, a function will be specialized even if the builtin is not the
expected builtin function.

Example::

    import builtins

    builtins.chr = lambda: mock

    def func():
        return len("abc")

In this example, the ``func()`` is optimized, but the function is *not*
specialize. The internal call to ``func.specialize()`` is ignored because the
``chr()`` function was replaced after the end of the Python initialization.


Guards on type dictionary and global namespace
-----------------------------------------------

For other guards on dictionaries (type dictionary, global namespace), the guard
uses the current value of the mapping. It doesn't check if the dictionary value
was "modified".


Tracing and profiling
---------------------

Tracing and profiling works in FAT mode, but the exact control flow and traces
are different in regular and FAT mode. For example, :ref:`loop unrolling
<loop-unroll>` removes the call to ``range(n)``.

See ``sys.settrace()`` and ``sys.setprofiling()`` functions.

Expected limitations
--------------------

Inlining makes debugging more complex:

* sys.getframe()
* locals()
* pdb
* etc.
* don't work as expected anymore

Bugs, shit happens:

* Missing guard: specialized function is called even if the "environment"
  was modified

FAT python! Memory vs CPU, fight!

* Memory footprint: loading two versions of a function is memory uses more
  memory
* Disk usage: .pyc will be more larger

Possible worse performance:

* guards adds an overhead higher than the optimization of the specialized code
* specialized code may be slower than the original bytecode


Changelog
=========

* 2016-01-18: Version 0.1

  * Add ``fatoptimizer.pretty_dump()``
  * Add Sphinx documentation: ``doc/`` directory
  * Add benchmark scripts: ``benchmarks/`` directory
  * Update ``fatoptimizer._register()`` for the new version of the PEP 511
    (``sys.set_code_transformers()``)

* 2016-01-14: First public release, version 0.0.


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
