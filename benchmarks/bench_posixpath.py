"""
Microbenchmark on function inlining.

Inline manuall _get_sep() in isabs(). Both functions come from the posixpath
module of the standard library.
"""

import fat
from fatoptimizer.benchmark import bench, format_dt, compared_dt

def _get_sep(path):
    if isinstance(path, bytes):
        return b'/'
    else:
        return '/'

def isabs(s):
    """Test whether a path is absolute"""
    sep = _get_sep(s)
    return s.startswith(sep)

def fast_isabs(s):
    """Test whether a path is absolute"""
    sep = _get_sep(s)
    return s.startswith(sep)

# Manually inline _get_sep() in isabs() depending on the type of the s argument
def isabs_str(s):
    return s.startswith('/')

for func in (_get_sep, isabs, fast_isabs, isabs_str):
    if fat.get_specialized(func):
        print("ERROR: a function is already specialized!")
        sys.exit(1)

fat.specialize(fast_isabs, isabs_str,
               [fat.GuardArgType(0, (str,)),
                fat.GuardGlobals(('_get_sep',)),
                fat.GuardBuiltins(('isinstance',)),
                fat.GuardFunc(_get_sep)])

dt = bench("isabs('/abc')")
print("original isabs() bytecode: %s" % format_dt(dt))

dt2 = bench("fast_isabs('/abc')")
print("_get_sep() inlined in isabs(): %s" % compared_dt(dt2, dt))

