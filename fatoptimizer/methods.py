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
    # FIXME: add more bytes methods

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
