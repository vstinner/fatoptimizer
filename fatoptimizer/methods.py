import codecs

from .pure import PureFunction


def check_encoding(args):
    if len(args) >= 1:
        encoding = args[0]
        try:
            encoding = codecs.lookup(encoding).name
        except LookupError:
            return False
        # FIXME: Allow more encodings?
        if encoding not in ('ascii', 'iso8859-1', 'utf-8'):
            return False

    if len(args) >= 2:
        errors = args[1]
        # FIXME: support more error handlers
        # 'backslashreplace' (only for encode), 'surrogateescape', etc.
        if errors not in ('strict', 'replace', 'ignore'):
            return False

    return True


def check_bytetype(args):
    return all(isinstance(arg, bytes) for arg in args)


def check_byte_or_int(*args):
    return all(any([isinstance(arg,bytes),(isinstance(arg,int) and arg<256 and arg >=0)]) for arg in args)


def add_pure_methods(config):
    def add(obj_type, name, *args, **kw):
        if obj_type not in config._pure_methods:
            config._pure_methods[obj_type] = {}
        func = getattr(obj_type, name)
        pure = PureFunction(func, name, *args, **kw)
        config._pure_methods[obj_type][name] = pure

    add(bytes, 'decode', (0, 2), str, str,
        check_args=check_encoding,
        exceptions=UnicodeDecodeError)
    add(bytes, 'count', (1, 3), object, int, int,
        check_args= check_byte_or_int,
        exceptions=TypeError)
    add(bytes, 'endswith', (1, 3), tuple, int, int)
    add(bytes, 'find', (1, 3), object, int, int,
        check_args= check_byte_or_int,
        exceptions=TypeError)
    add(bytes, 'index', (1, 3), object, int, int,
        check_args= check_byte_or_int,
        exceptions=TypeError)

    add(bytes, 'join', (0,1), object,
        check_args=check_bytetype,
        exceptions=TypeError)
    add(bytes, 'maketrans', 2, bytes, bytes)
    add(bytes, 'partition', 1, bytes)
    add(bytes, 'replace', (2,3), bytes, bytes, int)
    add(bytes, 'rfind', (1, 3), bytes, int, int)
    add(bytes, 'rindex', (1, 3), bytes, int, int)
    add(bytes, 'rpartition', 1, bytes)
    add(bytes, 'startswith', (1, 3), bytes, int, int)
    add(bytes, 'translate', (1, 2), bytes, bytes)
    add(bytes, 'center', (1, 2), int, str)
    add(bytes, 'ljust', (1, 2), int, str)
    add(bytes, 'lstrip', (1, 2), bytes)
    add(bytes, 'rjust', (1, 2), int, str)
    add(bytes, 'rstrip', (0, 1), bytes)
    add(bytes, 'rsplit', (0, 2), bytes, int)
    add(bytes, 'split', (0, 2), bytes, int)
    add(bytes, 'strip', (0, 1), bytes)
    add(bytes, 'capitalize', 0)
    add(bytes, 'expandtabs', (0, 1), int)
    add(bytes, 'isalnum', 0)
    add(bytes, 'isalpha', 0)
    add(bytes, 'isdigit', 0)
    add(bytes, 'islower', 0)
    add(bytes, 'isspace', 0)
    add(bytes, 'istitle', 0)
    add(bytes, 'isupper', 0)
    add(bytes, 'islower', 0)
    add(bytes, 'splitlines', (0, 1), bool)
    add(bytes, 'swapcase', 0)
    add(bytes, 'title', 0)
    add(bytes, 'upper', 0)
    add(bytes, 'zfill', 1, int)


    # FIXME: add config option since IEEE 754 can be funny on some corner
    # cases?
    add(float, 'as_integer_ratio', 0)
    add(float, 'is_integer', 0)
    add(float, 'hex', 0)

    # FIXME: frozenset:
    # 'copy', 'difference', 'intersection', 'union', 'symmetric_difference',
    #  'isdisjoint', 'issubset', 'issuperset',

    add(int, 'bit_length', 0)

    add(str, 'encode', (0, 2), str, str,
        check_args=check_encoding,
        exceptions=UnicodeEncodeError)
    # FIXME: add more str methods
    add(str, 'lower', 0)
    add(str, 'upper', 0)
    add(str, 'capitalize', 0)
    add(str, 'swapcase', 0)
    add(str, 'casefold', 0)
    add(str, 'isalpha', 0)
    add(str, 'isalnum', 0)
    add(str, 'isdecimal', 0)
    add(str, 'isdigit', 0)
    add(str, 'islower', 0)
    add(str, 'isnumeric', 0)
    add(str, 'isupper', 0)
    add(str, 'isidentifier', 0)
    add(str, 'istitle', 0)
    add(str, 'isspace', 0)
    add(str, 'swapcase', 0)
    add(str, 'title', 0)


    # FIXME: tuple: count, index
