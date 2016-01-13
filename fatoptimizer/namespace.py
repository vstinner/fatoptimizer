import ast
import contextlib

from .tools import (UNSET, get_constant, compact_dump,
    OptimizerError, NodeVisitor, RestrictToFunctionDefMixin, OptimizerStep)


class ComplexAssignment(OptimizerError):
    def __init__(self, node):
        super().__init__("Complex assignment: %s" % compact_dump(node))
        self.node = node


def _get_ast_name_node(node):
    while True:
        # only accept '*var'
        if isinstance(node, ast.Starred):
            # '*var = value' => 'var'
            node = node.value
        elif isinstance(node, ast.Subscript):
            # 'obj[slice] = value' => 'obj'
            node = node.value
        elif isinstance(node, ast.Attribute):
            # 'obj.attr = value' => 'obj'
            node = node.value
        elif (isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)):
            # 'obj.method().attr = value' => 'obj.method'
            node = node.func
        else:
            return node

def get_ast_names(node):
    node = _get_ast_name_node(node)

    if isinstance(node, ast.Name):
        return (node.id,)

    if isinstance(node, ast.Tuple):
        names = []
        for item in node.elts:
            item_names = get_ast_names(item)
            if item_names is None:
                return None
            names.extend(item_names)
        return names

    # unknown node type: return None


def _get_assign_names(targets, load_names, store_names):
    for target in targets:
        orig_target = target
        target = _get_ast_name_node(target)
        if (isinstance(target, ast.Name)
             and isinstance(target.ctx, ast.Store)):
            # 'x = value': store name 'x'
            store_names.add(target.id)
        elif (isinstance(target, ast.Name)
             and isinstance(target.ctx, ast.Load)):
            # 'obj.attr = value': load name 'obj'
            load_names.add(target.id)
        elif isinstance(target, ast.Tuple):
            # x, y = ...
            _get_assign_names(target.elts, load_names, store_names)
        elif isinstance(target, ast.Constant):
            # '(1).__class__ = MyInt': it raises a TypeError
            raise ComplexAssignment(orig_target)
        elif isinstance(target, (ast.Dict, ast.List)):
            # '{...}[key] = ...', '[...][index] = ...'
            pass
        elif isinstance(target, ast.Call):
            # 'globals()[key] = value'
            # 'type(mock)._mock_check_sig = checksig'
            raise ComplexAssignment(orig_target)
        else:
            raise Exception("unsupported assign target: %s"
                            % ast.dump(target))


class GlobalVisitor(NodeVisitor, RestrictToFunctionDefMixin):
    """Search for 'global var' statements."""

    def __init__(self, filename):
        super().__init__(filename)
        self.global_variables = set()

    def visit_Global(self, node):
        self.global_variables |= set(node.names)


class NonlocalVisitor(NodeVisitor):
    """Search for 'nonlocal var' statements."""

    def __init__(self, filename):
        super().__init__(filename)
        self.nonlocal_variables = set()

    def visit_Nonlocal(self, node):
        self.nonlocal_variables |= set(node.names)


class VariableVisitor(NodeVisitor, RestrictToFunctionDefMixin):
    """Find local and global variables.

    Find local and global variables of a function, but exclude variables of
    nested functions (functions, list comprehensions, generator expressions,
    etc.).
    """
    def __init__(self, filename):
        super().__init__(filename)
        # variable names
        self.global_variables = set()
        self.local_variables = set()
        self.nonlocal_variables = set()

    @classmethod
    def from_node_list(cls, filename, node_list):
        visitor = cls(filename)
        for node in node_list:
            visitor.find_variables(node)
        return visitor

    def find_variables(self, node):
        # search for "global var"
        visitor = GlobalVisitor(self.filename)
        visitor.generic_visit(node)
        self.global_variables |= visitor.global_variables

        # search for "nonlocal var"
        visitor = NonlocalVisitor(self.filename)
        visitor.generic_visit(node)
        self.nonlocal_variables |= visitor.nonlocal_variables

        # visit all nodes
        self.generic_visit(node)

    def visit_arg(self, node):
        self.local_variables.add(node.arg)

    def _assign(self, targets):
        # get variables
        load_names = set()
        store_names = set()
        _get_assign_names(targets, load_names, store_names)

        # Global and non local variables cannot be local variables
        store_names -= (self.global_variables | self.nonlocal_variables)
        self.local_variables |= store_names
        self.global_variables |= load_names

    def visit_For(self, node):
        self._assign([node.target])

    def visit_Assign(self, node):
        self._assign(node.targets)

    def visit_AugAssign(self, node):
        # We don't really need to handle AugAssign, Assign is enough to
        # detect local variables
        self._assign([node.target])

    def fullvisit_FunctionDef(self, node):
        self.local_variables.add(node.name)

    def fullvisit_AsyncFunctionDef(self, node):
        self.local_variables.add(node.name)

    def fullvisit_ClassDef(self, node):
        self.local_variables.add(node.name)

    def _visit_import_names(self, names):
        for name in names:
            if name.asname:
                self.local_variables.add(name.asname)
            else:
                self.local_variables.add(name.name)

    def visit_Import(self, node):
        self._visit_import_names(node.names)

    def visit_ImportFrom(self, node):
        self._visit_import_names(node.names)

    def visit_withitem(self, node):
        if node.optional_vars is not None:
            self._assign([node.optional_vars])


class Namespace:
    def __init__(self):
        # True if we are unable to follow the namespace, False otherwise
        self._unknown_state = False
        # mapping: variable name => value,
        # value can be UNSET for unknown value
        self._variables = {}
        # True if we are inside a conditional block (ast.If, ast.For body, etc.)
        self._inside_cond = False

    @contextlib.contextmanager
    def cond_block(self):
        """Enter a conditional block.

        Operations on local variables inside a condition block makes these
        variables as "unknown state".
        """
        was_inside = self._inside_cond
        try:
            self._inside_cond = True
            yield
        finally:
            self._inside_cond = was_inside

    def enter_unknown_state(self):
        if self._unknown_state:
            return True
        self._variables.clear()
        self._unknown_state = True
        return False

    def set(self, name, value):
        if not isinstance(name, str):
            raise TypeError("expect str")
        if self._unknown_state:
            return
        if self._inside_cond:
            value = UNSET
        self._variables[name] = value

    def unset(self, name):
        if self._unknown_state:
            return
        if self._inside_cond:
            self._variables[name] = UNSET
        else:
            if name in self._variables:
                del self._variables[name]

    def get(self, name):
        """Get the current value of a variable.

        Return UNSET if its value is unknown, or if the variable is not set.
        """
        if self._inside_cond:
            return UNSET
        return self._variables.get(name, UNSET)


class NamespaceStep(OptimizerStep):
    def fullvisit_FunctionDef(self, node):
        self.namespace.set(node.name, UNSET)

    def fullvisit_AsyncFunctionDef(self, node):
        self.namespace.set(node.name, UNSET)

    def fullvisit_ClassDef(self, node):
        self.namespace.set(node.name, UNSET)

    def _namespace_set(self, node, value, unset=False):
        if value is not UNSET:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names = (node.id,)
            else:
                names = get_ast_names(node)
                value = UNSET
        else:
            names = get_ast_names(node)

        if names is None:
            if self.namespace.enter_unknown_state():
                self.log(node,
                         "enter unknown namespace state: "
                         "don't support assignment %s",
                         compact_dump(node))
            return False

        for name in names:
            if unset:
                self.namespace.unset(name)
            else:
                self.namespace.set(name, value)
        return True

    def visit_Assign(self, node):
        value = get_constant(node.value)
        for target in node.targets:
            if not self._namespace_set(target, value):
                break

    def visit_AugAssign(self, node):
        self._namespace_set(node.target, UNSET)

    def visit_For(self, node):
        self._namespace_set(node.target, UNSET)

    def _visit_Import(self, node):
        for modname in node.names:
            if modname.asname:
                name = modname.asname
            else:
                name = modname.name
                # replace 'os.path' with 'os'
                name = name.split('.', 1)[0]
            self.namespace.set(name, UNSET)

    def visit_Import(self, node):
        self._visit_Import(node)

    def visit_ImportFrom(self, node):
        self._visit_Import(node)

    def visit_withitem(self, node):
        if node.optional_vars is not None:
            self._namespace_set(node.optional_vars, UNSET)

    def visit_Delete(self, node):
        for target in node.targets:
            if not self._namespace_set(target, UNSET, unset=True):
                break
