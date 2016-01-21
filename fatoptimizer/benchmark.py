"""
Tools used by microbenchmarks.
"""

import sys
import timeit


def bench(stmt, *, setup='', repeat=10**5, number=10):
    caller_globals = sys._getframe(1).f_globals
    timer = timeit.Timer(stmt, setup=setup, globals=caller_globals)
    return min(timer.repeat(repeat=repeat, number=number)) / number


def format_dt(dt, sign=False):
    if abs(dt) > 10e-3:
        if sign:
            return "%+.1f ms" % (dt*1e3)
        else:
            return "%.1f ms" % (dt*1e3)
    elif abs(dt) > 10e-6:
        if sign:
            return "%+.1f us" % (dt*1e6)
        else:
            return "%.1f us" % (dt*1e6)
    else:
        if sign:
            return "%+.0f ns" % (dt*1e9)
        else:
            return "%.0f ns" % (dt*1e9)


def compared_dt(specialized_dt, original_dt):
    percent = (specialized_dt - original_dt) * 100 / original_dt
    ratio = original_dt / specialized_dt
    if ratio >= 1.0:
        what = 'faster :-)'
    else:
        what = 'slower :-('
    return ('%s (%s, %+.1f%%, %.1fx %s)'
            % (format_dt(specialized_dt),
               format_dt(specialized_dt - original_dt, sign=True),
               percent, ratio, what))
