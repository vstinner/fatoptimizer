"""
Microbenchmark on the "copy builtin to constant".

The benchmark doesn't use fatoptimize, but specialize explicitly the function.
"""
import fat
import sys
from fatoptimizer.benchmark import bench, format_dt

def func():
    dict()
    dict()
    dict()
    dict()
    dict()
    dict()
    dict()
    dict()
    dict()
    dict()

if fat.get_specialized(func):
    print("ERROR: func() was already specialized")
    sys.exit(1)

dt = bench(func)
print("original bytecode (LOAD_GLOBAL dict): %s" % format_dt(dt))


def func_cst():
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
    'DICT'()
func_cst.__code__ = fat.replace_consts(func_cst.__code__, {'DICT': dict})

fat.specialize(func, func_cst, [fat.GuardBuiltins(('dict',))])

dt = bench(func)
print("specialized (LOAD_CONST): %s" % format_dt(dt))
