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
func_cst.__code__ = fat.replace_consts(func_cst.__code__, {'LEN': len})

dt = bench('func()')
print("original bytecode (call len): %s" % format_dt(dt))

dt2 = bench('func_cst()')
print("return 3: %s" % compared_dt(dt2, dt))

fat.specialize(func, func_cst, [fat.GuardBuiltins(('dict',))])
assert fat.get_specialized(func)
dt3 = bench('func()')
print("specialized (return 3): %s" % compared_dt(dt3, dt))

print("cost of GuardBuiltins: %s" % format_dt(dt3 - dt2, sign=True))
