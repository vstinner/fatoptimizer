"""
Tools used by microbenchmarks.
"""

import timeit


def bench(func, *, stmt='func()', setup='', repeat=10**5, number=10):
    timer = timeit.Timer(stmt,
                         setup=setup,
                         globals={'func': func})
    return min(timer.repeat(repeat=repeat, number=number)) / number


def format_dt(dt):
    if dt > 10e-3:
        return "%.1f ms" % (dt*1e3)
    elif dt > 10e-6:
        return "%.1f us" % (dt*1e6)
    else:
        return "%.0f ns" % (dt*1e9)


def compared_dt(specialized_dt, original_dt):
    percent = (specialized_dt - original_dt) * 100 / original_dt
    ratio = original_dt / specialized_dt
    if ratio >= 1.0:
        what = 'faster :-)'
    else:
        what = 'slower :-('
    return ('%s (%+.1f%%, %.1fx %s)'
            % (format_dt(specialized_dt), percent, ratio, what))
