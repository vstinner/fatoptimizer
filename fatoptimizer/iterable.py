import ast

from .tools import (OptimizerStep,
    get_literal, copy_lineno, get_constant, get_keywords,
    UNSET, ITERABLE_TYPES)
from .specialized import BuiltinGuard


class BaseSimplifyIterable(OptimizerStep):
    """Simplify iterable expressions."""

    def optimize_iterable(self, node):
        raise NotImplementedError

    def visit_For(self, node):
        if not self.config.simplify_iterable:
            return

        new_iter = self.optimize_iterable(node.iter)
        if new_iter is None:
            return

        new_node = ast.For(target=node.target,
                           iter=new_iter,
                           body=node.body,
                           orelse=node.orelse)
        copy_lineno(node, new_node)
        return new_node


class SimplifyIterable(BaseSimplifyIterable):
    def optimize_iterable(self, node):
        # it's already a constant, nothing to do
        if isinstance(node, ast.Constant):
            return

        # remplace empty dict (create at runtime) with an empty tuple
        # (constant)
        if isinstance(node, ast.Dict) and not node.keys:
            return self.new_constant(node, ())

        # FIXME: optimize dict?
        value = get_literal(node, types=(list, set), constant_items=True)
        if value is UNSET:
            return

        if not value:
            # replace empty iterable with an empty tuple
            return self.new_constant(node, ())

        if len(value) > self.config.max_seq_len:
            return

        if isinstance(value, list):
            return self.new_constant(node, tuple(value))
        if isinstance(value, set):
            return self.new_constant(node, frozenset(value))


class SimplifyIterableSpecialize(BaseSimplifyIterable):
    def optimize_range(self, node):
        if not(1 <= len(node.args) <= 3):
            return
        if get_keywords(node):
            return
        args = []
        for node_arg in node.args:
            arg = get_constant(node_arg, types=int)
            if arg is UNSET:
                return
            args.append(arg)

        seq = range(*args)
        if len(seq) > self.config.max_seq_len:
            return
        value = self.new_constant(node, tuple(seq))
        if value is None:
            return

        self.add_guard(BuiltinGuard('range'))
        return value

    def optimize_iterable(self, node):
        if (isinstance(node, ast.Call)
           and isinstance(node.func, ast.Name)
           and node.func.id == 'range'
           and self.is_builtin_variable('range')):
            return self.optimize_range(node)
