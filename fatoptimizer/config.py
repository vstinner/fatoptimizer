import builtins

from .tools import get_constant_size, ITERABLE_TYPES


class Config:
    # FIXME: use dir()?
    _attributes = '''
        _pure_builtins
        _pure_methods
        constant_folding
        constant_propagation
        copy_builtin_to_constant
        enabled
        inlining
        logger
        max_bytes_len
        max_constant_size
        max_int_bits
        max_str_len
        max_seq_len
        remove_dead_code
        replace_builtin_constant
        simplify_iterable
        unroll_loops
    '''.strip().split()

    def __init__(self, *, _optimize=True):
        # Is the AST optimizer enabled?
        self.enabled = True

        # File where logs are written to
        self.logger = None

        # Maximum size of a constant in bytes: the constant size is computed
        # using the size in bytes of marshal.dumps() output
        self.max_constant_size = 128

        # Maximum number of bits of a constant integer. Ignore the sign.
        self.max_int_bits = 256

        # Maximum length in bytes of a bytes string.
        self.max_bytes_len = self.max_constant_size

        # Maximum length in characters of a Unicode string.
        self.max_str_len = self.max_constant_size

        # Maximum length in number of items of a sequence. It is only a
        # preliminary check: max_constant_size still applies for sequences.
        self.max_seq_len = self.max_constant_size // 4

        # Methods of builtin types which have no side effect.
        #
        # Mapping: type => method_mapping
        # where method_mapping is a mapping: name => PureFunction
        self._pure_methods = {}

        # Builtin functions (PureFunction instances) which have no side effect
        # and so can be called during the compilation
        self._pure_builtins = {}

        # copy a global variable to a local variable, optimized used to load
        # builtin functions from slow builtins to fast local variables
        #
        # This optimizations breaks test_dynamic which explicitly modifies
        # builtins in the middle of a generator.
        self.copy_builtin_to_constant = False
        self._copy_builtin_to_constant = set(dir(builtins))

        # Loop unrolling (disabled by default): maximum number of loop
        # iterations (ex: n in 'for index in range(n):')
        self.unroll_loops = 16

        # Constant propagation
        self.constant_propagation = True

        # Constant folding
        self.constant_folding = True

        # Replace builtin constants (__debug__)
        self.replace_builtin_constant = True

        # Simplify iterables?
        # Example: replace 'for x in {}: ...' with 'for x in (): ...'
        self.simplify_iterable = True

        # Remove dead code?
        # Example: "if 0: ..." => "pass"
        self.remove_dead_code = True

        if _optimize:
            from .builtins import add_pure_builtins
            add_pure_builtins(self)

            from .methods import add_pure_methods
            add_pure_methods(self)

    def replace(self, config):
        new_config = Config(_optimize=False)
        for attr in self._attributes:
            if not attr.startswith('_') and attr in config:
                value = config[attr]
            else:
                value = getattr(self, attr)
            setattr(new_config, attr, value)
        return new_config

    def disable_all(self):
        self.max_constant_size = 128
        self.max_int_bits = 256
        self.max_bytes_len = self.max_constant_size
        self.max_str_len = self.max_constant_size
        self.max_seq_len = self.max_constant_size // 4
        self._pure_builtins = {}
        self._pure_methods = {}
        self.copy_builtin_to_constant = False
        self._copy_builtin_to_constant = set()
        self.unroll_loops = 0
        self.constant_propagation = False
        self.constant_folding = False
        self.replace_builtin_constant = False
        self.remove_dead_code = False
        self.simplify_iterable = False
        self.inlining = False

    def enable_all(self):
        self.max_constant_size = 1024   # 1 KB
        self.max_int_bits = self.max_constant_size
        self.max_bytes_len = self.max_constant_size
        self.max_str_len = self.max_constant_size
        self.max_seq_len = self.max_constant_size

        self.copy_builtin_to_constant = True
        self._copy_builtin_to_constant = set(dir(builtins))
        self.unroll_loops = 256
        self.constant_propagation = True
        self.constant_folding = True
        self.replace_builtin_constant = True
        self.remove_dead_code = True
        self.simplify_iterable = True
        self.inlining = True

        from .builtins import add_pure_builtins
        add_pure_builtins(self)

    def check_result(self, value):
        if isinstance(value, int):
            return (value.bit_length() <= self.max_int_bits)

        if isinstance(value, bytes):
            return (len(value) <= self.max_bytes_len)

        if isinstance(value, str):
            return (len(value) <= self.max_str_len)

        if isinstance(value, ITERABLE_TYPES) and len(value) > self.max_seq_len:
            return False

        size = get_constant_size(value)
        return (size <= self.max_constant_size)
