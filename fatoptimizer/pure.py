from .tools import UNSET


class PureFunction:
    def __init__(self, func, name, narg, *arg_types, check_args=None, exceptions=None):
        self.func = func
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

        try:
            result = self.func(*args)
        except Exception as exc:
            if (self.exceptions is not None
               and isinstance(exc, self.exceptions)):
                result = UNSET
            else:
                raise

        return result
