import ast

from .tools import copy_lineno, _new_constant


class BuiltinGuard:
    def __init__(self, name, reason=None):
        self.names = {name}
        self.reason = reason

    def add(self, guard):
        self.names |= guard.names

    def as_ast(self, node, modname):
        name = ast.Name(id=modname, ctx=ast.Load())
        copy_lineno(node, name)

        func = ast.Attribute(value=name, attr='GuardBuiltins', ctx=ast.Load())
        copy_lineno(node, func)

        names = _new_constant(node, tuple(sorted(self.names)))
        call = ast.Call(func=func, args=[names], keywords=[])
        copy_lineno(node, call)
        return call

    def __repr__(self):
        info = ['names=%r' % self.names]
        if self.reason:
            info.append('reason=%r' % self.reason)
        return '<%s %s>' % (self.__class__.__name__, ' '.join(info))


class SpecializedFunction:
    def __init__(self, body, guards, patch_constants=None):
        self.body = body
        self.guards = guards
        self.patch_constants = patch_constants

    def to_ast(self, modname, func, tmp_name):
        # tmp_name = func
        yield ast.Assign(targets=[ast.Name(id=tmp_name, ctx=ast.Store())],
                         value=ast.Name(id=func.name, ctx=ast.Load()))

        # def func2(...): ...
        for node in self.body:
            copy_lineno(func, node)
        func2 = ast.FunctionDef(name=func.name, args=func.args, body=self.body,
                                # explicitly drops decorator for the
                                # specialized function
                                decorator_list=[],
                                returns=None)
        yield func2

        if self.patch_constants:
            # func.__code__ = func.__code__.replace_consts({...})
            dict_keys = []
            dict_values = []
            for key, value in self.patch_constants.items():
                # FIXME: use optimizer.new_constant()?
                key = _new_constant(func, key)
                value = _new_constant(func, value)
                dict_keys.append(key)
                dict_values.append(value)
            mapping = ast.Dict(keys=dict_keys, values=dict_values)
            copy_lineno(func, mapping)

            mod = ast.Name(id=modname, ctx=ast.Load())
            name_func = ast.Name(id=func2.name, ctx=ast.Load())
            attr = ast.Attribute(value=name_func, attr='__code__', ctx=ast.Load())
            call = ast.Call(func=ast.Attribute(value=mod,
                                               attr='replace_consts', ctx=ast.Load()),
                            args=[attr, mapping],
                            keywords=[])
            copy_lineno(func, call)

            target = ast.Attribute(value=name_func, attr='__code__', ctx=ast.Store())
            yield ast.Assign(targets=[target],
                             value=call)

        # encode guards
        guards = [guard.as_ast(func, modname) for guard in self.guards]
        guards = ast.List(elts=guards, ctx=ast.Load())
        copy_lineno(func, guards)

        # fat.specialize(tmp_name, func2, guards)
        specialize = ast.Attribute(value=ast.Name(id=modname, ctx=ast.Load()),
                                   attr='specialize', ctx=ast.Load())
        name_func = ast.Name(id=tmp_name, ctx=ast.Load())
        code = ast.Attribute(value=ast.Name(id=func2.name, ctx=ast.Load()),
                             attr='__code__', ctx=ast.Load())
        call = ast.Call(func=specialize, args=[name_func, code, guards],
                        keywords=[])
        yield ast.Expr(value=call)

        # func = tmp_name
        yield ast.Assign(targets=[ast.Name(id=func.name, ctx=ast.Store())],
                         value=ast.Name(id=tmp_name, ctx=ast.Load()))

        # del tmp_name
        yield ast.Delete(targets=[ast.Name(id=tmp_name, ctx=ast.Del())])
