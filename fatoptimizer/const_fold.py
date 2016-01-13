import ast
import math
import operator

from .tools import (OptimizerStep, UNSET,
    FLOAT_TYPES, COMPLEX_TYPES, ITERABLE_TYPES,
    copy_lineno, get_constant, get_constant_size, copy_node, get_literal,
    compact_ascii)


SUBSCRIPT_INDEX_TYPES = tuple(set(ITERABLE_TYPES) - {set, frozenset})
SUBSCRIPT_SLICE_TYPES = tuple(set(ITERABLE_TYPES) - {set, frozenset, dict})
SLICE_ARG_TYPES = (int, type(None))


DIVIDE_BINOPS = (ast.Div, ast.FloorDiv, ast.Mod)

EVAL_BINOP = {
    # a + b, a - b, a * b
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    # see binop(): floordiv() may be used for int/int on Python 2
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    # a ** b
    ast.Pow: operator.pow,
    # a << b, a >> b
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    # a & b, a | b, a ^ b
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
}
BINOP_STR = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.Div: '/',
    ast.FloorDiv: '//',
    ast.Mod: '%',
    ast.Pow: '**',
    ast.LShift: '<<',
    ast.RShift: '>>',
    ast.BitAnd: '&',
    ast.BitOr: '|',
    ast.BitXor: '^',
}

# int: accept all keys of EVAL_BINOP
FLOAT_BINOPS = (
    ast.Add, ast.Sub,
    ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.Pow)
COMPLEX_BINOPS = (
    ast.Add, ast.Sub,
    ast.Mult, ast.Div,
)

EVAL_UNARYOP = {
    # not a, ~a, +a, -a
    ast.Not: operator.not_,
    ast.Invert: operator.invert,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

NOT_COMPARE = {
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,

    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,

    # Don't replace 'not(x < y)' with 'x >= y' because both expressions
    # can be different. For example, 'not(math.nan < 1.0)' is true,
    # whereas 'math.nan >= 1.0' is false.
    #
    # Don't replace 'not(x == y)' with 'x != y' because 'not x.__eq__(y)'
    # can return a different result than 'x.__ne__(y)'. For example,
    # a class may implement __eq__() but not __ne__() and the default
    # implementation of __ne__() has a different behaviour than
    # the class implementation of __eq__().
}

EVAL_COMPARE = {
    ast.In: lambda obj, seq: obj in seq,
    ast.NotIn: lambda obj, seq: obj not in seq,

    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,

    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def check_pow(config, num, exp, mod=None):
    if num == 0 and exp < 0:
        # 0 ** -1 raises a ZeroDivisionError
        return False

    if num < 0 and exp < 1.0 and exp != 0.0:
        # pow(-25, 0.5) raises a ValueError
        return False

    if mod is not None:
        # pow(a, b, m) only works if a and b are integers
        if not isinstance(num, int):
            return False
        if not isinstance(exp, int):
            return False

        if mod == 0:
            # pow(2, 1024, 0) raises a ValueError:
            # 'pow() 3rd argument cannot be 0'
            return False

    if (isinstance(num, int)
       and isinstance(exp, int)
       # don't call log2(0) (error)
       and num != 0
       # if exp < 0, the result is a float which has a fixed size
       and exp > 0):
        # bits(num ** exp) = log2(num) * exp
        if math.log2(abs(num)) * exp >= config.max_int_bits:
            # pow() result will be larger than max_constant_size.
            return False

    return True


class ConstantFolding(OptimizerStep):
    def check_binop(self, op, left, right):
        if isinstance(left, COMPLEX_TYPES) and isinstance(right, COMPLEX_TYPES):
            if isinstance(op, DIVIDE_BINOPS) and not right:
                # x/0: ZeroDivisionError
                return False

            if isinstance(op, ast.Pow):
                if isinstance(left, complex) or isinstance(right, complex):
                    return False

                return check_pow(self.config, left, right)

            if isinstance(op, (ast.LShift, ast.RShift)) and right < 0:
                # 1 << -3 and 1 >> -3 raise a ValueError
                return False

        if isinstance(left, int) and isinstance(right, int):
            return True

        if isinstance(left, FLOAT_TYPES) and isinstance(right, FLOAT_TYPES):
            return isinstance(op, FLOAT_BINOPS)

        if isinstance(left, COMPLEX_TYPES) and isinstance(right, COMPLEX_TYPES):
            return isinstance(op, COMPLEX_BINOPS)

        if isinstance(op, ast.Mult):
            if isinstance(right, int):
                # bytes * int
                if isinstance(left, bytes):
                    return (len(left) * right <= self.config.max_bytes_len)
                # str * int
                if isinstance(left, str):
                    return (len(left) * right <= self.config.max_str_len)
                # tuple * int
                if isinstance(left, tuple):
                    size = get_constant_size(left)
                    return (size * right <= self.config.max_seq_len)

            if isinstance(left, int):
                # int * bytes
                if isinstance(right, bytes):
                    return (left * len(right) <= self.config.max_bytes_len)
                # int * str
                if isinstance(right, str):
                    return (left * len(right) <= self.config.max_str_len)
                # int * tuple
                if isinstance(right, tuple):
                    size = get_constant_size(right)
                    return (left * size <= self.config.max_seq_len)

        if isinstance(op, ast.Add):
            if isinstance(left, str) and isinstance(right, str):
                return ((len(left) + len(right)) <= self.config.max_str_len)

            if isinstance(left, bytes) and isinstance(right, bytes):
                return ((len(left) + len(right)) <= self.config.max_bytes_len)

            if isinstance(left, tuple) and isinstance(right, tuple):
                return ((len(left) + len(right)) <= self.config.max_seq_len)

        return False

    def visit_BinOp(self, node):
        if not self.config.constant_folding:
            return

        eval_binop = EVAL_BINOP.get(node.op.__class__)
        if not eval_binop:
            return

        if isinstance(node.op, ast.Mod):
            # FIXME: optimize str%args and bytes%args
            left_types = COMPLEX_TYPES
        else:
            left_types = None

        left = get_constant(node.left, types=left_types)
        if left is UNSET:
            return

        right = get_constant(node.right)
        if right is UNSET:
            return

        ok = self.check_binop(node.op, left, right)
        if not ok:
            return

        result = eval_binop(left, right)
        new_node = self.new_constant(node, result)
        if new_node is None:
            return

        op_str = BINOP_STR[node.op.__class__]
        self.log(node, "constant folding: replace %s %s %s with %s",
                 compact_ascii(left), op_str, compact_ascii(right),
                 compact_ascii(result), add_line=True)
        return new_node

    def not_compare(self, node):
        compare = node.operand
        if len(compare.ops) != 1:
            # FIXME: optimize: 'not a <= b <= c' to 'a > b or b > c'
            return

        op = compare.ops[0]
        try:
            op = NOT_COMPARE[op.__class__]()
        except KeyError:
            return
        new_cmp = ast.Compare(left=compare.left, ops=[op],
                              comparators=compare.comparators)
        copy_lineno(compare, new_cmp)
        return new_cmp

    def visit_UnaryOp(self, node):
        if not self.config.constant_folding:
            return

        eval_unaryop = EVAL_UNARYOP.get(node.op.__class__)
        if eval_unaryop is None:
            return

        if isinstance(node.op, ast.Invert):
            types = int
        else:
            types =  COMPLEX_TYPES

        value = get_constant(node.operand, types=types)
        if value is not UNSET:
            result = eval_unaryop(value)
            return self.new_constant(node, result)

        if (isinstance(node.op, ast.Not)
        and isinstance(node.operand, ast.Compare)):
            new_node = self.not_compare(node)
            if new_node is not None:
                return new_node

    def subscript_slice(self, node):
        value = get_literal(node.value, types=SUBSCRIPT_SLICE_TYPES)
        if value is UNSET:
            return

        ast_start = node.slice.lower
        ast_stop = node.slice.upper
        ast_step = node.slice.step

        if ast_start is not None:
            start = get_constant(ast_start, types=SLICE_ARG_TYPES)
            if start is UNSET:
                return
        else:
            start = None
        if ast_stop is not None:
            stop = get_constant(ast_stop, types=SLICE_ARG_TYPES)
            if stop is UNSET:
                return
        else:
            stop = None
        if ast_step is not None:
            step = get_constant(ast_step, types=SLICE_ARG_TYPES)
            if step is UNSET:
                return
        else:
            step = None

        myslice = slice(start, stop, step)
        result = value[myslice]
        return self.new_constant(node, result)

    def subscript_index(self, node):
        value = get_literal(node.value, types=SUBSCRIPT_INDEX_TYPES)
        if value is UNSET:
            return

        if isinstance(value, dict):
            # dict[key] accepts any hashable key
            index_types = None
        else:
            index_types = int
        index = get_constant(node.slice.value, types=index_types)
        if index is UNSET:
            return

        try:
            result = value[index]
        except (IndexError, KeyError):
            return

        return self.new_constant(node, result)

    def visit_Subscript(self, node):
        if not self.config.constant_folding:
            return

        if isinstance(node.slice, ast.Slice):
            new_node = self.subscript_slice(node)
            if new_node is not None:
                return new_node

        elif isinstance(node.slice, ast.Index):
            new_node = self.subscript_index(node)
            if new_node is not None:
                return new_node

    def compare_cst(self, node):
        node_op = node.ops[0].__class__
        eval_op = EVAL_COMPARE.get(node_op)
        if eval_op is None:
            return

        if node_op in (ast.In, ast.NotIn):
            right_types = ITERABLE_TYPES
        else:
            right_types = None

        left = get_literal(node.left)
        if left is UNSET:
            return
        right = get_literal(node.comparators[0], types=right_types)
        if right is UNSET:
            return

        if (node_op in (ast.Eq, ast.NotEq)
           and ((isinstance(left, str) and isinstance(right, bytes))
                or (isinstance(left, bytes) and isinstance(right, str)))):
            # comparison between bytes and str can raise BytesWarning depending
            # on runtime option
            return

        try:
            result = eval_op(left, right)
        except TypeError:
            return
        return self.new_constant(node, result)

    def compare_contains(self, node):
        seq_ast = node.comparators[0]
        if not isinstance(seq_ast, (ast.Set, ast.List)):
            return

        seq = get_literal(seq_ast)
        if seq is UNSET:
            return

        if isinstance(seq_ast, ast.Set):
            seq = frozenset(seq)
        else:
            seq = tuple(seq)

        new_seq_ast = self.new_constant(seq_ast, seq)
        if new_seq_ast is None:
            return

        new_node = copy_node(node)
        new_node.comparators[0] = new_seq_ast
        return new_node

    def visit_Compare(self, node):
        if not self.config.constant_folding:
            return

        if len(node.ops) != 1:
            # FIXME: implement 1 < 2 < 3
            return
        if len(node.comparators) != 1:
            # FIXME: support this case? What's the syntax of this case?
            return

        new_node = self.compare_cst(node)
        if new_node is not None:
            return new_node

        # replace 'None is None' with True
        if (isinstance(node.ops[0], (ast.Is, ast.IsNot))
           and isinstance(node.left, ast.Constant)
           and node.left.value is None
           and isinstance(node.comparators[0], ast.Constant)
           and node.comparators[0].value is None):
            result = isinstance(node.ops[0], ast.Is)
            return self.new_constant(node, result)

        # replace 'x in {1, 2}' with 'x in frozenset({1, 2})'
        # replace 'x in [1, 2]' with 'x in frozenset((1, 2))'
        if isinstance(node.ops[0], ast.In):
            new_node = self.compare_contains(node)
            if new_node is not None:
                return new_node
