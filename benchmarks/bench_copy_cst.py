"""
Microbenchmark on the "copy builtin to constant".

The benchmark doesn't use fatoptimize, but specialize explicitly the function.
"""
import fat
import sys

mylen = len

def func(obj):
    return mylen(obj)

if fat.get_specialized(func):
    print("ERROR: func() was already specialized")
    sys.exit(1)

def func_cst(obj):
    return 'MYLEN'(obj)
func_cst.__code__ = fat.replace_consts(func_cst.__code__, {'MYLEN': mylen})

def run_benchmark(bench):
    bench.timeit(stmt='func("abc")',
                 globals=globals(),
                 name='original bytecode (LOAD_GLOBAL)')

    bench.timeit(stmt='func_cst("abc")',
                 globals=globals(),
                 name='LOAD_CONST')

    fat.specialize(func, func_cst, [fat.GuardGlobals(('mylen',))])
    assert fat.get_specialized(func)

    bench.timeit(stmt='func("abc")',
                 globals=globals(),
                 name='LOAD_CONST with guard')

