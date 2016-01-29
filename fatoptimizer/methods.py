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
    add(str, 'encode', (0, 2), str, str,
        check_args=check_encoding,
        exceptions=UnicodeEncodeError)
