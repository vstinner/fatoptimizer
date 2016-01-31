.. _todo:

++++++++++++++++++++++
fatoptimizer TODO list
++++++++++++++++++++++


Easy issues, for new contributors
=================================

* Complete fatoptimizer/methods.py to suppore more pure methods
* Complete fatoptimizer/builtins.py to suppore more pure builtin functions


Goal
====

To get visible performance gain, the following optimizations must be
implemented:

* Function inlining
* Detect and call pure functions
* Elimination of unused variables (set but never read): the constant
  propagation and loop unrolling create many of them. For example,
  replace "def f(): x=1; return x" with "def f(): return 1"
* Copy constant global variable to function globals
* Specialization for argument types: move invariant out of loops.
  Ex: create a bounded method "obj_append = obj.append" out of the loop.

Even if many optimizations can be implemented with a static optimizers, it's
still not a JIT compiler.  A JIT compiler is required to implement even more
optimizations.


Known Bugs
==========

* ``import *`` is ignored
* Usage of locals() or vars() must disable optimization. Maybe only when the
  optimizer produces new variables?


Search ideas of new optimizations
=================================

* `python.org wiki: PythonSpeed/PerformanceTips
  <https://wiki.python.org/moin/PythonSpeed/PerformanceTips>`_
* `Open issues of type Performance
  <http://bugs.python.org/issue?%40search_text=&ignore=file%3Acontent&title=&%40columns=title&id=&%40columns=id&stage=&creation=&creator=&activity=&%40columns=activity&%40sort=activity&actor=&nosy=&type=7&components=&versions=&dependencies=&assignee=&keywords=&priority=&status=1&%40columns=status&resolution=&nosy_count=&message_count=&%40group=&%40pagesize=50&%40startwith=0&%40sortdir=on&%40queryname=&%40old-queryname=&%40action=search>`_
* `Closed issues of type Performance
  <http://bugs.python.org/issue?%40search_text=&ignore=file%3Acontent&title=&%40columns=title&id=&%40columns=id&stage=&creation=&creator=&activity=&%40columns=activity&%40sort=activity&actor=&nosy=&type=7&components=&versions=&dependencies=&assignee=&keywords=&priority=&status=2&%40columns=status&resolution=&nosy_count=&message_count=&%40group=&%40pagesize=50&%40startwith=0&%40sortdir=on&%40queryname=&%40old-queryname=&%40action=search>`_
* `Unladen Swallow ProjectPlan
  <http://code.google.com/p/unladen-swallow/wiki/ProjectPlan>`_
* Ideas from PyPy, Pyston, Numba, etc.


More optimizations
==================

MUST HAVE
---------

More complex to implement (without breaking Python semantics).

* Remove useless temporary variables. Example:

  Code::

      def func():
         res = 1
         return res

  Constant propagation::

      def func():
         res = 1
         return 1

  Remove *res* local variable::

      def func():
         return 1

  Maybe only for simple types (int, str). It changes object lifetime:
  https://bugs.python.org/issue2181#msg63090

* Function inlining: see `Issue #10399 <http://bugs.python.org/issue10399>`_,
  AST Optimization: inlining of function calls

* Inline calls to all functions, short or not? Need guards on these functions
  and the global namespace. Example: posixpath._get_sep().

* Call pure functions of math, struct and string modules.
  Example: replace math.log(32) / math.log(2) with 5.0.


Pure functions
--------------

* Compute if a function is pure. See pythran.analysis.PureFunctions of pythran
  project, depend on ArgumentEffects and GlobalEffects analysys


Random
------

Easy to implement.

* [Python-ideas] (FAT Python) Convert keyword arguments to positional?
  https://mail.python.org/pipermail/python-ideas/2016-January/037874.html

* Loop unrolling: support multiple targets::

    for x, y in ((1, 2), (3, 4)):
        print(x, y)

* Tests:

  - ``if a: if b: code`` => ``if a and b: code``

* Optimize ``str%args`` and ``bytes%args``

* Constant folding:

  * replace get_constant() with get_literal()?

    - list + list
    - frozenset | frozenset
    - set | set

  * 2.0j ** 3.0
  * 1 < 2 < 3
  * ``if x and True: pass`` => ``if x: pass``
    http://bugs.python.org/issue7682
  * replace '(a and b) and c' (2 op) with 'a and b and c' (1 op),
    same for "or" operator

* Specialize also AsyncFunctionDef (run stage 2, not only stage 1)


Can be done later
-----------------

Unknown speedup, easy to medium to implement.

* Replace dict(...) with {...} (dict literal):
  https://doughellmann.com/blog/2012/11/12/the-performance-impact-of-using-dict-instead-of-in-cpython-2-7-2/

* Use SimplifyIterable on dict/frozenset argument

* print(): convert arguments to strings

* Remove dead code: remove "pass; pass"

* Simplify iteratable:

  - for x in set("abc"): ... => for x in frozenset("abc"): ...
    Need a guard on set builtin

  - for x in "abc": ... => for x in ("a", "b", "c"): ...
    Is it faster? Does it use less memory?

  - at least, loop unrolling must work on "for x in 'abc': ..."


Can be done later and are complex
---------------------------------

Unknown speedup, complex to implement.

* Remove "if 0: yield" but tag FunctionDef as a generator?

* Implement CALL_METHOD bytecode, but execute the following code correctly
  (output must be 1, 2 and not 1, 1)::

      class C(object):
          def foo(self):
              return 1
      c = c()
      print c.foo()
      c.foo = lambda: 2
      print c.foo()

  Need a guard on C.foo?

  See https://bugs.python.org/issue6033#msg95707

  Is it really possible? FAT Python doesn't support guards on the instance
  dict, it's more designed to use guards on the type dict.

* Optimize 'lambda: chr(65)'. Lambda are functions, but defined as expressions.
  It's not easy to inject the func.specialize() call,
  func.__code__.replace_consts() call, etc. Maybe only optimize in some
  specific cases?

  Specialization of nested function was disabled because the cost to
  specialize the function can be higher than the speedup if the function
  is called once and then destroyed.

* Enable copy builtins to constants when we know that builtins and globals are
  not modified. Need to ensure that the function is pure and only calls pure
  functions.

* Move invariant out of loops using guards on argument types:

  - Merge duplicate LOAD_ATTR, when we can make sure that the attribute will
    not be modified
  - list.append: only for list type

* Loop unrolling:

  - support break and continue
  - support raise used outside try/except

* Constant propagation, copy accross namespaces:

  - list-comprehension has its own separated namespace::

        n = 100
        seq = [randrange(n) for i in range(n)]

  - copy globals to locals: need a guard on globals

* Convert naive loop to list/dict/set comprehension.
  Replace "x=[]; for item in data: x.append(item.upper())"
  with "x=[item.upper() for item in data]". Same for x=set() and x={}.

* Call more builtin functions:

  - all(), any()
  - enumerate(iterable), zip()
  - format()
  - filter(pred, iterable), map(pred, iterable), reversed()

* operator module:

  - need to add an import, need to ensure that operator name is not used
  - lambda x: x[1] => operator.itemgetter(1)
  - lambda x: x.a => operator.attrgetter('a')
  - lambda x: x.f('a', b=1) => operator.methodcaller('f', 'a', b=1)

* map, itertools.map, filter:

  - [f(x) for x in a] => map(f, a) / list(map(f, a))
  - (f(x) for x in a) => itertools.map(f, a) / map(f, a) ? scope ?
  - (x for x in a if f(x)) => filter(f, a)
  - (x for x in a if not f(x)) => __builtin_filternot__(f, a) ?
  - (2 * x for x in a) => map((2).__mul__, a)
  - (x for x in a if x in 'abc') => filter('abc'.__contains__, a)



Profiling
=========

* implement code to detect the exact type of function parameters and function
  locals and save it into an annotation file
* implement profiling directed optimization: benchmark guards at runtime
  to decide if it's worth to use a specialized function. Measure maybe also
  the memory footprint using tracemalloc?
* implement basic stategy to decide if specialized function must be emitted
  or not using raw estimation, like the size of the bytecode in bytes



Later
=====

* efficient optimizations on objects, not only simple functions
* handle python modules and python imports

  - checksum of the .py content?
  - how to handle C extensions? checksum of the .so file?
  - how to handle .pyc files?

* find an efficient way to specialize nested functions
* configuration to manually help the optimizer:

  - give a whitelist of "constants": app.DEBUG, app.enum.BLUE, ...
  - type hint with strict types: x is Python int in range [3; 10]
  - expect platform values to be constant: sys.version_info, sys.maxunicode,
    os.name, sys.platform, os.linesep, etc.
  - declare pure functions
  - see fatoptimizer for more ideas

* Restrict the number of guards, number of specialized bytecode, number
  of arg_type types with fatoptimizer.Config
* fatoptimizer.VariableVisitor: support complex assignments like
  'type(mock)._mock_check_sig = checksig'
* Support specialized CFunction_Type, not only specialized bytecode?
* Add an opt-in option to skip some guards if the user knows that the
  application will never modify function __code__, override builtin methods,
  modify a constant, etc.
* Optimize real objects, not only simple functions. For example, inline a
  method.
* Function parameter: support more complex guard to complex types like
  list of integers?
* handle default argument values for argument type guards?
* Support locals()[key], vars()[key], globals()[key]?
* Support decorators
* Copy super() builtin to constants doesn't work. Calling the builtin super()
  function creates a free variable, whereas calling the constant doesn't
  create a free variable.
* Tail-call recursion?

    def factorial(n):
        if n > 1:
            return n * factorial(n-1)
        else:
            return 1


Support decorator
=================

weakref.py::

    @property
    def atexit(self):
        """Whether finalizer should be called at exit"""
        info = self._registry.get(self)
        return bool(info) and info.atexit

    @atexit.setter
    def atexit(self, value):
        info = self._registry.get(self)
        if info:
            info.atexit = bool(value)

It's not possible to replace it with::

    def atexit(self):
        """Whether finalizer should be called at exit"""
        info = self._registry.get(self)
        return bool(info) and info.atexit
    atexit = property(atexit)

    def atexit(self, value):
        info = self._registry.get(self)
        if info:
            info.atexit = bool(value)
    atexit = atexit.setter(atexit)

The last line 'atexit = atexit.setter(atexit)' because 'atexit' is now
the second function, not more the first decorated function (the property).

Define the second atexit under a different name? No! It changes the code name,
which is wrong.

Maybe we can replace it with::

    def atexit(self):
        """Whether finalizer should be called at exit"""
        info = self._registry.get(self)
        return bool(info) and info.atexit
    atexit = property(atexit)

    _old_atexit = atexit
    def atexit(self, value):
        info = self._registry.get(self)
        if info:
            info.atexit = bool(value)
    atexit = _old_atexit.setter(atexit)

But for this, we need to track the namespace during the optimization. The
VariableVisitor in run *before* the optimizer, it doesn't track the namespace
at the same time.


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
