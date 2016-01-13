import ast

from .namespace import Namespace
from .tools import NodeTransformer


_COND_BLOCK = {ast.If, ast.For, ast.While, ast.Try}


class BaseOptimizer(NodeTransformer):
    def __init__(self, filename):
        super().__init__(filename)
        self.namespace = Namespace()

    def _visit_attr(self, parent_node, attr_name, node):
        parent_type = type(parent_node)
        if (parent_type in _COND_BLOCK
           and attr_name != "finalbody"
           and not(attr_name == "test" and parent_type == ast.If)):
            with self.namespace.cond_block():
                return self.visit(node)
        else:
            return self.visit(node)

    def _run_new_optimizer(self, node):
        optimizer = BaseOptimizer()
        return optimizer.visit(node)

    def fullvisit_FunctionDef(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_AsyncFunctionDef(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_ClassDef(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_DictComp(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_ListComp(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_SetComp(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_GeneratorExp(self, node):
        return self._run_new_optimizer(node)

    def fullvisit_Lambda(self, node):
        return self._run_new_optimizer(node)
