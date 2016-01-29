import ast

from .tools import OptimizerStep, UNSET, get_literal
from .specialized import BuiltinGuard


class CallPureBuiltin(OptimizerStep):
    def visit_Call(self, node):
        attr = ode.func
        if not isinstance(attr, ast.Attribute):
            return
        if not isinstance(attr.value, ast.Constant):
            return
