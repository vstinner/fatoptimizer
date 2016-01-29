from .pure import PureFunction


def add_pure_methods(config):
    def add(obj_type, name, *args, **kw):
        if obj_type not in config._pure_methods:
            config._pure_methods[obj_type] = {}
        func = getattr(obj_type, name)
        pure = PureFunction(func, name, *args, **kw)
        config._pure_methods[obj_type][name] = pure

    add(bytes, 'decode', (0, 2), str, str)
    add(str, 'encode', (0, 2), str, str)
