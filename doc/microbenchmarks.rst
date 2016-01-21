.. _microbench:

+++++++++++++++
Microbenchmarks
+++++++++++++++

REMINDER: on a microbenchmark, even a significant speedup doesn't mean that you
will get a significant speedup on your application.

The ``benchmarks/`` directory contains microbenchmarks used to test ``fat`` and
``fatoptimizer`` performances.


Function inlining and specialization using the parameter type
=============================================================

Optimize::

    def _get_sep(path):
        if isinstance(path, bytes):
            return b'/'
        else:
            return '/'

    def isabs(s):
        """Test whether a path is absolute"""
        sep = _get_sep(s)
        return s.startswith(sep)

to::

    def isabs(s):
        return s.startswith('/')

but only if *s* parameter is a string.

2016-01-21::

    original isabs() bytecode: 488 ns
    _get_sep() inlined in isabs(): 268 ns (-220 ns, -45.0%, 1.8x faster :-))

2015-10-21::

    $ ./python -m timeit 'import posixpath; isabs = posixpath.isabs' 'isabs("/root")'
    1000000 loops, best of 3: 0.939 usec per loop
    $ ./python -F -m timeit 'import posixpath; isabs = posixpath.isabs' 'isabs("/root")'
    1000000 loops, best of 3: 0.755 usec per loop

Script: ``benchmarks/bench_posixpath.py``.


Move invariant out of loop (list.append)
========================================

Optimize::

    def func(obj, data):
        for item in data:
            obj.append(item)

to::

    def func(obj, data):
        append = obj.append
        for item in data:
            append(item)


2016-01-21::

    range(10 ** 0)
    - original bytecode: 297 ns
    - append=obj.append with guards: 310 ns (+13 ns, +4.4%, 1.0x slower :-()
    - append=obj.append: 306 ns (+9 ns, +3.1%, 1.0x slower :-()
    range(10 ** 1)
    - original bytecode: 972 ns
    - append=obj.append with guards: 703 ns (-268 ns, -27.6%, 1.4x faster :-))
    - append=obj.append: 701 ns (-271 ns, -27.9%, 1.4x faster :-))
    range(10 ** 3)
    - original bytecode: 72.2 us
    - append=obj.append with guards: 43.8 us (-28.4 us, -39.4%, 1.6x faster :-))
    - append=obj.append: 43.7 us (-28.6 us, -39.5%, 1.7x faster :-))
    range(10 ** 5)
    - original bytecode: 8131.5 us
    - append=obj.append with guards: 5289.5 us (-2842.0 us, -35.0%, 1.5x faster :-))
    - append=obj.append: 5294.2 us (-2837.4 us, -34.9%, 1.5x faster :-))

2015-10-21::

    $ ./python bench.py
    regular python: range(1)-> 502 ns
    regular python: range(10)-> 1.7 us
    regular python: range(10**3)-> 122.0 us
    regular python: range(10**5)-> 8.5 ms

    $ ./python -F bench.py
    fat python: range(1)-> 479 ns (-5%)
    fat python: range(10)-> 1.1 us (-35%)
    fat python: range(10**3)-> 65.2 us (-47%)
    fat python: range(10**5)-> 5.3 ms (-38%)

Script: ``benchmarks/bench_list_append.py``.


Call builtin
============

Optimize::

    def func():
        return len("abc")

to::

    def func():
        return 3

2015-01-21 (best timing of 5 runs):

===============================  ======
Test                             Perf
===============================  ======
Original bytecode (call len)     116 ns
return 3 with guard on builtins   90 ns
return 3                          79 ns
===============================  ======

GuardBuiltins has a cost of 11 ns.

Script: ``benchmarks/bench_len_abc.py``.


Copy builtin function to constant
=================================

Optimize::

    def func(obj):
        return len(obj)

to::

    def func(obj):
        return 'LEN'(obj)
    func.__code__ = fat.replace_consts(func.__code__, {'LEN': len})

2015-01-21 (best timing of 5 runs):

=================================  ======
Test                               Perf
=================================  ======
Original bytecode (LOAD_GLOBAL)    121 ns
LOAD_CONST with guard on builtins  116 ns
LOAD_CONST                         105 ns
=================================  ======

GuardBuiltins has a cost of 11 ns.

Script: ``benchmarks/bench_copy_builtin_to_cst.py``.


Copy global function to constant
================================

Optimize::

    mylen = len

    def func(obj):
        return len(obj)

to::

    mylen = len

    def func(obj):
        return 'MYLEN'(obj)
    func.__code__ = fat.replace_consts(func.__code__, {'MYLEN': len})

2015-01-21 (best timing of 5 runs):

=================================  ======
Test                               Perf
=================================  ======
Original bytecode (LOAD_GLOBAL)    115 ns
LOAD_CONST with guard on globals   112 ns
LOAD_CONST                         105 ns
=================================  ======

GuardGlobals has a cost of 7 ns.

Script: ``benchmarks/bench_copy_global_to_cst.py``.


Cost of guards
==============

Cost of GuardDict guard.

2016-01-21::

    no guard: 81 ns
    with 1000 guards on globals: 3749 ns
    cost of 1000 guards: 3667 ns (4503.4%)
    average cost of 1 guard: 4 ns (4.5%)

    no guard: 82 ns
    with 100 guards on globals: 419 ns
    cost of 100 guards: 338 ns (414.6%)
    average cost of 1 guard: 3 ns (4.1%)

    no guard: 81 ns
    with 10 guards on globals: 117 ns
    cost of 10 guards: 36 ns (43.9%)
    average cost of 1 guard: 4 ns (4.4%)

    no guard: 82 ns
    with 1 guards on globals: 87 ns
    cost of 1 guards: 5 ns (6.5%)
    average cost of 1 guard: 5 ns (6.5%)

2016-01-06::

    no guard: 431 ns
    with 1000 guards on globals: 7974 ns
    cost of 1000 guards: 7542 ns (1748.1%)
    average cost of 1 guard: 8 ns (1.7%)

    no guard: 429 ns
    with 100 guards on globals: 1197 ns
    cost of 100 guards: 768 ns (179.0%)
    average cost of 1 guard: 8 ns (1.8%)

    no guard: 426 ns
    with 10 guards on globals: 515 ns
    cost of 10 guards: 89 ns (20.8%)
    average cost of 1 guard: 9 ns (2.1%)

    no guard: 430 ns
    with 1 guards on globals: 449 ns
    cost of 1 guards: 19 ns (4.5%)
    average cost of 1 guard: 19 ns (4.5%)

Script: ``benchmarks/bench_guards.py``.
