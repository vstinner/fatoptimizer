import ast

from .tools import OptimizerStep, UNSET, compact_ascii


class ConstantPropagation(OptimizerStep):
    """Propagate constant values to variables.

    This optimizer step requires the NamespaceStep step.
    """
    def visit_Name(self, node):
        if not self.config.constant_propagation:
            return

        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            return
        name = node.id
        if name not in self.local_variables:
            # the Namespace object only tracks local variables
            return

        value = self.namespace.get(name)
        if value is UNSET:
            return

        new_node = self.new_constant(node, value)
        if new_node is None:
            return

        self.log(node, "constant propagation: replace %s with %s",
                 node.id, compact_ascii(value), add_line=True)
        return new_node
