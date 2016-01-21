"""
Microbenchmark on the "call builtin functions [with a constant]".

The benchmark doesn't use fatoptimize, but specialize explicitly the function.
"""
import fat
import sys
from fatoptimizer.benchmark import bench, format_dt, compared_dt

def func():
    return len("abc")

if fat.get_specialized(func):
    print("ERROR: func() was already specialized")
    sys.exit(1)

def func_cst():
    return 3

def run_benchmark(bench):
    bench.timeit('func()',
                 globals=globals(),
                 name="original bytecode (call len)")

    bench.timeit('func_cst()',
                 globals=globals(),
                 name="return 3")

    fat.specialize(func, func_cst, [fat.GuardBuiltins(('len',))])
    assert fat.get_specialized(func)

    bench.timeit('func()',
                 globals=globals(),
                 name="return 3 with guard on builtins")
