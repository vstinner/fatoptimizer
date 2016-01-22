import ast
import collections
import marshal
import sys


FLOAT_TYPES = (int, float)
COMPLEX_TYPES = FLOAT_TYPES + (complex,)
STR_TYPES = (bytes, str)

# Primitive Python types (not containers)
PRIMITIVE_TYPES = (type(None), bool, int, float, complex, bytes, str)

# Iterable types
ITERABLE_TYPES = (str, bytes, tuple, frozenset, list, set, dict)

# Maximum length of a "short" AST dump, limit used by error_what() and default
# limit of compact_dump()
COMPACT_DUMP_MAXLEN = 100

# Marker used for "not set" value, different than None
UNSET = object()


class OptimizerError(Exception):
    pass


class OptimizerStep:
    pass


def compact_ascii(value, maxlen=30):
    text = ascii(value)
    if len(text) > maxlen:
        text = text[:maxlen] + '(...)'
    return text


def compact_dump(node, maxlen=COMPACT_DUMP_MAXLEN):
    if isinstance(node, list):
        return repr([compact_dump(node_item, maxlen) for node_item in node])
    node_repr = ast.dump(node)
    if len(node_repr) > maxlen:
        node_repr = node_repr[:maxlen] + '(...)'
    return node_repr


# FIXME: replace it with FindNodes, see unroll.py
def _iter_all_ast(node):
    yield node
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    for child in _iter_all_ast(item):
                        yield child
        elif isinstance(value, ast.AST):
            for child in _iter_all_ast(value):
                yield child


def ast_contains(tree, obj_type):
    if isinstance(tree, list):
        return any(ast_contains(node, obj_type) for node in tree)
    else:
        return any(isinstance(node, obj_type) for node in _iter_all_ast(tree))


def copy_node(node):
    new_node = type(node)()
    for field, value in ast.iter_fields(node):
        setattr(new_node, field, value)
    for attr in node._attributes:
        try:
            value = getattr(node, attr)
        except AttributeError:
            pass
        else:
            setattr(new_node, attr, value)
    return new_node


def get_constant_size(value):
    return len(marshal.dumps(value))


def _is_constant(value):
    if isinstance(value, (tuple, frozenset)):
        return all(_is_constant(item) for item in value)
    else:
        return isinstance(value, PRIMITIVE_TYPES)


def _new_constant(node, value):
    if isinstance(value, ast.AST):
        # convenient shortcut: return the AST object unchanged
        return value

    # FIXME: test the config directly here?

    if value is None:
        new_node = ast.Constant(value=None)
    elif isinstance(value, (bool, int, float, complex, str, bytes)):
        new_node = ast.Constant(value=value)
    elif isinstance(value, (tuple, frozenset)):
        if not _is_constant(value):
            raise TypeError("container items are not constant: %r" % (value,))
        new_node = ast.Constant(value=value)
    elif isinstance(value, list):
        elts = [_new_constant(node, elt) for elt in value]
        new_node = ast.List(elts=elts, ctx=ast.Load())
    elif isinstance(value, dict):
        keys = []
        values = []
        for key, value in value.items():
            keys.append(_new_constant(node, key))
            values.append(_new_constant(node, value))
        new_node = ast.Dict(keys=keys, values=values, ctx=ast.Load())
    elif isinstance(value, set):
        elts = [_new_constant(node, elt) for elt in value]
        new_node = ast.Set(elts=elts, ctx=ast.Load())
    else:
        raise TypeError("unknown type: %s" % type(value).__name__)

    copy_lineno(node, new_node)
    return new_node


# FIXME: use functools.singledispatch?
def _get_constant(node, *, types=None):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        # FIXME: rely on constant folding for that!
        value = get_constant(node.operand, types=types)
        if value is UNSET:
            return UNSET
        return (-value)
    return UNSET


def get_constant(node, *, types=None):
    if types is not None:
        value = _get_constant(node, types=types)
        if not isinstance(value, types):
            return UNSET
        return value
    else:
        return _get_constant(node)


def _get_node_list(seq, literal=False):
    values = []
    for value in seq:
        # only get constant items, otherwise optimizations will not produce
        # a constant
        if literal:
            value = _get_literal(value)
        else:
            value = get_constant(value)
        if value is UNSET:
            return UNSET
        values.append(value)
    return values


def _get_literal(node, constant_items=False):
    use_literal = (not constant_items)

    value = get_constant(node)
    if value is not UNSET:
        return value

    if isinstance(node, ast.Tuple):
        elts = _get_node_list(node.elts, literal=use_literal)
        if elts is UNSET:
            return UNSET
        return list(elts)

    if isinstance(node, ast.List):
        elts = _get_node_list(node.elts, literal=use_literal)
        if elts is UNSET:
            return UNSET
        return list(elts)

    if isinstance(node, ast.Set):
        # elements must be hashable
        elts = _get_node_list(node.elts)
        if elts is UNSET:
            return UNSET
        return set(elts)

    if isinstance(node, ast.Dict):
        # FIXME: this code is slow, only do it when get_literal() is
        # called with types==dict (or dict in types)

        # keys musts be hashable
        keys = _get_node_list(node.keys)
        if keys is UNSET:
            return UNSET

        values = _get_node_list(node.values, literal=use_literal)
        if values  is UNSET:
            return UNSET

        return dict(zip(keys, values))

    return UNSET


def get_literal(node, *, constant_items=False, types=None):
    if types is not None:
        value = _get_literal(node, constant_items)
        if not isinstance(value, types):
            return UNSET
        return value
    else:
        return _get_literal(node, constant_items)


def _set_lineno(node, lineno, col_offset):
    if 'lineno' in node._attributes:
        if not hasattr(node, 'lineno'):
            node.lineno = lineno
    if 'col_offset' in node._attributes:
        if not hasattr(node, 'col_offset'):
            node.col_offset = col_offset
    for child in ast.iter_child_nodes(node):
        _set_lineno(child, lineno, col_offset)


def copy_lineno(orig_node, new_node):
    _set_lineno(new_node, orig_node.lineno, orig_node.col_offset)


def pretty_dump(node, annotate_fields=True, include_attributes=False,
                lineno=False, indent='  '):
    """
    Return a formatted dump of the tree in *node*.  This is mainly useful for
    debugging purposes.  The returned string will show the names and the values
    for fields.  This makes the code impossible to evaluate, so if evaluation is
    wanted *annotate_fields* must be set to False.  Attributes such as line
    numbers and column offsets are not dumped by default.  If this is wanted,
    *include_attributes* can be set to True.

    Recipe written by Alex Leone, January 2010:
    http://alexleone.blogspot.fr/2010/01/python-ast-pretty-printer.html
    """
    def _format(node, level=0):
        if isinstance(node, ast.AST):
            fields = [(a, _format(b, level)) for a, b in ast.iter_fields(node)]
            if include_attributes and node._attributes:
                fields.extend([(a, _format(getattr(node, a), level))
                               for a in node._attributes])
            if lineno and getattr(node, 'lineno', None):
                fields.append(('lineno', str(node.lineno)))
            return ''.join([
                node.__class__.__name__,
                '(',
                ', '.join(('%s=%s' % field for field in fields)
                           if annotate_fields else
                           (b for a, b in fields)),
                ')'])
        elif isinstance(node, list):
            lines = ['[']
            lines.extend((indent * (level + 2) + _format(x, level + 2) + ','
                         for x in node))
            if len(lines) > 1:
                lines.append(indent * (level + 1) + ']')
            else:
                lines[-1] += ']'
            return '\n'.join(lines)
        return repr(node)
    if isinstance(node, list):
        nodes = [_format(item, 1) for item in node]
        nodes = (',\n' + indent).join(nodes)
        spaces = ' ' * (len(indent) - 1)
        return '[%s%s]' % (spaces, nodes)
    if not isinstance(node, ast.AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    return _format(node)


class NodeVisitorMeta(type):
    def __new__(mcls, name, bases, namespace):
        self_class = super().__new__(mcls, name, bases, namespace)

        steps = [cls for cls in self_class.__mro__
                 if OptimizerStep in cls.__bases__]

        # AST object name (ex: 'Name') => list of visitors
        self_class._fullvisitors = collections.defaultdict(list)
        self_class._visitors = collections.defaultdict(list)
        for step in steps:
            for name in dir(step):
                if name.startswith('fullvisit_'):
                    key = name[10:]
                    func = getattr(step, name)
                    self_class._fullvisitors[key].append(func)
                elif name.startswith('visit_'):
                    key = name[6:]
                    func = getattr(step, name)
                    self_class._visitors[key].append(func)

        for name in dir(self_class):
            if name.startswith('fullvisit_'):
                key = name[10:]
                func = getattr(self_class, name)
                visitors = self_class._fullvisitors[key]
                if func not in visitors:
                    visitors.append(func)
            elif name.startswith('visit_'):
                key = name[6:]
                func = getattr(self_class, name)
                visitors = self_class._visitors[key]
                if func not in visitors:
                    visitors.append(func)

        return self_class


class BaseNodeVisitor(metaclass=NodeVisitorMeta):
    def __init__(self, filename):
        self.filename = filename

    def error_what(self, node):
        return compact_dump(node, COMPACT_DUMP_MAXLEN)

    def error_where(self, node):
        where = self.filename
        if hasattr(node, 'lineno'):
            where = '%s:%s' % (where, node.lineno)
        return where

    def _call_visitor_method(self, visitor, node):
        """Call visitor(node).

        Wrap exceptions to add more context on error.
        OptimizerError exceptions are not catched.
        """
        try:
            return visitor(self, node)
        except (OptimizerError, RecursionError):
            raise
        except Exception as exc:
            what = self.error_what(node)
            where = self.error_where(node)
            raise OptimizerError("error at %s on visiting %s: %s"
                                 % (where, what, exc))


class NodeVisitor(BaseNodeVisitor, ast.NodeVisitor):
    """Node visitor.

    Differences with ast.NodeVisitor:

    - Compute the mapping AST node name => list of methods when the class
      is instanciated
    - Support 'full' visitors (method name prefixed with 'fullvisit_') which
      skip the call the generic_visit() and so give a full control
    - If an exception is raised, it is wrapped into a new OptimizerError
      which adds the location in the file (filename and line number)
      of the current proceed AST node.
    """
    def visit(self, node):
        key = node.__class__.__name__

        # "full" visitor calling generic_visit() internally?
        if key in self._fullvisitors:
            visitors = self._fullvisitors[key]
            for visitor in visitors:
                self._call_visitor_method(visitor, node)
        else:
            # visit attributes
            new_node = self.generic_visit(node)
            assert new_node is not UNSET
            if new_node is not None:
                node = new_node

        if key in self._visitors:
            # visit the node
            visitors = self._visitors[key]
            for visitor in visitors:
                self._call_visitor_method(visitor, node)


class NodeTransformer(BaseNodeVisitor):
    """Node visitor.

    Differences with ast.NodeTransformer:

    - Create a new tree if at least one attribute is modified, so the input
      tree is left unchanged
    - Inherit advantages of NodeVisitor compared to ast.NodeVisitor

    Creating a new tree is needed to be able to specialize a function:
    basically, return [original_tree, specialized_tree].
    """

    def optimize_node_list(self, node_list):
        return node_list

    def _visit_attr(self, parent_node, attr_name, node):
        return self.visit(node)

    def generic_visit(self, node, ignore_fields=None):
        fields = {}
        modified = False

        if ignore_fields:
            if isinstance(ignore_fields, str):
                ignore_fields = {ignore_fields}
            else:
                ignore_fields = set(ignore_fields)

        for field, value in ast.iter_fields(node):
            if ignore_fields is not None and field in ignore_fields:
                fields[field] = value
                continue

            if isinstance(value, list):
                values = value
                new_values = []
                all_ast = True
                for value in values:
                    if isinstance(value, ast.AST):
                        new_value = self._visit_attr(node, field, value)
                        modified |= (new_value != value)
                        if isinstance(new_value, list):
                            new_values.extend(new_value)
                        else:
                            new_values.append(new_value)
                    else:
                        # arguments.kw_defaults contains AST nodes
                        # (ex: Constant) and non-AST nodes (ex: None)
                        all_ast = False
                        new_values.append(value)
                if all_ast:
                    value = new_values
                    new_values = self.optimize_node_list(new_values)
                    modified |= (new_values is not value)
                value = new_values

            elif isinstance(value, ast.AST):
                old_value = value
                value = self._visit_attr(node, field, value)
                modified |= (value != old_value)

            # Create a dictionary of fields used if any field is modified
            # to create a new AST node
            fields[field] = value

        if modified:
            # create a new AST node with the new fields
            new_node = type(node)()
            if 'lineno' in node._attributes:
                copy_lineno(node, new_node)
            for field, value in fields.items():
                setattr(new_node, field, value)
            return new_node

        return node

    def visit(self, node):
        key = node.__class__.__name__

        # "full" visitor calling generic_visit() internally?
        if key in self._fullvisitors:
            visitors = self._fullvisitors[key]
            for visitor in visitors:
                new_node = self._call_visitor_method(visitor, node)
                if new_node is not None:
                    assert new_node is not UNSET
                    if type(new_node) != type(node):
                        # AST node type changed
                        return new_node
                    else:
                        node = new_node
        else:
            new_node = self.generic_visit(node)
            assert new_node is not UNSET
            if new_node is not None:
                node = new_node

        if key in self._visitors:
            visitors = self._visitors[key]
            for visitor in visitors:
                new_node = self._call_visitor_method(visitor, node)
                if new_node is not None:
                    assert new_node is not UNSET
                    if type(new_node) != type(node):
                        # AST node type changed
                        return new_node
                    else:
                        node = new_node

        return node

    def visit_node_list(self, node_list):
        assert isinstance(node_list, list)
        new_node_list = []
        for node in node_list:
            new_node = self.visit(node)
            assert new_node is not None and new_node is not UNSET
            if isinstance(new_node, list):
                new_node_list.extend(new_node)
            else:
                new_node_list.append(new_node)
        return new_node_list


class RestrictToFunctionDefMixin:
    # don't visit children of nodes having their own namespace
    def fullvisit_DictComp(self, node):
        return node
    def fullvisit_ListComp(self, node):
        return node
    def fullvisit_SetComp(self, node):
        return node
    def fullvisit_GeneratorExp(self, node):
        return node
    def fullvisit_FunctionDef(self, node):
        return node
    def fullvisit_AsyncFunctionDef(self, node):
        return node
    def fullvisit_Lambda(self, node):
        return node
    def fullvisit_ClassDef(self, node):
        return node


class FindStrVisitor(NodeVisitor, RestrictToFunctionDefMixin):
    """Find Str nodes.

    Find all Str nodes to compute constants.
    """
    def __init__(self, filename):
        super().__init__(filename)
        self.str_constants = set()

    @classmethod
    def from_node(cls, filename, node):
        visitor = cls(filename)
        visitor.visit(node)
        return visitor

    def visit_Str(self, node):
        self.str_constants.add(node.s)


class FindNodes:
    """Find AST nodes."""

    def __init__(self, ast_types, callback):
        self.ast_types = ast_types
        self.callback = callback

    def visit(self, node):
        if isinstance(node, self.ast_types):
            res = self.callback(node)
            if not res:
                return False
        return self.generic_visit(node)

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        res = self.visit(item)
                        if not res:
                            return False
            elif isinstance(value, ast.AST):
                res = self.visit(value)
                if not res:
                    return False
        return True


class ReplaceVariable(NodeTransformer, RestrictToFunctionDefMixin):
    def __init__(self, filename, name_mapping):
        super().__init__(filename)
        # Mapping (dict or whatever): old name => new name
        self.name_mapping = name_mapping

    def replace_func_def(self, node):
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id not in self.name_mapping:
            return node
        new_value = self.name_mapping[node.id]
        return _new_constant(node, new_value)


def Call(**kw):
    if sys.version_info >= (3, 5):
        return ast.Call(**kw)
    else:
        return ast.Call(starargs=None, kwargs=None, **kw)
