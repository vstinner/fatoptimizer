import ast

from .tools import (OptimizerStep, ReplaceVariable, FindNodes,
                    compact_dump, copy_lineno,
                    ITERABLE_TYPES)


CANNOT_UNROLL = (ast.Break, ast.Continue, ast.Raise)


class UnrollStep(OptimizerStep):
    def _visit_For(self, node):
        if not isinstance(node.target, ast.Name):
            return

        # for i in (1, 2, 3): ...
        if not isinstance(node.iter, ast.Constant):
            return
        iter_value = node.iter.value
        if not isinstance(iter_value, tuple):
            return
        if not(1 <= len(iter_value) <= self.config.unroll_loops):
            return

        # don't optimize if 'break' or 'continue' is found in the loop body
        found = None
        def find_callback(node):
            nonlocal found
            found = node
            return False

        # FIXME: restrict this the current scope
        # (don't enter class/function def/list comprehension/...)
        visitor = FindNodes(CANNOT_UNROLL, find_callback)
        visitor.visit(node)
        if found is not None:
            self.log(node,
                     "cannot unroll loop: %s is used at line %s",
                     compact_dump(found),
                     found.lineno)
            return

        name = node.target.id
        body = node.body

        # replace 'for i in (1, 2, 3): body' with...
        new_node = []
        for value in node.iter.value:
            value_ast = self.new_constant(node.iter, value)
            if value_ast is None:
                return

            # 'i = 1'
            name_ast = ast.Name(id=name, ctx=ast.Store())
            copy_lineno(node, name_ast)
            assign = ast.Assign(targets=[name_ast],
                                value=value_ast)
            copy_lineno(node, assign)
            new_node.append(assign)

            # duplicate 'body'
            new_node.extend(body)

        if node.orelse:
            new_node.extend(node.orelse)

        self.log(node, "unroll loop (%s iterations)", len(node.iter.value))

        return new_node

    def visit_For(self, node):
        if not self.config.unroll_loops:
            return

        new_node = self._visit_For(node)
        if new_node is None:
            return

        # loop was unrolled: run again the optimize on the new nodes
        return self.visit_node_list(new_node)


class UnrollListComp:
    def _unroll_comp(self, node, new_ast_type):
        if not self.config.unroll_loops:
            return

        # FIXME: support multiple generators
        # [i for i in range(3) for y in range(3)]
        if len(node.generators) > 1:
            return

        generator = node.generators[0]
        if not isinstance(generator, ast.comprehension):
            return
        # FIXME: support if
        if generator.ifs:
            return

        if not isinstance(generator.target, ast.Name):
            return
        target = generator.target.id

        if not isinstance(generator.iter, ast.Constant):
            return
        iter = generator.iter.value
        if not isinstance(iter, ITERABLE_TYPES):
            return

        items = []
        body = node.elt
        for value in iter:
            ast_value = self.new_constant(node, value)
            if ast_value is None:
                return
            replace = ReplaceVariable(self.filename, {target: ast_value})
            item = replace.visit(body)
            items.append(item)

        new_node = new_ast_type(elts=items, ctx=ast.Load())
        copy_lineno(node, new_node)
        return new_node

    def unroll_list_comp(self, node):
        return self._unroll_comp(node, ast.List)

    def unroll_set_comp(self, node):
        return self._unroll_comp(node, ast.Set)
