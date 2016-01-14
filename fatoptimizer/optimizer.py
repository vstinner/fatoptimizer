import ast
import linecache

from .namespace import (VariableVisitor, ComplexAssignment,
    NamespaceStep)
from .tools import (copy_lineno, _new_constant, pretty_dump,
    ReplaceVariable, FindStrVisitor, get_literal,
    RestrictToFunctionDefMixin)
from .specialized import BuiltinGuard, SpecializedFunction
from .base_optimizer import BaseOptimizer
from .const_propagate import ConstantPropagation
from .const_fold import ConstantFolding
from .call_pure import CallPureBuiltin
from .unroll import UnrollStep
from .copy_to_const import CopyBuiltinToConstantStep
from .bltin_const import ReplaceBuiltinConstant
from .convert_const import ConvertConstant
from .dead_code import RemoveDeadCode, remove_dead_code
from .iterable import SimplifyIterable, SimplifyIterableSpecialize


def add_import(tree, name, asname):
    # import fat as __fat__
    import_node = ast.Import(names=[ast.alias(name=name, asname=asname)],
                      lineno=1, col_offset=1)
    for index, node in enumerate(tree.body):
        if (index == 0 and isinstance(node, ast.Expr)
           and isinstance(node.value, ast.Constant)
           and isinstance(node.value.value, str)):
            # docstring
            continue
        if (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            # from __future__ import ...
            continue
        tree.body.insert(index, import_node)
        break
    else:
        # body is empty or only contains __future__ imports
        tree.body.append(import_node)


class NakedOptimizer(BaseOptimizer):
    """Optimizer without any optimization."""

    def __init__(self, config, filename, parent=None):
        BaseOptimizer.__init__(self, filename)
        self.config = config
        if parent is not None:
            self.parent = parent
            # module is a ModuleOptimizer instance
            self.module = parent.module
        else:
            self.parent = None
            self.module = self
        # attributes set in optimize()
        self.root = None
        self._global_variables = set()
        self.nonlocal_variables = set()
        self.local_variables = set()
        # used by FunctionOptimizer.new_str_constant()
        self._new_str_constants = set()

    def optimize_node_list(self, node_list):
        if not self.config.remove_dead_code:
            return node_list
        return remove_dead_code(self, node_list)

    @classmethod
    def from_parent(cls, parent):
        return cls(parent.config, parent.filename, parent=parent)

    def new_constant(self, node, value):
        if not self.config.check_result(value):
            return
        return _new_constant(node, value)

    def log(self, node, message, *args, add_line=False):
        logger = self.config.logger
        if not logger:
            return
        message = message % args
        message = "%s: fatoptimizer: %s" % (self.error_where(node), message)
        print(message, file=logger)

        if add_line:
            line = linecache.getline(self.filename, node.lineno)
            if line:
                line = line.strip()
            if line:
                print("  %s" % line, file=logger)

        logger.flush()

    def _is_global_variable(self, name):
        if name in self._global_variables:
            return True
        module = self.module
        if module is not self:
            if name in module.local_variables:
                return True
            if name in module._global_variables:
                return True
        return False

    def is_builtin_variable(self, name):
        # local variable?
        if name in self.local_variables:
            return False

        # global variable?
        if self._is_global_variable(name):
            return False

        # non local variable?
        if name in self.nonlocal_variables:
            return False

        # free variable? (local variable of a parent function)
        parent = self.parent
        while parent is not None:
            if name in parent.local_variables:
                return False
            parent = parent.parent

        # variable not defined anywhere: it is likely
        # the expected builtin function
        return True

    def new_local_variable(self, name):
        if name in self.local_variables:
            index = 2
            while True:
                name2 = "%s%s" % (name, index)
                if name2 not in self.local_variables:
                    break
                index += 1
            name = name2
        return name

    def _run_new_optimizer(self, node):
        optimizer = Optimizer.from_parent(self)
        return optimizer.optimize(node)

    def fullvisit_FunctionDef(self, node):
        optimizer = FunctionOptimizer.from_parent(self)
        new_node = optimizer.optimize(node)
        if isinstance(new_node, list):
            # The function was optimized

            # find new local variables
            visitor = VariableVisitor.from_node_list(self.filename, new_node)
            self.local_variables |= visitor.local_variables
        return new_node

    def optimize(self, tree):
        self.root = tree

        # Find variables
        visitor = VariableVisitor(self.filename)
        try:
            visitor.find_variables(tree)
        except ComplexAssignment as exc:
            # globals() is used to store a variable:
            # give up, don't optimize the function
            self.log(exc.node, "skip optimisation: %s", exc)
            return tree
        self._global_variables |= visitor.global_variables
        self.nonlocal_variables |= visitor.nonlocal_variables
        self.local_variables |= visitor.local_variables

        # Optimize nodes
        return self.generic_visit(tree)


class Optimizer(NakedOptimizer,
                NamespaceStep,
                ReplaceBuiltinConstant,
                UnrollStep,
                ConstantPropagation,
                SimplifyIterable,
                ConstantFolding,
                RemoveDeadCode):
    """Optimizer for AST nodes other than Module and FunctionDef."""


class FunctionOptimizerStage1(RestrictToFunctionDefMixin, Optimizer):
    """Stage 1 optimizer for ast.FunctionDef nodes."""



class FunctionOptimizer(NakedOptimizer,
                        CallPureBuiltin,
                        SimplifyIterableSpecialize,
                        CopyBuiltinToConstantStep):
    """Optimizer for ast.FunctionDef nodes.

    First, run FunctionOptimizerStage1 and then run optimizations which may
    create a specialized function.
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        if self.parent is None:
            raise ValueError("parent is not set")
        self._guards = []
        # FIXME: move this to the optimizer step?
        # global name => CopyBuiltinToConstant
        self.copy_builtin_to_constants = {}

    def add_guard(self, new_guard):
        if not isinstance(new_guard, BuiltinGuard):
            raise ValueError("unsupported guard")
        if self._guards:
            guard = self._guards[0]
            guard.add(new_guard)
        else:
            self._guards.append(new_guard)

    def new_str_constant(self, value):
        str_constants = self._new_str_constants
        str_constants |= self.parent._new_str_constants

        # FIXME: self.root is an old version of the tree, the new tree can
        # contain new strings
        visitor = FindStrVisitor.from_node(self.filename, self.root)
        str_constants |= visitor.str_constants

        visitor = FindStrVisitor.from_node(self.filename, self.parent.root)
        str_constants |= visitor.str_constants

        if value in str_constants:
            index = 2
            while True:
                new_value = "%s#%s" % (value, index)
                if new_value not in str_constants:
                    break
                index += 1
            value = new_value

        self._new_str_constants.add(value)
        self.parent._new_str_constants.add(value)
        return value

    def _patch_constants(self, node):
        copy_builtin_to_constants = self.copy_builtin_to_constants.values()
        patch_constants = {}
        for copy_global in copy_builtin_to_constants:
            builtin_name = copy_global.global_name
            value = ast.Name(id=builtin_name, ctx=ast.Load())
            patch_constants[copy_global.unique_constant] = value
            self.add_guard(BuiltinGuard(builtin_name, reason='patch constant'))

        names = dict((copy_global.global_name, copy_global.unique_constant)
                     for copy_global in copy_builtin_to_constants)
        replace = ReplaceVariable(self.filename, names)
        new_node = replace.replace_func_def(node)
        return (new_node, patch_constants)

    def _specialize(self, func_node, new_node):
        if self.copy_builtin_to_constants:
            new_node, patch_constants = self._patch_constants(new_node)
        else:
            patch_constants = None

        self.log(func_node, "specialize function %s, guards: %s",
                 func_node.name, self._guards)

        new_body = [func_node]

        tmp_name = self.parent.new_local_variable('_ast_optimized')
        func = SpecializedFunction(new_node.body, self._guards, patch_constants)

        modname = self.module.get_fat_module_name()
        for node in func.to_ast(modname, func_node, tmp_name):
            copy_lineno(func_node, node)
            new_body.append(node)

        return new_body

    def _stage1(self, tree):
        optimizer = FunctionOptimizerStage1.from_parent(self)
        return optimizer.optimize(tree)

    def optimize(self, func_node):
        func_node = self._stage1(func_node)

        if func_node.decorator_list:
            # FIXME: support decorators
            self.log(func_node, "skip optimisation: don't support decorators")
            return func_node

        new_node = super().optimize(func_node)

        if self._guards:
            # calling pure functions, replacing range(n) with a tuple, etc.
            # can allow new optimizations with the stage 1
            new_node = self._stage1(new_node)

        if self.copy_builtin_to_constants or self._guards:
            new_node = self._specialize(func_node, new_node)

        return new_node


class ModuleOptimizer(Optimizer):
    """Optimizer for ast.Module nodes."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._fat_module = None

    def get_fat_module_name(self):
        if not self._fat_module:
            # FIXME: ensure that the name is unique...
            self._fat_module = '__fat__'
        return self._fat_module

    def _replace_config(self, node):
        config = get_literal(node)
        if not isinstance(config, dict):
            # ignore invalid config
            return True

        # Replace the configuration
        # Note: unknown configuration options are ignored
        self.config = self.config.replace(config)

    def _find_config(self, body):
        # FIXME: only search in the N first statements?
        # Example: skip docstring, but stop at the first import?
        for node in body:
            if (isinstance(node, ast.Assign)
               and len(node.targets) == 1
               and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == '__fatoptimizer__'):
                self._replace_config(node.value)

    def optimize(self, tree):
        orig_tree = tree

        tree = ConvertConstant(self.filename).visit(tree)

        if isinstance(tree, ast.Module):
            self._find_config(tree.body)
            if not self.config.enabled:
                self.log(tree,
                         "skip optimisation: disabled in __fatoptimizer__")
                return orig_tree

        tree = super().optimize(tree)

        if self._fat_module:
            add_import(tree, 'fat', self._fat_module)

        return tree
