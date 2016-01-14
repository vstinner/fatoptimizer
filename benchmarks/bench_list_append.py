"""
Microbenchmark on "move invariant (list.append) out of loops" optimization.

Specialize manually the function.
"""

import fat
import sys
import timeit
from fatoptimizer.benchmark import bench, format_dt, compared_dt


def func(obj, data):
    for item in data:
        obj.append(item)


def func2(obj, data):
    for item in data:
        obj.append(item)


def fast_func2(obj, data):
    append = obj.append
    for item in data:
        append(item)


def main():
    if fat.get_specialized(func) or fat.get_specialized(func2):
        print("ERROR: functions already specialized!")
        sys.exit(1)

    fat.specialize(func2, fast_func2, [fat.GuardArgType(0, (list,))])

    def bench_list(func, range_pow10):
        repeat = 10 ** max(5 - range_pow10, 1)
        return bench(func,
              stmt='mylist = []; func(mylist, data)',
              setup='data=range(10 ** %s)' % range_pow10,
              repeat=repeat, number=10)

    for range_pow10 in (0, 1, 3, 5):
        print("range(10 ** %s)" % range_pow10)

        dt = bench_list(func, range_pow10)
        print("- original bytecode: %s" % format_dt(dt))

        dt2 = bench_list(func2, range_pow10)
        print("- specialized bytecode: %s" % compared_dt(dt2, dt))


if __name__ == "__main__":
    main()
