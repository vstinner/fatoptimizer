import ast

from .tools import OptimizerStep


class CopyBuiltinToConstant:
    def __init__(self, global_name, unique_constant):
        self.global_name = global_name
        self.unique_constant = unique_constant


class CopyBuiltinToConstantStep(OptimizerStep):
    def visit_Call(self, node):
        if not self.config.copy_builtin_to_constant:
            return

        if not isinstance(node.func, ast.Name):
            return
        func = node.func.id

        if func not in self.config._copy_builtin_to_constant:
            return

        if func in self.copy_builtin_to_constants:
            # already replaced
            return

        if not self.is_builtin_variable(func):
            return

        # If super() is replace with a string, the required free variable
        # (reference to the current class) is not created by the compiler
        if func == 'super':
            return

        unique_constant = self.new_str_constant('LOAD_GLOBAL %s' % func)
        copy_global = CopyBuiltinToConstant(func, unique_constant)
        self.copy_builtin_to_constants[func] = copy_global
