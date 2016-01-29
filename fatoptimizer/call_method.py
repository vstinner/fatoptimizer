import ast

from .tools import OptimizerStep, UNSET, get_literal
from .specialized import BuiltinGuard


class CallPureMethods(OptimizerStep):
    """Call methods of builtin types which have no side effect."""

    def call_method(self, pure_func, obj, node):
        value = pure_func.call_method(obj, node)
        if value is UNSET:
            return

        new_node = self.new_constant(node, value)
        if new_node is None:
            return

        self.log(node, "call pure method: replace %s with %r",
                 ast.dump(node), value, add_line=True)
        return new_node

    def visit_Call(self, node):
        attr = node.func
        if not isinstance(attr, ast.Attribute):
            return
        if not isinstance(attr.value, ast.Constant):
            return
        method_name = attr.attr

        obj = attr.value.value
        value_type = type(obj)
        if value_type not in self.config._pure_methods:
            return
        methods = self.config._pure_methods[value_type]
        if method_name not in methods:
            return
        pure_func = methods[method_name]

        return self.call_method(pure_func, obj, node)
