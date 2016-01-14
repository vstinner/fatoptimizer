++++++++++
Benchmarks
++++++++++

Macro benchmarks
================

fatoptimizer is not ready for macro benchmarks. Important optimizations like
function inlining are still missing. See :ref:`fatoptimizer TODO list <todo>`.

Microbenchmarks
===============

Reminder: even a significant speedup on a microbenchmark doesn't mean that you
will get the same speedup on your application.

The ``benchmarks/`` directory contains microbenchmarks used to test ``fat`` and
``fatoptimizer`` performances.

Cost of guards
--------------

2016-01-06::

    $ ./python -F bench_guards.py

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


Move invariant out of loop (list.append)
----------------------------------------


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



posixpath.isabs
---------------

Code::

    def _get_sep(path):
        if isinstance(path, bytes):
            return b'/'
        else:
            return '/'

    def isabs(s):
        """Test whether a path is absolute"""
        sep = _get_sep(s)
        return s.startswith(sep)

    if sys.flags.fat:
        import fat

        def isabs_str(s):
            return s.startswith('/')

        i = isabs.add(isabs_bytes)
        isabs.add_arg_type_guard(i, 0, bytes)
        isabs.add_dict_key_guard(i, sys.modules[__name__].__dict__, '_get_sep')
        isabs.add_func_guard(i, _get_sep)

2015-10-21::

    $ ./python -m timeit 'import posixpath; isabs = posixpath.isabs' 'isabs("/root")'
    1000000 loops, best of 3: 0.939 usec per loop
    $ ./python -F -m timeit 'import posixpath; isabs = posixpath.isabs' 'isabs("/root")'
    1000000 loops, best of 3: 0.755 usec per loop

=> 20% faster

