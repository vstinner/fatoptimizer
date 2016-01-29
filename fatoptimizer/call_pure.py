import ast

from .tools import OptimizerStep, UNSET, get_literal
from .specialized import BuiltinGuard


class CallPureBuiltin(OptimizerStep):
    def call_builtin(self, node, pure_func):
        value = pure_func.call(node)
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
            new_node = self.call_builtin(node, pure_func)
            if new_node is not None:
                return new_node
