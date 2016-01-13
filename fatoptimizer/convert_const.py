import ast

from .tools import NodeTransformer, copy_lineno


class ConvertConstant(NodeTransformer):
    # Note: update PRIMITIVE_TYPES, ITERABLE_TYPES
    # and _is_constant() of tools when new types are supported

    def convert(self, node, value):
        new_node = ast.Constant(value=value)
        copy_lineno(node, new_node)
        return new_node

    def visit_NameConstant(self, node):
        return self.convert(node, node.value)

    def visit_Num(self, node):
        return self.convert(node, node.n)

    def visit_Str(self, node):
        return self.convert(node, node.s)

    def visit_Bytes(self, node):
        return self.convert(node, node.s)

    def visit_Tuple(self, node):
        elts = []
        for elt in node.elts:
            if not isinstance(elt, ast.Constant):
                return
            elts.append(elt.value)
        return self.convert(node, tuple(elts))
