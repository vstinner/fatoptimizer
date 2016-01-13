import ast

from .tools import OptimizerStep


CONSTANTS = {
    '__debug__': __debug__,
}


class ReplaceBuiltinConstant(OptimizerStep):
    def visit_Name(self, node):
        if not self.config.replace_builtin_constant:
            return
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            return

        name = node.id
        if name not in CONSTANTS:
            return
        if not self.is_builtin_variable(name):
            # constant overriden in the local or in the global namespace
            return

        result = CONSTANTS[name]
        return self.new_constant(node, result)
