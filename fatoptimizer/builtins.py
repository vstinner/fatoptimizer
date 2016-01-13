import builtins
import functools

from .tools import (UNSET,
    FLOAT_TYPES, COMPLEX_TYPES, STR_TYPES, ITERABLE_TYPES)
from .const_fold import check_pow


class _PureBuiltin:
    def __init__(self, name, narg, *arg_types, check_args=None, exceptions=None):
        self.name = name
        if isinstance(narg, tuple):
            self.min_narg, self.max_narg = narg
            if self.min_narg is None:
                raise ValueError("minimum number of parameters is None")
        elif isinstance(narg, int):
            self.min_narg = narg
            self.max_narg = narg
        else:
            raise TypeError("narg must be tuple or int, got %s"
                            % type(narg).__name__)
        self.arg_types = arg_types
        if len(self.arg_types) < self.min_narg:
            raise ValueError("not enough argument types")
        if self.max_narg is not None and len(self.arg_types) > self.max_narg:
            raise ValueError("too many argument types")
        self._check_args_cb = check_args
        self.exceptions = exceptions

    def check_nargs(self, nargs):
        if self.min_narg is not None and self.min_narg > nargs:
            return False
        if self.max_narg is not None and self.max_narg < nargs:
            return False
        return True

    def _check_args(self, args):
        if not self.check_nargs(len(args)):
            return False
        if self._check_args_cb is not None:
            if not self._check_args_cb(args):
                return False
        return True

    def call(self, args):
        if not self._check_args(args):
            return UNSET

        func = getattr(builtins, self.name)
        try:
            result = func(*args)
        except Exception as exc:
            if (self.exceptions is not None
               and isinstance(exc, self.exceptions)):
                result = UNSET
            else:
                raise

        return result


def _chr_check_args(args):
    code_point = args[0]
    return 0 <= code_point <= 0x10ffff


def _complex_check_args(args):
    code_point = args[0]
    return 0 <= code_point <= 0x10ffff


def _divmod_check_args(args):
    # don't divide by zero
    return bool(args[1])


def _ord_check_args(args):
    string = args[0]
    return (len(string) == 1)


def _bytes_check_args(args):
    arg = args[0]
    if not isinstance(arg, tuple):
        return True
    return all(0 <= item <= 255 for item in arg)


def _pow_check_args(config, args):
    num = args[0]
    exp = args[1]
    if len(args) >= 3:
        mod = args[2]
    else:
        mod = None
    return check_pow(config, num, exp, mod)


def add_pure_builtins(config):
    def add(*args, **kw):
        func = _PureBuiltin(*args, **kw)
        config._pure_builtins[func.name] = func

    ANY_TYPE = None

    pow_check_args = functools.partial(_pow_check_args, config)
    add('abs', 1, COMPLEX_TYPES)
    add('ascii', 1, ANY_TYPE)
    add('bin', 1, int)
    add('bool', 1, COMPLEX_TYPES + STR_TYPES)
    add('bytes', 1, (bytes,) + (tuple,), check_args=_bytes_check_args)
    add('chr', 1, int, check_args=_chr_check_args)
    # FIXME: optimize also complex(int, int)
    add('complex', (1, 2), COMPLEX_TYPES + STR_TYPES, COMPLEX_TYPES,
        # catch ValueError for complex('xyz')
        # catch TypeError for complex('xyz', 1)
        exceptions=(ValueError, TypeError))
    # catch TypeError for unhashable keys
    add('dict', (0, 1), ITERABLE_TYPES, exceptions=TypeError)
    add('divmod', 2, FLOAT_TYPES, FLOAT_TYPES, check_args=_divmod_check_args)
    add('float', 1, FLOAT_TYPES + STR_TYPES,
        # catch ValueError for float('xyz')
        exceptions=ValueError)
    # frozenset(([1, 2, 3],)) raises TypeError: unhashable type
    add('frozenset', (0, 1), ITERABLE_TYPES, exceptions=TypeError)
    add('hex', 1, int)
    add('int', 1, FLOAT_TYPES + STR_TYPES,
        # catch ValueError for int('xyz')
        exceptions=ValueError)
    add('len', 1, ITERABLE_TYPES)
    add('list', 1, ITERABLE_TYPES)
    add('oct', 1, int)
    add('ord', 1, STR_TYPES, check_args=_ord_check_args)
    add('max', (1, None), ANY_TYPE,
        # catch TypeError for non comparable values
        exceptions=TypeError)
    add('min', (1, None), ANY_TYPE,
        # catch TypeError for non comparable values
        exceptions=TypeError)
    add('pow', (2, 3), FLOAT_TYPES, FLOAT_TYPES, FLOAT_TYPES,
        check_args=pow_check_args,
        exceptions=(ValueError, TypeError, OverflowError))
    add('repr', 1, COMPLEX_TYPES + STR_TYPES)
    add('round', (1, 2), FLOAT_TYPES, int)
    # set(([1, 2, 3],)) raises TypeError: unhashable type
    add('set', 1, ITERABLE_TYPES, exceptions=TypeError)
    add('str', 1, COMPLEX_TYPES + (str,))
    # sum(): int+list raises TypeError
    add('sum', (1, 2), ANY_TYPE, ANY_TYPE,
        exceptions=TypeError)
    add('tuple', 1, ITERABLE_TYPES)
