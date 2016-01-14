import fat
import sys
import timeit
from fatoptimizer.benchmark import bench, format_dt

def fast_func():
    pass


# use for a dummy guard below
global_var = 2


def bench_guards(nguard):
    def func():
        pass

    no_guard = bench(func, number=100)
    print("no guard: %s" % format_dt(no_guard))

    if fat.get_specialized(func):
        print("ERROR: func already specialized")
        sys.exit(1)

    guards = [fat.GuardDict(globals(), ('global_var',)) for i in range(nguard)]
    fat.specialize(func, fast_func, guards)

    with_guards = bench(func)
    print("with %s guards on globals: %s"
          % (nguard, format_dt(with_guards)))

    dt = with_guards - no_guard
    print("cost of %s guards: %s (%.1f%%)"
          % (nguard, format_dt(dt), dt * 100 / no_guard))

    dt = dt / nguard
    print("average cost of 1 guard: %s (%.1f%%)"
          % (format_dt(dt), dt * 100 / no_guard))
    print()


def main():
    for nguard in (1000, 100, 10, 1):
        bench_guards(nguard)


if __name__ == "__main__":
    main()
