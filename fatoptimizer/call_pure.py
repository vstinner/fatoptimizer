import ast

from .tools import OptimizerStep, UNSET, get_literal
from .specialized import BuiltinGuard


class CallPureBuiltin(OptimizerStep):
    def _get_call_args(self, pure_func, node):
        if node.keywords:
            # FIXME: support keywords
            return

        if not pure_func.check_nargs(len(node.args)):
            return

        values = []
        for index, node_arg in enumerate(node.args):
            try:
                arg_type = pure_func.arg_types[index]
            except IndexError:
                arg_type = None
            value = get_literal(node_arg, types=arg_type)
            if value is UNSET:
                return
            values.append(value)
        return values

    def _call_builtin(self, node, pure_func):
        args = self._get_call_args(pure_func, node)
        if args is None:
            return

        value = pure_func.call(args)
        if value is UNSET:
            return

        new_node = self.new_constant(node, value)
        if new_node is None:
            return

        self.log(node, "call pure builtin function: replace %s with %r",
                 ast.dump(node), value, add_line=True)
        self.add_guard(BuiltinGuard(node.func.id, 'call builtin'))
        return new_node

    def visit_Call(self, node):
        func = node.func

        if (isinstance(func, ast.Name)
           and func.id in self.config._pure_builtins
           and self.is_builtin_variable(func.id)):
            pure_func = self.config._pure_builtins[func.id]
            new_node = self._call_builtin(node, pure_func)
            if new_node is not None:
                return new_node
