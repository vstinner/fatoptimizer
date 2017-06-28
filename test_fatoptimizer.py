# Disable the AST optimizer on this module
__fatoptimizer__ = {'enabled': False}

import ast
import fatoptimizer.convert_const
import fatoptimizer.namespace
import fatoptimizer.optimizer
import fatoptimizer.tools
import io
import re
import sys
from fatoptimizer.tools import UNSET
import textwrap
import unittest
from unittest import mock


if sys.version_info < (3, 5):
    # RecursionError was introduced in Python 3.5
    fatoptimizer.tools.RecursionError = RuntimeError


need_python35 = unittest.skipIf(sys.version_info < (3, 5), "need python 3.5")



if not hasattr(ast, 'Constant'):
    # backport ast.Constant of the PEP 511
    class Constant(ast.AST):
        _attributes = ('lineno', 'col_offset')
        _fields = ('value',)

        def __init__(self, value):
            self.value = value

    ast.Constant = Constant


def format_code(code):
    return textwrap.dedent(code).strip()


def compile_ast(source):
    source = format_code(source)
    return ast.parse(source, '<string>', 'exec')


def compile_ast_expr(source):
    module = ast.parse(source, '<string>', 'exec')
    assert isinstance(module, ast.Module)
    body = module.body
    assert len(body) == 1
    expr = body[0]
    assert isinstance(expr, ast.Expr)
    return expr.value


def specialize_constant(node, value):
    if value is None or isinstance(value, bool):
        new_node = ast.NameConstant(value=value)
    elif isinstance(value, (int, float, complex)):
        new_node = ast.Num(n=value)
    elif isinstance(value, str):
        new_node = ast.Str(s=value)
    elif isinstance(value, bytes):
        new_node = ast.Bytes(s=value)
    elif isinstance(value, tuple):
        elts = [specialize_constant(node, elt) for elt in value]
        new_node = ast.Tuple(elts=elts, ctx=ast.Load())
    else:
        raise ValueError("unknown constant: %r" % value)
    fatoptimizer.tools.copy_lineno(node, new_node)
    return new_node


def builtin_guards(*names):
    args = ', '.join(map(repr, sorted(names)))
    return '[__fat__.GuardBuiltins(%s)]' % (args,)


class SpecializeConstant(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, frozenset):
            return node
        return specialize_constant(node, node.value)


class AstToolsTests(unittest.TestCase):
    def test_get_starargs(self):
        tree = compile_ast('func()')
        node = fatoptimizer.tools.get_starargs(tree.body[0].value)
        self.assertIsNone(node)

        tree = compile_ast('func(arg, *varargs)')
        node = fatoptimizer.tools.get_starargs(tree.body[0].value)
        self.assertIsInstance(node, ast.Name)
        self.assertEqual(node.id, 'varargs')

        tree = compile_ast('func()')
        with self.assertRaises(ValueError):
            fatoptimizer.tools.get_starargs(tree)

    def test_get_keywords(self):
        tree = compile_ast('func()')
        keywords = fatoptimizer.tools.get_keywords(tree.body[0].value)
        self.assertFalse(keywords)

        tree = compile_ast('func(x=1, y=2)')
        keywords = fatoptimizer.tools.get_keywords(tree.body[0].value)
        self.assertEqual(len(keywords), 2)
        self.assertIsInstance(keywords[0], ast.keyword)
        self.assertEqual(keywords[0].arg, 'x')
        self.assertIsInstance(keywords[1], ast.keyword)
        self.assertEqual(keywords[1].arg, 'y')

        tree = compile_ast('func(arg, *varargs, **kwargs)')
        keywords = fatoptimizer.tools.get_keywords(tree.body[0].value)
        self.assertEqual(len(keywords), 1)
        self.assertIsInstance(keywords[0], ast.keyword)
        self.assertIsNone(keywords[0].arg)

        tree = compile_ast('func()')
        with self.assertRaises(ValueError):
            fatoptimizer.tools.get_keywords(tree)

    def test_get_varkeywords(self):
        tree = compile_ast('func()')
        keywords = fatoptimizer.tools.get_varkeywords(tree.body[0].value)
        self.assertFalse(keywords)

        tree = compile_ast('func(x=1, y=2)')
        keywords = fatoptimizer.tools.get_varkeywords(tree.body[0].value)
        self.assertFalse(keywords)

        tree = compile_ast('func(arg, *varargs, **kwargs)')
        varkwds = fatoptimizer.tools.get_varkeywords(tree.body[0].value)
        self.assertIsInstance(varkwds, ast.Name)
        self.assertEqual(varkwds.id, 'kwargs')

        tree = compile_ast('func()')
        with self.assertRaises(ValueError):
            fatoptimizer.tools.get_varkeywords(tree)


class VariableVisitorTests(unittest.TestCase):
    def check_vars(self, code, local_variables, global_variables=None,
                   nonlocal_variables=None,
                   get_node=None):
        tree = compile_ast(code)
        self.assertIsInstance(tree, ast.Module)

        if get_node:
            node = get_node(tree)
        else:
            node = tree.body[0]

        visitor = fatoptimizer.namespace.VariableVisitor("<string>")
        visitor.find_variables(node)
        self.assertEqual(visitor.local_variables, local_variables)
        if global_variables is not None:
            self.assertEqual(visitor.global_variables, global_variables)
        else:
            self.assertEqual(visitor.global_variables, set())
        if nonlocal_variables is not None:
            self.assertEqual(visitor.nonlocal_variables, nonlocal_variables)
        else:
            self.assertEqual(visitor.nonlocal_variables, set())

    def test_module(self):
        code = """
            global x
            y = 1
        """
        self.check_vars(code, {'y'}, {'x'}, get_node=lambda tree: tree)

    def test_for(self):
        code = """
            def func(arg):
                for x in arg:
                    pass
                for y, z in arg:
                    pass
        """
        self.check_vars(code, {'arg', 'x', 'y', 'z'})

    def test_local(self):
        code = """
            x = 1
            def func():
                x = 2
        """
        self.check_vars(code, {'x'}, get_node=lambda tree: tree.body[1])

    def test_func_args(self):
        code = """
            def func(arg1, arg2, *varargs, **kwargs):
                pass
        """
        self.check_vars(code, {'arg1', 'arg2', 'varargs', 'kwargs'})

        code = """
            def func(*varargs):
                pass
        """
        self.check_vars(code, {'varargs'})

        code = """
            def func(**kw):
                pass
        """
        self.check_vars(code, {'kw'})

    @need_python35
    def test_nested(self):
        code = """
            def func(arg):
                def func2(arg2):
                    var2 = arg2
                async def afunc3(arg3):
                    var3 = arg3
                var = [None for listcomp in range(3)]
                var = {None: None for dictcomp in range(3)}
                var = {None for setcomp in range(3)}
                var = (None for genexp in range(3))
        """
        self.check_vars(code, {'arg', 'func2', 'afunc3', 'var'})

    def test_assign(self):
        code = """
            def func():
                a, b = 1, 2
                *c, d = (3, 4)
                e.f = 5
                g[:2] = [6, 7]
        """
        self.check_vars(code, {'a', 'b', 'c', 'd'}, {'e', 'g'})

    def test_assign_complex(self):
        code = """
            def func(arg):
                first, *obj.attr[0], last = arg
                obj.attr[0].attr2[1] = arg
        """
        self.check_vars(code, {'arg', 'first', 'last'}, {'obj'})

        code = """
            def func(arg):
                obj.meth().y = arg
        """
        self.check_vars(code, {'arg'}, {'obj'})

    def test_modify_globals(self):
        code = """
            def set_global(key, arg):
                globals()[key] = arg
        """
        with self.assertRaises(fatoptimizer.namespace.ComplexAssignment):
            self.check_vars(code, set())

        code = """
            def assign(checksig):
                type(mock)._mock_check_sig = checksig
        """
        with self.assertRaises(fatoptimizer.namespace.ComplexAssignment):
            self.check_vars(code, set())

    def test_global(self):
        code = """
            x = 1
            def func1():
                global x
                x = 2
        """
        self.check_vars(code, set(), {'x'}, get_node=lambda tree: tree.body[1])

    def test_nonlocal(self):
        code = """
            def func1():
                nonlocal x
                x = 2
        """
        self.check_vars(code, set(), nonlocal_variables={'x'})

    def test_late_global(self):
        code = """
            def func1():
                x = 6
                global x
        """
        self.check_vars(code, set(), {'x'})

    def test_function_def(self):
        code = """
            def func():
                x = 1
                def nested():
                    pass
        """
        self.check_vars(code, {'x', 'nested'})

    def test_import(self):
        code = """
            def func():
                from sys import flags
                from sys import ps1 as PS1
                import os
                import subprocess, email
        """
        self.check_vars(code, {'flags', 'PS1', 'os', 'subprocess', 'email'})

    def test_with(self):
        code = """
            def func():
                with open(name1) as fp1, open(name2) as fp2, open(name3):
                    pass
                with cm() as (a, b):
                    pass
                with cm() as self.attr:
                    pass
        """
        self.check_vars(code, {'fp1', 'fp2', 'a', 'b'}, {'self'})

        code = """
            obj = object()

            def func():
                global obj
                with cm() as obj.attr:
                    pass
        """
        self.check_vars(code, set(), {'obj'}, get_node=lambda tree: tree.body[1])

    def test_augassign(self):
        code = """
            def func():
                # artificial example, it raises UnboundLocalError
                x += 1
        """
        self.check_vars(code, {'x'})

    def test_nested_func(self):
        code = """
            def func(self):
                def func2():
                    self.attr = 1
        """
        self.check_vars(code, set(), {'self'},
                        get_node=lambda tree: tree.body[0].body[0])


class BaseAstTests(unittest.TestCase):
    maxDiff = 15000

    def setUp(self):
        if hasattr(sys, 'ast_transformers'):
            # Disable the AST hook (if any)
            old_transformers = sys.ast_transformers
            self.addCleanup(setattr, sys, 'ast_transformers', old_transformers )
            sys.ast_transformers = []

        # Disable all optimizations by default
        self.config = fatoptimizer.Config()
        self.config.disable_all()

    def assertAstEqual(self, tree1, tree2):
        # ast objects don't support comparison,
        # so compare their text representation
        tree1 = SpecializeConstant().visit(tree1)
        text1 = fatoptimizer.pretty_dump(tree1)
        text2 = fatoptimizer.pretty_dump(tree2)
        self.assertEqual(text1, text2)

    def optimize(self, source):
        tree = compile_ast(source)
        return fatoptimizer.optimize(tree, "<string>", self.config)

    def check_optimize(self, source1, source2):
        tree1 = self.optimize(source1)
        if isinstance(source2, ast.AST):
            tree2 = ast.Module(body=[source2])
        else:
            tree2 = compile_ast(source2)
        self.assertAstEqual(tree1, tree2)

    def check_optimize_func(self, expr, result):
        before = "def func(): return (%s)" % expr
        tree1 = self.optimize(before)

        if isinstance(result, ast.AST):
            after = "def func(): return 0"
            tree2 = compile_ast(after)
            tree2.body[0].body[0].value = result
        else:
            after = "def func(): return (%s)" % result
            tree2 = compile_ast(after)

        self.assertAstEqual(tree1, tree2)

    def check_dont_optimize(self, source, result=None):
        if result is None:
            result = source
        self.check_optimize(source, result)

    def check_dont_optimize_func(self, expr, result=None):
        if result is None:
            result = expr
        self.check_optimize_func(expr, result)

    def indent(self, source, level=1):
        source = format_code(source)
        indent = '    ' * level
        return '\n'.join(indent + line for line in source.splitlines())

    def format_specialize(self, before, specialized, guards,
                          template=None):
        before = textwrap.dedent(before).strip()
        specialized = textwrap.dedent(specialized).strip()

        if not template:
            template = """
                {import_fat}

                {code}
            """
        template = format_code(template)

        code1 = before

        code2 = textwrap.dedent("""
            import fat as __fat__

            {before}

            _ast_optimized = func

            {specialized}

            __fat__.specialize(_ast_optimized, func.__code__, {guards})

            func = _ast_optimized
            del _ast_optimized
        """).strip()
        code2 = code2.format(before=before,
                             specialized=specialized,
                             guards=guards)

        return (code1, code2)

    def check_specialize(self, *args, **kw):
        code1, code2 = self.format_specialize(*args, **kw)
        self.check_optimize(code1, code2)

    def check_func_specialize(self, source, specialized, guards,
                            replace_consts='', template=None):
        source = self.indent(source)
        before = textwrap.dedent("""
            def func():
            {source}
        """).strip()
        before = before.format(source=source)

        if isinstance(specialized, ast.AST):
            specialized_ast = specialized
            specialized = 'def func(): return 8421028141204'
        else:
            specialized_ast = None

            specialized = self.indent(specialized)
            specialized = "def func():\n" + specialized

            if replace_consts:
                specialized += ('\nfunc.__code__ = __fat__.replace_consts(func.__code__, %s)'
                                % replace_consts)

        code1, code2 = self.format_specialize(before, specialized, guards, template=template)

        tree1 = self.optimize(code1)
        tree2 = compile_ast(code2)
        if specialized_ast:
            # import, def func, _ast_optimized = func, [def func]
            node = tree2.body[3]
            assert node.body[0].value.n == 8421028141204
            node.body[:] = [specialized_ast]
        self.assertAstEqual(tree1, tree2)

    def check_builtin_func(self, func, source, specialized):
        self.check_func_specialize(source, specialized,
                                 guards=builtin_guards(func))


class FunctionsTests(BaseAstTests):
    def test_get_constant(self):
        def get_constant(source):
            filename = "test"
            tree = compile_ast_expr(source)
            tree = fatoptimizer.convert_const.ConvertConstant(filename).visit(tree)
            return fatoptimizer.tools.get_constant(tree)

        self.assertEqual(get_constant('True'), True)
        self.assertEqual(get_constant('False'), False)
        self.assertEqual(get_constant('None'), None)
        self.assertEqual(get_constant('1'), 1)
        self.assertEqual(get_constant(r'"unicode \u20ac"'), "unicode \u20ac")
        self.assertEqual(get_constant(r'b"bytes \xff"'), b"bytes \xff")
        self.assertEqual(get_constant('(1, 2, 3)'), (1, 2, 3))

        # unsupported types
        self.assertIs(get_constant('[1, 2]'), UNSET)
        self.assertIs(get_constant('{1, 2}'), UNSET)
        self.assertIs(get_constant('{"key": "value"}'), UNSET)

    def new_constant(self, value):
        node = ast.Num(n=1, lineno=1, col_offset=1)
        return fatoptimizer.tools._new_constant(node, value)

    def test_new_constant_primitive(self):
        self.assertAstEqual(self.new_constant(None),
                            compile_ast_expr('None'))
        self.assertAstEqual(self.new_constant(False),
                            compile_ast_expr('False'))
        self.assertAstEqual(self.new_constant(True),
                            compile_ast_expr('True'))
        self.assertAstEqual(self.new_constant(2),
                            compile_ast_expr('2'))
        self.assertAstEqual(self.new_constant(4.0),
                            compile_ast_expr('4.0'))
        self.assertAstEqual(self.new_constant(4.0j),
                            compile_ast_expr('4.0j'))
        self.assertAstEqual(self.new_constant("unicode \u20ac"),
                            compile_ast_expr(r'"unicode \u20ac"'))
        self.assertAstEqual(self.new_constant(b"bytes \xff"),
                            compile_ast_expr(r'b"bytes \xff"'))

    def test_new_constant_containers(self):
        self.assertAstEqual(self.new_constant((1, 2)),
                            compile_ast_expr('(1, 2)'))
        self.assertAstEqual(self.new_constant([1, 2]),
                            compile_ast_expr('[1, 2]'))
        self.assertAstEqual(self.new_constant({"key": "value"}),
                            compile_ast_expr('{"key": "value"}'))
        self.assertAstEqual(self.new_constant({"a": 1, "b": 2, "c": 3, "d": 4}),
                            compile_ast_expr(repr({"a": 1, "b": 2, "c": 3, "d": 4})))


class CallPureBuiltinTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        from fatoptimizer.builtins import add_pure_builtins
        add_pure_builtins(self.config)

    def test_builtin_abs(self):
        self.check_builtin_func('abs',
            'return abs(-3)',
            'return 3')

    def test_builtin_ascii(self):
        self.check_builtin_func('ascii',
            'return ascii(3)',
            'return "3"')

    def test_builtin_bool(self):
        self.check_builtin_func('bool',
            'return bool("x")',
            'return True')

    def test_builtin_bin(self):
        self.check_builtin_func('bin',
            'return bin(15)',
            'return "0b1111"')

    def test_builtin_bytes(self):
        self.check_builtin_func('bytes',
            "return bytes(b'abc')",
            "return b'abc'")

        self.check_builtin_func('bytes',
            "return bytes((65, 66, 67))",
            "return b'ABC'")

        self.check_dont_optimize_func("bytes('unicode')")

        self.check_dont_optimize_func("bytes((-1,))")

        self.check_dont_optimize_func("bytes((256,))")

    def test_builtin_chr(self):
        self.check_builtin_func('chr',
            'return chr(65)',
            'return "A"')

        self.check_dont_optimize_func('chr(-1)')
        self.check_dont_optimize_func('chr(0x110000)')

    def test_builtin_complex(self):
        self.check_builtin_func('complex',
            'return complex("1.0j")',
            'return 1.0j')

        self.check_builtin_func('complex',
            'return complex(3j)',
            'return 3j')

        self.check_builtin_func('complex',
            'return complex(0, 2)',
            'return 2j')

        self.check_dont_optimize_func("complex('xyz')")
        self.check_dont_optimize_func("complex('1.0', 2)")

    def test_builtin_dict(self):
        self.check_builtin_func('dict',
            "return dict(((1, 2), (3, 4)))",
            "return {1: 2, 3: 4}")

        self.check_builtin_func('dict',
            "return dict({1: 2, 3: 4})",
            "return {1: 2, 3: 4}")

        self.check_builtin_func('dict',
            "return dict()",
            "return {}")

        self.check_dont_optimize_func("dict({['list']: 'value'})")

    def test_builtin_divmod(self):
        self.check_builtin_func('divmod',
            'return divmod(100, 3)',
            'return (33, 1)')

        # division by zero
        self.check_dont_optimize_func("divmod(1, 0)")
        self.check_dont_optimize_func("divmod(2.0, 0.0)")

    def test_builtin_float(self):
        self.check_builtin_func('float',
            'return float("1.0")',
            'return 1.0')

        self.check_builtin_func('float',
            'return float(2)',
            'return 2.0')

        self.check_builtin_func('float',
            'return float(3.0)',
            'return 3.0')

        self.check_dont_optimize_func("float('xyz')")

    def test_builtin_frozenset(self):
        self.check_builtin_func('frozenset',
            "return frozenset(('abc',))",
            ast.Return(ast.Constant(value=frozenset(('abc',)))))

        self.check_builtin_func('frozenset',
            "return frozenset()",
            ast.Return(ast.Constant(value=frozenset())))

        self.check_dont_optimize_func('frozenset(([],))')

    def test_builtin_hex(self):
        self.check_builtin_func('hex',
            'return hex(16)',
            'return "0x10"')

    def test_builtin_int(self):
        self.check_builtin_func('int',
            'return int(123)',
            'return 123')

        self.check_builtin_func('int',
            'return int(123.0)',
            'return 123')

        self.check_builtin_func('int',
            'return int("123")',
            'return 123')

        self.check_dont_optimize_func("int(1j)")
        self.check_dont_optimize_func("int('xyz')")

    def test_builtin_len(self):
        self.check_builtin_func('len', 'return len("abc")', 'return 3')

    def test_builtin_list(self):
        self.check_builtin_func('list',
                                'return list("abc")',
                                'return ["a", "b", "c"]')

    def test_builtin_oct(self):
        self.check_builtin_func('oct',
            'return oct(83)',
            'return "0o123"')

    def test_builtin_ord(self):
        self.check_builtin_func('ord', 'return ord("A")', 'return 65')
        self.check_builtin_func('ord', 'return ord(b"A")', 'return 65')

        self.check_dont_optimize_func("ord(123)")
        self.check_dont_optimize_func("ord('')")
        self.check_dont_optimize_func("ord('xyz')")

    def test_builtin_max(self):
        self.check_builtin_func('max', 'return max(4, 6)', 'return 6')

        self.check_dont_optimize_func("max(b'bytes', 'unicode')")

    def test_builtin_min(self):
        self.check_builtin_func('min', 'return min(4, 6)', 'return 4')

        self.check_dont_optimize_func("min(b'bytes', 'unicode')")

    def test_builtin_repr(self):
        self.check_builtin_func('repr',
                                'return repr("abc")',
                                'return "\'abc\'"')

    def test_builtin_pow(self):
        # int
        self.check_builtin_func('pow',
            'return pow(2, 8)',
            'return 256')

        # float
        self.check_builtin_func('pow',
            'return pow(16.0, 0.5)',
            'return 4.0')

        # int modulo
        self.check_builtin_func('pow',
            'return pow(10, 3, 7)',
            'return 6')

    def test_builtin_round(self):
        self.check_builtin_func('round',
            'return round(1.5)',
            'return 2')

    def test_builtin_set(self):
        self.check_builtin_func('set',
            "return set(('abc',))",
            "return {'abc'}")

        self.check_dont_optimize_func('set(([],))')

    def test_builtin_str(self):
        self.check_builtin_func('str',
            'return str(123)',
            'return "123"')

        self.check_builtin_func('str',
            'return str("hello")',
            'return "hello"')

    def test_builtin_sum(self):
        self.check_builtin_func('sum',
            'return sum((1, 2, 3))',
            'return 6')

        self.check_dont_optimize_func('sum(([],))')

    def test_builtin_tuple(self):
        self.check_builtin_func('tuple',
            'return tuple("abc")',
            'return ("a", "b", "c")')

    def test_config_argtype(self):
        self.check_builtin_func('str',
            'return str(123)',
            'return "123"')

        self.config._pure_builtins['str'].arg_types = (str,)
        self.check_dont_optimize("""
            def func():
                return str(123)
        """)

    def test_pow_max_bits(self):
        self.config.max_int_bits = 16
        self.check_builtin_func('pow',
            'return pow(2, 15)',
            'return 32768')

        self.check_dont_optimize("""
            def func():
                return pow(2, 16)
        """)

        self.config.max_int_bits = 17
        self.check_builtin_func('pow',
            'return pow(2, 16)',
            'return 65536')

    def test_config_pure_builtins(self):
        self.check_builtin_func('str',
            'return str(123)',
            'return "123"')

        del self.config._pure_builtins['str']
        self.check_dont_optimize("""
            def func():
                return str(123)
        """)


class ConfigTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.constant_folding = True

    def test_config_max_int_bits(self):
        self.config.max_int_bits = 16
        self.check_optimize("""
            def func():
                return 1 << 15
        """, """
            def func():
                return 32768
        """)

        self.check_dont_optimize("""
            def func():
                return 1 << 16
        """)


    def test_config_max_bytes_len(self):
        self.config.max_bytes_len = 3
        self.check_optimize("""
            def func():
                return b'x' * 3
        """, """
            def func():
                return b'xxx'
        """)

        self.check_dont_optimize("""
            def func():
                return b'x' * 4
        """)

    def test_config_max_str_len(self):
        self.config.max_str_len = 3
        self.check_optimize("""
            def func():
                return 'x' * 3
        """, """
            def func():
                return 'xxx'
        """)

        self.check_dont_optimize("""
            def func():
                return 'x' * 4
        """)

    # FIXME: fix this test
    #def test_config_max_constant_size(self):
    #    size = fatoptimizer.tools.get_constant_size('abc')
    #    self.config.max_constant_size = size
    #    self.check_builtin_func('str',
    #        'return str(123)',
    #        'return "123"')

    #    self.config.max_constant_size = size - 1
    #    self.check_dont_optimize("""
    #        def func():
    #            return str(1234)
    #    """)


class OptimizerTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        from fatoptimizer.builtins import add_pure_builtins
        add_pure_builtins(self.config)

    def check_add_import(self, before='', after=''):
        template = ("""
            %s
            {import_fat}
            %s

            {code}
        """ % (after, before))


        code1 = textwrap.dedent("""
            def func():
                print(chr(65))
        """)

        code2 = """
            def func():
                print("A")
        """

        self.check_specialize(code1, code2,
                              guards=builtin_guards('chr'),
                              template=template)

    def test_add_import_after_docstring(self):
        self.check_add_import(after='"docstring"')

    def test_add_import_after_import_future(self):
        self.check_add_import(after='from __future__ import print_function')

    def test_add_import_before_import_sys(self):
        self.check_add_import(before='import sys')

    def test_builtin_chr(self):
        self.check_func_specialize(
            "return chr(65)",
            'return "A"',
            guards=builtin_guards('chr'))

    def test_reentrant_functiondef(self):
        # Test reentrant call to visit_FunctionDef() (func2()) when we already
        # decided to specialized the function func()
        self.check_func_specialize("""
            res = chr(65)

            def func2():
                return 2

            return res
        """, """
            res = "A"

            def func2():
                return 2

            return res
        """,
        guards=builtin_guards('chr'))

    def test_generic_visitor(self):
        # Test that visitor visits ast.Call arguments
        self.check_func_specialize("""
            print(chr(65))
        """, """
            print("A")
        """, guards=builtin_guards('chr'))

    def test_combined_called(self):
        # optimize str(obj) where obj is not a constant, but a call
        # which will be optimized to a constant
        self.check_func_specialize(
            'return str(ord("A"))',
            "return '65'",
            guards=builtin_guards('ord', 'str'))

    def test_duplicate_guards(self):
        # check that duplicated guards are removed
        self.check_func_specialize(
            "return ord('A') + ord('B')",
            "return 65 + 66",
            guards=builtin_guards('ord'))

    def test_decorator(self):
        # FIXME: support decorators
        self.check_dont_optimize("""
            @decorator
            def func():
                return ord('A')
        """)

    def test_method(self):
        template = format_code("""
            {import_fat}

            class MyClass:
                {code}
        """)

        self.check_specialize("""
            def func(self):
                return chr(65)
        """, """
            def func(self):
                return "A"
        """, guards=builtin_guards('chr'), template=template)

    def test_nested_functiondef(self):
        template = format_code("""
            {import_fat}

            def create_func():
                {code}

                return func
        """)

        self.check_specialize("""
            def func():
                return chr(65)
        """, """
            def func():
                return "A"
        """, guards=builtin_guards('chr'), template=template)


class OptimizerVariableTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        from fatoptimizer.builtins import add_pure_builtins
        add_pure_builtins(self.config)

    def test_global(self):
        template = format_code("""
            {import_fat}

            x = 1

            def create_func():
                x = 2
                {code}
        """)

        self.check_func_specialize("""
            global x
            return ord("A") + x
        """, """
            global x
            return 65 + x
        """, guards=builtin_guards('ord'), template=template)

    def test_late_global(self):
        template = format_code("""
            {import_fat}

            x = 1

            def create_func():
                x = 2
                {code}
        """)

        self.check_func_specialize("""
            copy_to_local = x
            global x
            return ord("A") + x
        """, """
            copy_to_local = x
            global x
            return 65 + x
        """, guards=builtin_guards('ord'), template=template)

    def test_assign(self):
        template = format_code("""
            {import_fat}

            def create_func():
                x = 1

                {code}
        """)

        self.check_func_specialize("""
            # assignement: x is local to nested
            x = 2
            return ord("A") + x
        """, """
            x = 2
            return 65 + x
        """, guards=builtin_guards('ord'), template=template)


class ReplaceVariableTests(BaseAstTests):
    def check_replace(self, name_mapping, source1, source2):
        tree1 = compile_ast(source1)
        filename = '<string>'
        replace = fatoptimizer.optimizer.ReplaceVariable(filename, name_mapping)
        tree1.body[0] = replace.replace_func_def(tree1.body[0])

        tree2 = compile_ast(source2)
        self.assertAstEqual(tree1, tree2)

    def test_replace(self):
        self.check_replace({'x': 7},
        """
            def func():
                x()
                return x
        """,
        """
            def func():
                7()
                return 7
        """)


    def test_list_comprehension(self):
        self.check_replace({'x': 7},
        """
            def func():
                y = x
                listcomp = [x() for i in range(3)]
                dictcomp = {x(): None for i in range(3)}
                setcomp = {x() for i in range(3)}
                gen = (x() for i in range(3))
                lam = lambda x: str(x)
        """,
        """
            def func():
                y = 7
                listcomp = [x() for i in range(3)]
                dictcomp = {x(): None for i in range(3)}
                setcomp = {x() for i in range(3)}
                gen = (x() for i in range(3))
                lam = lambda x: str(x)
        """)


class CopyBuiltinToConstantTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.copy_builtin_to_constant = True
        self.config._copy_builtin_to_constant.add('max')
        self.guards = builtin_guards('max')

    def test_simple(self):
        self.check_func_specialize("""
            return max(x, y)
        """, """
            return 'LOAD_GLOBAL max'(x, y)
        """,
        self.guards,
        replace_consts="{'LOAD_GLOBAL max': max}")

    def test_called_twice(self):
        self.check_func_specialize("""
            a = max(x, y)
            b = max(x, y)
        """, """
            a = 'LOAD_GLOBAL max'(x, y)
            b = 'LOAD_GLOBAL max'(x, y)
        """,
        self.guards,
        replace_consts="{'LOAD_GLOBAL max': max}")

    def test_disabled(self):
        self.config.copy_builtin_to_constant = False
        self.check_dont_optimize("""
            def func(x, y):
                return max(x, y)
        """)

    def test_global(self):
        # don't optimize because global 'max' name is overriden
        self.check_dont_optimize("""
            def func(x, y):
                # don't do that at home, kids!
                global max
                max = min
                return max(x, y)
        """)

    def test_local_name(self):
        self.check_func_specialize("""
            global_max = 1
            return max(x, y)
        """, """
            global_max = 1
            return 'LOAD_GLOBAL max'(x, y)
        """,
        self.guards,
        replace_consts="{'LOAD_GLOBAL max': max}")

        self.check_func_specialize("""
            global_max = 1
            global_max2 = 2
            return max(x, y)
        """, """
            global_max = 1
            global_max2 = 2
            return 'LOAD_GLOBAL max'(x, y)
        """,
        self.guards,
        replace_consts="{'LOAD_GLOBAL max': max}")

    # FIXME: specialize nested function?
    #def test_nested_func_before(self):
    #    self.config._copy_builtin_to_constant.add('int')
    #    self.check_optimize("""
    #        def func():
    #            def func2(x):
    #                return int(x)

    #            y = func2(4)
    #            return int(y)
    #    """, """
    #        import fat as __fat__

    #        def func():
    #            def func2(x):
    #                return int(x)

    #            y = func2(4)
    #            return int(y)

    #        _ast_optimized = func
    #        def func():
    #            def func2(x):
    #                return int(x)
    #            _ast_optimized = func2
    #            def func2(x):
    #                return 'LOAD_GLOBAL int'(x)

    #            func2.__code__ = __fat__.replace_consts(func2.__code__, {{'LOAD_GLOBAL int': 'LOAD_GLOBAL int#2'}})

    #            __fat__.specialize(_ast_optimized, func2.__code__, {guards})
    #            func2 = _ast_optimized
    #            del _ast_optimized

    #            y = func2(4)
    #            return 'LOAD_GLOBAL int#2'(y)

    #        func.__code__ = __fat__.replace_consts(func.__code__, {{'LOAD_GLOBAL int#2': int}})
    #        __fat__.specialize(_ast_optimized, func.__code__, {guards})
    #        func = _ast_optimized
    #        del _ast_optimized
    #    """.format(guards=builtin_guards('int')))

    # FIXME: specialize nested function?
    #def test_nested_func_after(self):
    #    self.config._copy_builtin_to_constant.add('len')
    #    self.check_optimize("""
    #        def func(arg):
    #            len(arg)

    #            def func2(x):
    #                len(x)
    #    """, """
    #        import fat as __fat__

    #        def func(arg):
    #            len(arg)

    #            def func2(x):
    #                len(x)

    #        _ast_optimized = func
    #        def func(arg):
    #            'LOAD_GLOBAL len'(arg)

    #            def func2(x):
    #                len(x)
    #            _ast_optimized = func2
    #            def func2(x):
    #                'LOAD_GLOBAL len#2'(x)

    #            func2.__code__ = __fat__.replace_consts(func2.__code__, {{'LOAD_GLOBAL len#2': 'LOAD_GLOBAL len'}})
    #            __fat__.specialize(_ast_optimized, func2.__code__, {guards})
    #            func2 = _ast_optimized
    #            del _ast_optimized

    #        func.__code__ = __fat__.replace_consts(func.__code__, {{'LOAD_GLOBAL len': len}})
    #        __fat__.specialize(_ast_optimized, func.__code__, {guards})
    #        func = _ast_optimized
    #        del _ast_optimized
    #    """.format(guards=builtin_guards('len')))

    def test_repr_global(self):
        # In func()/method(), repr() builtin cannot be copied to constant,
        # because the call to __fat__.replace_consts(func.__code__, {'...': repr}) would
        # load the local repr() function instead of the builtin repr()
        # function.
        self.config._copy_builtin_to_constant.add('repr')

        self.check_dont_optimize("""
            def repr(obj):
                return 'local'

            def func(obj):
                return repr(obj)
        """)

        self.check_dont_optimize("""
            class MyClass:
                @staticmethod
                def repr(obj):
                    return 'local'

                def method(self, obj):
                    return repr(obj)
        """)

    def test_local_func(self):
        self.config._copy_builtin_to_constant.add('sum')
        self.check_dont_optimize("""
            def func():
                def sum(*args):
                    return local

                return sum([1, 2, 3])
        """)

    def test_super(self):
        self.config._copy_builtin_to_constant.add('super')
        self.check_dont_optimize("""
            class MyClass(ParentClass):
                def method(self):
                    super().method()
        """)


class UnrollLoopTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.unroll_loops = 16

    def test_unroll_tuple(self):
        self.check_optimize("""
            def func():
                for i in (True, 3, "text"):
                    print(i)
        """, """
            def func():
                i = True
                print(i)

                i = 3
                print(i)

                i = "text"
                print(i)
        """)

    def test_unroll_tuple(self):
        self.check_optimize("""
            def func():
                for i in (
                    (True, 'a'),
                    (False, 'b'),
                ):
                    print(i)
        """, """
            def func():
                i = (True, 'a')
                print(i)

                i = (False, 'b')
                print(i)
        """)

    def test_not_builtin_range(self):
        self.check_dont_optimize("""
            range = lambda x: (x,)

            def func():
                for i in range(2):
                    print(i)
        """)

        self.check_dont_optimize("""
            def func():
                range = lambda x: (x,)

                for i in range(2):
                    print(i)
        """)

    def test_not_range_int(self):
        self.check_dont_optimize("""
            def func():
                for i in range(2.0):
                    print(i)
        """)

    def test_unroll_range(self):
        self.config.simplify_iterable = True
        self.check_builtin_func('range', """
            for i in range(2):
                print(i)
        """, """
            i = 0
            print(i)

            i = 1
            print(i)
        """)

    def test_else(self):
        self.check_optimize("""
            def func():
                for i in (3,):
                    print(i)
                else:
                    print("else")
        """, """
            def func():
                i = 3
                print(i)

                print("else")
        """)

    def test_dont_optimize(self):
        self.check_dont_optimize("""
            def func():
                for i in range(3):
                    print(i)
                    break
        """)

        self.check_dont_optimize("""
            def func():
                for i in range(3):
                    print(i)
                    continue
        """)

        self.check_dont_optimize("""
            def func():
                for i in range(3):
                    if i == 1:
                        raise ValueError
                    print(i)
        """)


class UnrollComprehensionTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.unroll_loops = 16
        self.config.constant_folding = True

    def test_config_disable(self):
        self.config.unroll_loops = 0
        self.check_dont_optimize('[i for i in (1, 2, 3)]')

    def test_config_max_loops(self):
        self.config.unroll_loops = 3
        self.check_optimize('[i for i in (1, 2, 3)]',
                            '[1, 2, 3]')
        self.check_dont_optimize('[i for i in (1, 2, 3, 4)]')

    def test_listcomp(self):
        self.check_optimize('[i for i in (1, 2, 3)]',
                            '[1, 2, 3]')
        self.check_optimize('[i*2 for i in "abc"]',
                            '["aa", "bb", "cc"]')

    def test_setcomp(self):
        self.check_optimize('{i for i in (1, 2, 3)}',
                            '{1, 2, 3}')
        self.check_optimize('{i*2 for i in "abc"}',
                            '{"aa", "bb", "cc"}')

    def test_dictcomp(self):
        self.check_optimize('{i:i for i in (1, 2, 3)}',
                            '{1: 1, 2: 2, 3: 3}')
        self.check_optimize('{i:i*2 for i in (1, 2, 3)}',
                            '{1: 2, 2: 4, 3: 6}')


class NodeVisitorTests(BaseAstTests):
    def check_call_visitor(self, visitor):
        tree = ast.parse("1+1")
        with self.assertRaises(Exception) as cm:
            visitor.visit(tree)

        binop = tree.body[0].value
        what = ast.dump(binop)
        self.assertEqual(str(cm.exception),
                         'error at <string>:1 on visiting %s: bug' % what)

        # Test truncature of the AST dump
        with mock.patch('fatoptimizer.tools.COMPACT_DUMP_MAXLEN', 5):
            with self.assertRaises(Exception) as cm:
                visitor.visit(tree)

            what = 'BinOp(...)'
            self.assertEqual(str(cm.exception),
                             'error at <string>:1 on visiting %s: bug' % what)

    def test_visitor_call_visitor(self):
        class BuggyVisitor(fatoptimizer.tools.NodeVisitor):
            def visit_Module(self, node):
                # visit_Module() calls indirectly visit_BinOp(),
                # but the exception must only be wrapped once
                self.generic_visit(node)

            def visit_BinOp(self, node):
                raise Exception("bug")

        visitor = BuggyVisitor("<string>")
        self.check_call_visitor(visitor)

    def test_transformer_call_visitor(self):
        class BuggyTransformer(fatoptimizer.tools.NodeTransformer):
            def visit_Module(self, node):
                # visit_Module() calls indirectly visit_BinOp(),
                # but the exception must only be wrapped once
                self.generic_visit(node)

            def visit_BinOp(self, node):
                raise Exception("bug")

        visitor = BuggyTransformer("<string>")
        self.check_call_visitor(visitor)

    def check_pass_optimizer_error(self, visitor):
        tree = ast.parse("1+1")
        with self.assertRaises(fatoptimizer.OptimizerError) as cm:
            # visit() must not wrap OptimizerError into a generic Exception
            visitor.visit(tree)

    def test_visitor_pass_optimizer_error(self):
        class BuggyVisitor(fatoptimizer.tools.NodeVisitor):
            def visit_Module(self, node):
                # visit_Module() calls indirectly visit_BinOp()
                self.generic_visit(node)

            def visit_BinOp(self, node):
                raise fatoptimizer.OptimizerError

        visitor = BuggyVisitor("<string>")
        self.check_pass_optimizer_error(visitor)

    def test_transformer_pass_optimizer_error(self):
        class BuggyTransformer(fatoptimizer.tools.NodeTransformer):
            def visit_Module(self, node):
                # visit_Module() calls indirectly visit_BinOp()
                self.generic_visit(node)

            def visit_BinOp(self, node):
                raise fatoptimizer.OptimizerError

        visitor = BuggyTransformer("<string>")
        self.check_pass_optimizer_error(visitor)


class NamespaceTests(BaseAstTests):
    def get_namespace(self, code):
        filename = "test"

        tree = compile_ast(code)
        tree = fatoptimizer.convert_const.ConvertConstant(filename).visit(tree)

        self.assertIsInstance(tree, ast.Module)
        func_def = tree.body[0]
        self.assertIsInstance(func_def, ast.FunctionDef)

        parent = fatoptimizer.optimizer.Optimizer(self.config, filename)
        optimizer = fatoptimizer.optimizer.FunctionOptimizerStage1(self.config, filename, parent=parent)
        optimizer.optimize(func_def)
        return optimizer.namespace

    def check_namespace(self, code, expected):
        ns = self.get_namespace(code)
        self.assertEqual(ns._variables, expected)
        self.assertFalse(ns._unknown_state)

    def check_unknown_namespace(self, code):
        ns = self.get_namespace(code)
        self.assertTrue(ns._unknown_state, ns._variables)
        self.assertEqual(ns._variables, {})

    def test_assign(self):
        code = """
            def func():
                x = 1
        """
        self.check_namespace(code, {'x': 1})

    def test_assign_attr(self):
        code = """
            def func(obj):
                x = obj
                x.y = 2
        """
        self.check_namespace(code, {'x': UNSET})

        code = """
            def func(obj):
                obj.attr = 1
                x = 1
                return x
        """
        self.check_namespace(code, {'obj': UNSET, 'x': 1})

        code = """
            def func(obj, value):
                obj.attr = value
                x = 1
                return x
        """
        self.check_namespace(code, {'obj': UNSET, 'x': 1})

    def test_assign_subscript(self):
        code = """
            def func(obj):
                x = obj
                x[:3] = 2
        """
        self.check_namespace(code, {'x': UNSET})

    def test_aug_assign(self):
        code = """
            def func():
                x = 5
                x += 5
        """
        self.check_namespace(code, {'x': UNSET})

    def test_aug_assign_attr(self):
        code = """
            def func(obj):
                x = obj
                x.y += 7
        """
        self.check_namespace(code, {'x': UNSET})

    def test_for(self):
        code = """
            def func(obj):
                for x in obj:
                    y = 1
                else:
                    z = 3
        """
        self.check_namespace(code, {'x': UNSET, 'y': UNSET, 'z': UNSET})

    def test_while(self):
        code = """
            def func(obj):
                while obj:
                    obj.method()
                    x = 1
                else:
                    y = 2
        """
        self.check_namespace(code, {'x': UNSET, 'y': UNSET})

    def test_loop_unrolling(self):
        self.config.unroll_loops = 16
        code = """
            def func():
                for x in (5,):
                    pass
        """
        self.check_namespace(code, {'x': 5})

    def test_function_def(self):
        code = """
            def func():
                def g():
                    pass
        """
        self.check_namespace(code, {'g': UNSET})

    @need_python35
    def test_async_function_def(self):
        code = """
            def func():
                async def g():
                    pass
        """
        self.check_namespace(code, {'g': UNSET})

    def test_class_def(self):
        code = """
            def func():
                class MyClass:
                    pass
        """
        self.check_namespace(code, {'MyClass': UNSET})

    def test_with(self):
        code = """
            def func(cb, cb2, f):
                with cb() as (a, b), cb2() as c, f:
                    pass
        """
        self.check_namespace(code, {'a': UNSET, 'b': UNSET, 'c': UNSET})

        code = """
            def func(cb):
                with cb() as (a, *b):
                    pass
        """
        self.check_namespace(code, {'a': UNSET, 'b': UNSET})

    def test_import(self):
        code = """
            def func():
                import sys
                import os.path
                import posix as _posix
        """
        self.check_namespace(code, {'sys': UNSET, 'os': UNSET, '_posix': UNSET})

    def test_import_from(self):
        code = """
            def func():
                from sys import ps1
                from os.path import exists as path_exists
        """
        self.check_namespace(code, {'ps1': UNSET, 'path_exists': UNSET})

    def test_delete(self):
        code = """
            def func():
                x = 1
                del x
        """
        self.check_namespace(code, {})

        code = """
            def func():
                x = 1
                y = 2
                z = 3
                del x, y
        """
        self.check_namespace(code, {'z': 3})

        code = """
            def func():
                a = 1
                b = 2
                c = 3
                d = 4
                del (a, b), c
        """
        self.check_namespace(code, {'d': 4})

    def test_cond_delete(self):
        code = """
            def func(cb):
                x = 1
                try:
                    cb()
                    del x
                finally:
                    pass
        """
        self.check_namespace(code, {'x': UNSET})

    def test_if(self):
        code = """
            def func(cond):
                if cond:
                    x = 1
                else:
                    x = 2
                return x
        """
        self.check_namespace(code, {'x': UNSET})

    def test_nested_cond_block(self):
        code = """
            def func(cond, cond2):
                if cond:
                    if cond2:
                        x = 1
                    else:
                        x = 2
                else:
                    x = 3
                return x
        """
        self.check_namespace(code, {'x': UNSET})

    def test_try(self):
        # try/except
        code = """
            def func(cb):
                try:
                    cb()
                    x = 1
                except:
                    x = 2
        """
        self.check_namespace(code, {'x': UNSET})

        # try/except/finally
        code = """
            def func(cb):
                try:
                    cb()
                    x = 1
                except:
                    x = 2
                finally:
                    x = 3
        """
        self.check_namespace(code, {'x': 3})

        # try/except/else/finally
        code = """
            def func(cb):
                try:
                    cb()
                    x = 1
                except:
                    x = 2
                else:
                    x = 3
                finally:
                    x = 4
        """
        self.check_namespace(code, {'x': 4})

        # try/finally
        code = """
            def func(cb):
                try:
                    cb()
                    x = 1
                finally:
                    x = 3
        """
        self.check_namespace(code, {'x': 3})

        # try/finally
        code = """
            def func(cb):
                try:
                    cb()
                    x = 1
                finally:
                    x = 3
        """
        self.check_namespace(code, {'x': 3})


class ConstantPropagationTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.constant_propagation = True

    def test_module(self):
        # optimization must also work at the module scope
        self.check_optimize("""
            x = 1
            y = x
        """, """
            x = 1
            y = 1
        """)

    def test_basic(self):
        self.check_optimize("""
            def func():
                x = 1
                y = x
                return y
        """, """
            def func():
                x = 1
                y = 1
                return 1
        """)

    def test_assign_targets(self):
        self.check_optimize("""
            def func():
                x = y = 1
                return (x, y)
        """, """
            def func():
                x = y = 1
                return (1, 1)
        """)

    def test_tuple(self):
        self.check_optimize("""
            def func():
                x = (8, 9)
                y = x
                return y
        """, """
            def func():
                x = (8, 9)
                y = (8, 9)
                return (8, 9)
        """)

    def test_with(self):
        self.check_dont_optimize("""
            def func():
                x = 1
                with func2() as x:
                    pass
                return x
        """)

    def test_for(self):
        self.check_dont_optimize("""
            i = 0
            for x in (3, 5):
                i = i + 1
            y = i
        """)

        self.check_dont_optimize("""
            def func():
                i = 0
                for x in (3, 5):
                    i = i + 1
                return i
        """)

    def test_while(self):
        self.check_optimize("""
            i = 0
            y = i
            while i < 10:
                i = i + 1
            z = i
        """, """
            i = 0
            y = 0
            while i < 10:
                i = i + 1
            z = i
        """)

        self.check_optimize("""
            def func():
                i = 0
                y = i
                while i < 10:
                    i = i + 1
                z = i
        """, """
            def func():
                i = 0
                y = 0
                while i < 10:
                    i = i + 1
                z = i
        """)

    def test_delete(self):
        self.check_dont_optimize("""
            def func():
                x = 0
                del x
                return x
        """)

    def test_constant_folding(self):
        # Test constant propagation + constant folding
        self.config.constant_folding = True
        self.check_optimize("""
            def func():
                x = 1
                y = x + 1
                return y
        """, """
            def func():
                x = 1
                y = 2
                return 2
        """)

    def test_complex_assign(self):
        self.check_dont_optimize("""
            def func(x):
                x.y().z = 1
                return x
        """)

        self.check_dont_optimize("""
            def func(x):
                x.attr = 1
                return x
        """)

        self.check_dont_optimize("""
            def func():
                x, *y = (1, 2)
                return x, y
        """)


class BaseConstantFoldingTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.constant_folding = True


class ConstantFoldingBinOpTests(BaseConstantFoldingTests):
    def test_disabled(self):
        self.check_optimize_func("1 + 1", "2")

        self.config.constant_folding = False
        self.check_dont_optimize_func("1 + 1")

    def test_not_constant(self):
        self.check_dont_optimize_func("x + 1")
        self.check_dont_optimize_func("1 + x")

    def test_shift_error(self):
        self.check_dont_optimize_func("1 << -3",
                                 ast.BinOp(left=ast.Num(n=1), op=ast.LShift(), right=ast.Num(-3)))
        self.check_dont_optimize_func("1 >> -3",
                                 ast.BinOp(left=ast.Num(n=1), op=ast.RShift(), right=ast.Num(-3)))

    def test_float_binopts(self):
        self.check_dont_optimize_func('1.0 << 2')
        self.check_dont_optimize_func('1.0 >> 2')
        self.check_dont_optimize_func('1.0 & 2')
        self.check_dont_optimize_func('1.0 | 2')
        self.check_dont_optimize_func('1.0 ^ 2')

    def test_complex_binopts(self):
        self.check_dont_optimize_func('1.0j ** 2')
        self.check_dont_optimize_func('1.0j // 2')
        self.check_dont_optimize_func('1.0j % 2')
        self.check_dont_optimize_func('1.0j << 2')
        self.check_dont_optimize_func('1.0j >> 2')
        self.check_dont_optimize_func('1.0j & 2')
        self.check_dont_optimize_func('1.0j | 2')
        self.check_dont_optimize_func('1.0j ^ 2')

    def test_division_by_zero(self):
        self.check_dont_optimize_func("1 // 0")
        self.check_dont_optimize_func("1.0 // 0.0")

        self.check_dont_optimize_func("1 / 0")
        self.check_dont_optimize_func("1.0 / 0.0")
        self.check_dont_optimize_func("1.0j / 0.0j")

    def test_formatting(self):
        # FIXME: optimize bytes%args and str%args
        self.check_dont_optimize_func("b'hello %s' % b'world'")
        self.check_dont_optimize_func("'hello %s' % 'world'")

    def test_add(self):
        self.check_optimize_func("2 + 3", "5")
        self.check_optimize_func("2.0 + 3.0", "5.0")
        self.check_optimize_func("2.0j + 3.0j", "5.0j")
        self.check_optimize_func("(1, 2) + (3,)", "(1, 2, 3)")

        self.config.max_str_len = 2
        self.check_optimize_func("'a' + 'b'", "'ab'")
        self.check_dont_optimize_func("'a' + 'bc'")

        self.config.max_bytes_len = 2
        self.check_optimize_func("b'a' + b'b'", "b'ab'")
        self.check_dont_optimize_func("b'a' + b'bc'")

    def test_sub(self):
        self.check_optimize_func("3 - 2", "1")
        self.check_optimize_func("3.0 - 2.0", "1.0")
        self.check_optimize_func("3.0j - 2.0j", "1.0j")

    def test_mul(self):
        self.check_optimize_func("2 * 3", "6")
        self.check_optimize_func("2.0 * 3.0", "6.0")
        self.check_optimize_func("2.0j * 3.0", "6j")

        self.check_optimize_func("'a' * 3", "'aaa'")
        self.check_optimize_func("b'x' * 3", "b'xxx'")
        self.check_optimize_func("(1, 2) * 2", "(1, 2, 1, 2)")

        self.check_optimize_func("3 * 'a'", "'aaa'")
        self.check_optimize_func("3 * b'x'", "b'xxx'")
        self.check_optimize_func("2 * (1, 2)", "(1, 2, 1, 2)")

    def test_floor_div(self):
        self.check_optimize_func("10 // 3", "3")
        self.check_optimize_func("10.0 // 3.0", "3.0")

    def test_div(self):
        self.check_optimize_func("5 / 2", "2.5")
        self.check_optimize_func("5.0 / 2.0", "2.5")
        self.check_optimize_func("5.0j / 2.0", "2.5j")

    def test_mod(self):
        self.check_optimize_func("5 % 2", "1")
        self.check_optimize_func("5.0 % 2.0", "1.0")

    def test_pow(self):
        self.check_optimize_func("2 ** 3", "8")
        self.check_optimize_func("2.0 ** 3.0", "8.0")

        # complex
        self.check_dont_optimize_func("2.0j ** 3.0")
        self.check_dont_optimize_func("2.0 ** 3.0j")

        # 0 ** -1
        self.check_dont_optimize_func("0 ** -1",
                                 ast.BinOp(left=ast.Num(n=0), op=ast.Pow(), right=ast.Num(-1)))
        self.check_dont_optimize_func("0.0 ** -1",
                                 ast.BinOp(left=ast.Num(n=0.0), op=ast.Pow(), right=ast.Num(-1)))

    def test_pow_max_int_bits(self):
        self.config.max_int_bits = 16
        self.check_optimize_func('2 ** 15', '32768')
        self.check_dont_optimize_func("2 ** 16")

        self.config.max_int_bits = 17
        self.check_optimize_func('2 ** 15', '32768')

    def test_shift(self):
        self.check_optimize_func("1 << 3", "8")
        self.check_optimize_func("16 >> 2", "4")

    def test_bits(self):
        self.check_optimize_func("3 & 1", "1")
        self.check_optimize_func("1 | 2", "3")
        self.check_optimize_func("3 ^ 3", "0")


class ConstantFoldingUnaryOpTests(BaseConstantFoldingTests):
    def test_not_constant(self):
        self.check_dont_optimize_func("-x")
        self.check_dont_optimize_func("+x")
        self.check_dont_optimize_func("~x")
        self.check_dont_optimize_func("not x")

    def test_uadd(self):
        self.check_optimize_func("+3", "3")
        self.check_optimize_func("+3.0", "3.0")
        self.check_optimize_func("+3.0j", "3.0j")
        self.check_dont_optimize_func("+'abc'")

    def test_usub(self):
        self.check_optimize_func("-3", ast.Num(n=-3))
        self.check_optimize_func("-3.0", ast.Num(n=-3.0))
        self.check_optimize_func("-3.0j", ast.Num(n=-3.0j))
        self.check_dont_optimize_func("-'abc'")

    def test_invert(self):
        self.check_optimize_func("~3", ast.Num(n=-4))
        self.check_dont_optimize_func("~3.0")
        self.check_dont_optimize_func("~3.0j")
        self.check_dont_optimize_func("~'abc'")

    def test_not(self):
        self.check_optimize_func("not 3", "False")
        self.check_optimize_func("not 3.0", "False")
        self.check_optimize_func("not 3.0j", "False")
        self.check_dont_optimize_func("not 'abc'")

    def test_not_compare(self):
        self.check_optimize_func("not(x is y)", "x is not y")
        self.check_optimize_func("not(x is not y)", "x is y")

        self.check_optimize_func("not(x in y)", "x not in y")
        self.check_optimize_func("not(x not in y)", "x in y")

        self.check_dont_optimize_func("not(x < y)")
        self.check_dont_optimize_func("not(x <= y)")
        self.check_dont_optimize_func("not(x > y)")
        self.check_dont_optimize_func("not(x >= y)")

        self.check_dont_optimize_func("not(x == y)")
        self.check_dont_optimize_func("not(x != y)")

        self.check_dont_optimize_func("not(x < y < y)")

class ConstantFoldingSubscritTests(BaseConstantFoldingTests):
    def test_not_constant(self):
        self.check_dont_optimize_func("x[k]")
        self.check_dont_optimize_func("'abc'[k]")
        self.check_dont_optimize_func("x[0]")
        self.check_dont_optimize_func("x[0:stop]")
        self.check_dont_optimize_func("x[start:10]")
        self.check_dont_optimize_func("x[:10]")

    def test_subscript_index(self):
        self.check_optimize_func("'abc'[0]", "'a'")
        self.check_optimize_func("'abc'[-2]", "'b'")
        self.check_optimize_func("'abcde'[::2]", "'ace'")

        self.check_optimize_func("b'ABC'[0]", "65")
        self.check_optimize_func("(10, 20, 30, 40)[-1]", "40")

        # list
        self.check_optimize_func("[10, 20, 30][0]", "10")

        # dict with int and str keys
        self.check_optimize_func("{9: 'x', 3: 'y'}[9]", "'x'")
        self.check_optimize_func("{'x': 9, 'y': 3}['x']", "9")

        # don't optimize
        self.check_dont_optimize_func("2[1]")
        self.check_dont_optimize_func("'abc'[1.0]")
        self.check_dont_optimize_func("{10, 20, 30}[1]")
        self.check_dont_optimize_func("{1: 2, 3: 4}[['x']]")  # list key
        self.check_dont_optimize_func("{1: 2}[8]")  # KeyError

    def test_subscript_slice(self):
        self.check_optimize_func("'abc'[:2]", "'ab'")
        self.check_optimize_func("'abc'[-2:]", "'bc'")
        self.check_optimize_func("b'ABC'[:2]", "b'AB'")
        self.check_optimize_func("(10, 20, 30, 40)[:2]", "(10, 20)")

        # list
        self.check_optimize_func("[10, 20, 30][:2]", "[10, 20]")

        # wrong types
        self.check_dont_optimize_func("'abc'[1.0:]")
        self.check_dont_optimize_func("'abc'[:2.0]")
        self.check_dont_optimize_func("'abc'[::3.0]")
        self.check_dont_optimize_func("{10, 20, 30}[:2]")
        self.check_dont_optimize_func("{1:2, 3:4}[:2]")


class ConstantFoldingCompareTests(BaseConstantFoldingTests):
    def test_not_constant(self):
        self.check_dont_optimize_func("a in b")
        self.check_dont_optimize_func("'x' in b")
        self.check_dont_optimize_func("a in 'xyz'")

        self.check_dont_optimize_func("a < b")
        self.check_dont_optimize_func("'x' < b")
        self.check_dont_optimize_func("a < 'xyz'")

    def test_contains_type_error(self):
        self.check_dont_optimize_func("1 in 'abc'")
        self.check_dont_optimize_func("'x' in 2")
        self.check_dont_optimize_func("b'bytes' in 'unicode'")
        self.check_dont_optimize_func("'unicode' in b'bytes'")

    def test_contains(self):
        # str
        self.check_optimize_func("'a' in 'abc'", "True")
        self.check_optimize_func("'a' not in 'abc'", "False")

        # bytes
        self.check_optimize_func("65 in b'ABC'", "True")

        # tuple
        self.check_optimize_func("2 in (1, 2, 3)", "True")
        self.check_optimize_func("2 not in (1, 2, 3)", "False")

        # list
        self.check_optimize_func("2 in [1, 2, 3]", "True")

        # set
        self.check_optimize_func("2 in {1, 2, 3}", "True")

    def test_compare(self):
        self.check_optimize_func("1 < 2", "True")
        self.check_optimize_func("1 <= 2", "True")
        self.check_optimize_func("1 == 2", "False")
        self.check_optimize_func("1 != 2", "True")
        self.check_optimize_func("1 > 2", "False")
        self.check_optimize_func("1 >= 2", "False")

        # comparison between bytes and str can raise BytesWarning depending
        # on runtime option
        self.check_dont_optimize_func('"x" == b"x"')
        self.check_dont_optimize_func('b"x" == "x"')
        self.check_dont_optimize_func('"x" != b"x"')
        self.check_dont_optimize_func('b"x" != "x"')

        # bytes < str raises TypeError
        self.check_dont_optimize_func('b"bytes" < "str"')

    def test_is(self):
        self.check_optimize_func("None is None", "True")

    def test_contains_to_const(self):
        # list => tuple
        self.check_optimize_func("x in [1, 2]", "x in (1, 2)")

        # set => frozenset
        const = ast.Constant(value=frozenset({1, 2}))
        node = ast.Compare(left=ast.Name(id='x', ctx=ast.Load()),
                           ops=[ast.In()],
                           comparators=[const])
        self.check_optimize_func("x in {1, 2}", node)

        # [] is not a constant: don't optimize
        self.check_dont_optimize_func("x in [1, [], 2]")
        self.check_dont_optimize_func("x in {1, [], 2}")


class ConstantFoldingCondBlock(BaseConstantFoldingTests):
    def test_if(self):
        self.check_optimize("""
            if test:
                x = 1 + 1
            else:
                x = 2 + 2
        """, """
            if test:
                x = 2
            else:
                x = 4
        """)

    def test_for(self):
        self.check_optimize("""
            for i in range(5):
                i += 1 + 1
        """, """
            for i in range(5):
                i += 2
        """)

    def test_while(self):
        self.check_optimize("""
            x = 0
            while x < 2:
                x += 1 +1
        """, """
            x = 0
            while x < 2:
                x += 2
        """)

    def test_try(self):
        self.check_optimize("""
            try:
                x = 1 + 1
            except:
                x = 2 + 2
            else:
                x = 3 + 3
            finally:
                x = 4 + 4
        """, """
            try:
                x = 2
            except:
                x = 4
            else:
                x = 6
            finally:
                x = 8
        """)


class NewOptimizerTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.constant_propagation = True
        self.config.constant_folding = True

    def test_FunctionDef(self):
        self.check_optimize("""
            x = 1
            def func():
                return 2 + 3 + x
        """, """
            x = 1
            def func():
                return 5 + x
        """)

    @need_python35
    def test_AsyncFunctionDef(self):
        self.check_optimize("""
            x = 1
            async def func():
                return 2 + 3 + x
        """, """
            x = 1
            async def func():
                return 5 + x
        """)

    def test_ClassDef(self):
        self.check_optimize("""
            x = 1
            class MyClass:
                y = 2 + 3 + x
        """, """
            x = 1
            class MyClass:
                y = 5 + x
        """)

    def test_DictComp(self):
        self.check_optimize("""
            x = 1
            y = {k: 2 + 3 + x for k in "abc"}
        """, """
            x = 1
            y = {k: 5 + x for k in "abc"}
        """)

    def test_ListComp(self):
        self.check_optimize("""
            x = 1
            y = [2 + 3 + x for k in "abc"]
        """, """
            x = 1
            y = [5 + x for k in "abc"]
        """)

    def test_SetComp(self):
        self.check_optimize("""
            x = 1
            y = {2 + 3 + x for k in "abc"}
        """, """
            x = 1
            y = {5 + x for k in "abc"}
        """)

    def test_GeneratorExp(self):
        self.check_optimize("""
            x = 1
            y = (2 + 3 + x for k in "abc")
        """, """
            x = 1
            y = (5 + x for k in "abc")
        """)

    def test_Lambda(self):
        self.check_optimize("""
            x = 1
            y = lambda: 2 + 3 + x
        """, """
            x = 1
            y = lambda: 5 + x
        """)


class ReplaceBuiltinConstantTests(BaseAstTests):
    def test_constants(self):
        self.config.replace_builtin_constant = True
        self.check_optimize("__debug__", str(__debug__))

        self.config.replace_builtin_constant = False
        self.check_dont_optimize("__debug__")


class RemoveDeadCodeConstantTestTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.remove_dead_code = True

    def test_config(self):
        self.config.remove_dead_code = False
        self.check_dont_optimize("if False: x = 1")

    def test_if(self):
        self.check_optimize("if False: x = 1", "pass")
        self.check_optimize("if True: x = 1", "x = 1")

        self.check_dont_optimize("""
            def func():
                if 0:
                    yield
        """)

    def test_if_else(self):
        self.check_optimize("""
            if True:
                x = 1
            else:
                x = 2
        """, """
            x = 1
        """)
        self.check_optimize("""
            if False:
                x = 1
            else:
                y = 2
        """, """
            y = 2
        """)

    def test_while(self):
        self.check_optimize("while 0: x = 1", "pass")

        self.check_dont_optimize("while 1: x = 1")

    def test_while_else(self):
        self.check_optimize("""
            while 0:
                x = 1
            else:
                y = 2
        """, """
            y = 2
        """)

    def test_return(self):
        self.check_optimize("""
            def func():
                x = 1
                return 1
                return 2
        """, """
            def func():
                x = 1
                return 1
        """)

        self.check_dont_optimize("""
            def func(obj):
                return
                if 0:
                    yield from obj
        """)

    def test_return_logger(self):
        self.config.logger = io.StringIO()

        def get_logs():
            logger = self.config.logger
            logger.seek(0)
            return logger.readlines()

        self.check_optimize("""
            def func():
                x = 1
                return 1
                return 2
        """, """
            def func():
                x = 1
                return 1
        """)

        self.assertEqual(get_logs(),
                         ['<string>:4: fatoptimizer: Remove unreachable code: '
                          'Return(value=Constant(value=2))\n'])

    def test_try_dont_remove(self):
        self.check_dont_optimize("""
            try:
                pass
            except Exception:
                yield 3
        """)

    def test_try_dont_remove_illegal(self):
        # must raise SyntaxError
        self.check_dont_optimize("""
            for x in (1, 2):
                try:
                    pass
                except Exception:
                    func2()
                finally:
                    # continue is final is illegal
                    continue
        """)

        self.check_dont_optimize("""
            for x in (1, 2):
                try:
                    pass
                except Exception:
                    func2()
                else:
                    func3()
                finally:
                    # continue is final is illegal
                    continue
        """)

        self.check_dont_optimize("""
            for x in (1, 2):
                try:
                    pass
                except Exception:
                    try:
                        func2()
                    finally:
                        # continue is final is illegal
                        continue
        """)

    def test_try_empty_else(self):
        # else block is empty, body block is not empty

        # without final block
        self.check_optimize("""
            try:
                func1()
            except Exception:
                func2()
            else:
                pass
        """, """
            try:
                func1()
            except Exception:
                func2()
        """)

        # with final block
        self.check_optimize("""
            try:
                func1()
            except Exception:
                func2()
            else:
                pass
            finally:
                func3()
        """, """
            try:
                func1()
            except Exception:
                func2()
            finally:
                func3()
        """)

    def test_try_empty_body_non_empty_else(self):
        # try block is empty, else block is non empty

        # without final block
        self.check_optimize("""
            try:
                pass
            except Exception:
                func2()
            else:
                func3()
        """, """
            func3()
        """)

        # with final block
        self.check_optimize("""
            try:
                pass
            except Exception:
                func2()
            else:
                func3()
            finally:
                func4()
        """, """
            try:
                func3()
            finally:
                func4()
        """)

    def test_try_empty_body_empty_else(self):
        # try and else blocks are empty

        self.check_optimize("""
            try:
                pass
            except Exception:
                func2()
            else:
                pass
        """, """
            pass
        """)

        self.check_optimize("""
            try:
                pass
            except Exception:
                func2()
            else:
                pass
            finally:
                func3()
        """, """
            func3()
        """)

    def test_try_logger_empty_else(self):
        self.config.logger = io.StringIO()

        def get_logs():
            logger = self.config.logger
            logger.seek(0)
            return logger.readlines()

        self.check_optimize("""
            try:
                func1()
            except Exception:
                func2()
            else:
                pass
                pass
            finally:
                func3()
        """, """
            try:
                func1()
            except Exception:
                func2()
            finally:
                func3()
        """)

        self.assertEqual(get_logs(),
                         ['<string>:6: fatoptimizer: Remove dead code (empty else block in try/except): Pass()\n',
                          '<string>:7: fatoptimizer: Remove dead code (empty else block in try/except): Pass()\n'])

    def test_try_logger_empty_body(self):
        self.config.logger = io.StringIO()

        def get_logs():
            logger = self.config.logger
            logger.seek(0)
            return logger.readlines()

        self.check_optimize("""
            try:
                pass
            except Exception:
                func2()
            finally:
                func3()
        """, """
            func3()
        """)

        self.assertEqual(get_logs(),
                        ['<string>:2: fatoptimizer: Remove dead code '
                            '(empty try block): Pass()\n',
                         '<string>:3: fatoptimizer: Remove dead code '
                             "(empty try block): "
                             "ExceptHandler(type=Name(id='Exception', "
                             "ctx=Load()), name=None, "
                             "body=[Expr(value=Call(func=Name(id='(...)\n"])

    def test_for_empty_iter(self):
        self.check_optimize("for x in (): print(x)", "pass")
        self.check_optimize("""
            for x in ():
                print(x)
            else:
                y = 1
        """, """
            y = 1
        """)

    def test_if_empty_else(self):
        self.check_optimize("""
            if test:
                if_block
            else:
                pass
        """, """
            if test:
                if_block
        """)

        self.check_optimize("""
            if test:
                pass
            else:
                else_block
        """, """
            if not test:
                else_block
        """)

        self.check_dont_optimize("""
            if test:
                pass
        """)

    def test_while_empty_else(self):
        self.check_optimize("""
            while test:
                body
            else:
                pass
        """, """
            while test:
                body
        """)

        self.check_dont_optimize("""
            while test:
                pass
            else:
                else_block
        """)

    def test_for_empty_else(self):
        self.check_optimize("""
            for obj in seq:
                body
            else:
                pass
        """, """
            for obj in seq:
                body
        """)

        self.check_dont_optimize("""
            for obj in seq:
                pass
            else:
                else_block
        """)


class SimplifyIterableTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.simplify_iterable = True

    def test_config(self):
        self.config.simplify_iterable = False
        self.check_dont_optimize('''
            for x in {}: pass
        ''')

    def test_replace_with_empty_tuple(self):
        # empty list
        self.check_optimize('for x in []: pass',
                            'for x in (): pass')

        # empty dict
        self.check_optimize('for x in {}: pass',
                            'for x in (): pass')

        # need a guard on set() builtin
        self.check_dont_optimize('for x in set(): pass')

    def test_replace_with_constant(self):
        # list => tuple
        self.check_optimize('for x in [1, 2, 3]: pass',
                            'for x in (1, 2, 3): pass')

        # set => frozenset
        self.check_optimize('for x in {1, 2, 3}: pass',
                            ast.For(target=ast.Name(id='x', ctx=ast.Store()),
                                    iter=ast.Constant(frozenset((1, 2, 3))),
                                    body=[ast.Pass()],
                                    orelse=[]))

        # don't optimize if items are not constants
        self.check_dont_optimize('for x in [1, x]: pass')
        self.check_dont_optimize('for x in {1, x}: pass')

    def test_range(self):
        self.check_builtin_func('range', '''
            for x in range(3):
                pass
        ''', '''
            for x in (0, 1, 2):
                pass
        ''')

        self.check_builtin_func('range', '''
            for x in range(5, 7):
                pass
        ''', '''
            for x in (5, 6):
                pass
        ''')

        self.check_builtin_func('range', '''
            for x in range(0, 10, 2):
                pass
        ''', '''
            for x in (0, 2, 4, 6, 8):
                pass
        ''')


class InliningTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.inlining = True

    def test_config(self):
        self.config.inlining = False
        self.check_dont_optimize('''
            def g(x):
                return 42
            def f(x):
                return g(x) + 3
        ''')

    def test_trivial(self):
        self.check_optimize('''
            def g(x):
                return 42
            def f(x):
                return g(x) + 3
        ''', '''
            def g(x):
                return 42
            def f(x):
                return 42 + 3
        ''')

    def test_nested_function(self):
        self.check_optimize('''
            def f(x):
                def g(x):
                    return 100
                return g(x) + 3
        ''', '''
            def f(x):
                def g(x):
                    return 100
                return 100 + 3
        ''')

    # It shouldn't matter if the caller is defined before the callee,
    # but currently it does
    @unittest.expectedFailure
    def test_out_of_order(self):
        self.check_optimize('''
            def f(x):
                return g(x) + 3
            def g(x):
                return 42
        ''', '''
            def f(x):
                return 42 + 3
            def g(x):
                return 42
        ''')

    def test_simple(self):
        self.check_optimize('''
            def g(x):
                return x * x
            def f(x):
                return g(x) + 3
        ''', '''
            def g(x):
                return x * x
            def f(x):
                return (x * x) + 3
        ''')

    def test_constant(self):
        self.check_optimize('''
            def g(x):
                return x * x
            def f(x):
                return g(7) + 3
        ''', '''
            def g(x):
                return x * x
            def f(x):
                return (7 * 7) + 3
        ''')

    def test_self_recursive(self):
        self.check_dont_optimize('''
            def f(x):
                return f(x)
        ''')

    @unittest.expectedFailure
    def test_mutually_recursive(self):
        self.check_dont_optimize('''
            def f(x):
                return g(x)
            def g(x):
                return f(x)
        ''')

    def test_not_enough_positional_args(self):
        self.check_dont_optimize('''
            def g(x):
                return x * x
            def f(x):
                return g() + 3
        ''')

    def test_too_many_positional_args(self):
        self.check_dont_optimize('''
            def g(x):
                return x * x
            def f(p, q, r):
                return g(p, q, r) + 3
        ''')

    @unittest.expectedFailure
    def test_starargs(self):
        self.check_optimize('''
            def g(*args):
                return args[0]
            def f(x):
                return g(1, 2, 3) + 3
        ''', '''
            def g(*args):
                return args[0]
            def f(x):
                return (1, 2, 3)[0] + 3
        ''')

    def test_keyword_args(self):
        self.check_optimize('''
            def g(foo, bar):
                return foo * bar
            def f(x, y):
                return g(foo=x, bar=y) + 3
        ''', '''
            def g(foo, bar):
                return foo * bar
            def f(x, y):
                return (x * y) + 3
        ''')

    def test_keyword_args_reversed(self):
        self.check_optimize('''
            def g(foo, bar):
                return foo * bar
            def f(x, y):
                return g(bar=x, foo=y) + 3
        ''', '''
            def g(foo, bar):
                return foo * bar
            def f(x, y):
                return (y * x) + 3
        ''')

    @unittest.expectedFailure
    def test_kwargs(self):
        self.check_optimize('''
            def g(**kwargs):
                return args['foo']
            def f(x):
                return g(foo=42) + 3
        ''', '''
            def g(**kwargs):
                return args['foo']
            def f(x):
                return {'foo':42}['foo'] + 3
        ''')

    def test_remap_varnames(self):
        self.check_optimize('''
            def g(y):
                return y * y
            def f(x):
                return g(x) + 3
        ''', '''
            def g(y):
                return y * y
            def f(x):
                return (x * x) + 3
        ''')

    def test_callee_uses_locals(self):
        self.check_dont_optimize('''
            def g1(y):
                return locals()
            def f1(x):
                return g1(x)
        ''')

    def test_caller_uses_locals(self):
        self.check_optimize('''
            def g2(y):
                return y * y
            def f2(x):
                a = g2(x)
                print(locals())
                return a
        ''', '''
            def g2(y):
                return y * y
            def f2(x):
                a = x * x
                print(locals())
                return a
        ''')

    def test_compound_expression(self):
        self.check_optimize('''
            def discriminant(a, b, c):
                return (b * b) - (4 * a * c)
            def count_real_solutions(a, b, c):
                d = discriminant(a, b, c)
                if d > 0:
                   return 2
                elif d == 0:
                   return 1
                else:
                   return 0
        ''', '''
            def discriminant(a, b, c):
                return (b * b) - (4 * a * c)
            def count_real_solutions(a, b, c):
                d = (b * b) - (4 * a * c)
                if d > 0:
                   return 2
                elif d == 0:
                   return 1
                else:
                   return 0
        ''')

    def test_pass(self):
        self.check_optimize('''
            def noop(a, b, c):
                pass
            def caller_of_noop(x):
                a = noop(x, 4, 'foo')
        ''', '''
            def noop(a, b, c):
                pass
            def caller_of_noop(x):
                a = None
        ''')

class ModuleConfigTests(BaseAstTests):
    def get_config(self, config_dict):
        source = '__fatoptimizer__ = %r' % config_dict
        optimizer = fatoptimizer.optimizer.ModuleOptimizer(self.config, 'test')
        tree = ast.parse(source)
        optimizer.optimize(tree)
        return optimizer.config

    def test_enabled(self):
        self.assertEqual(self.config.enabled, True)
        config = self.get_config({'enabled': False})
        self.assertEqual(config.enabled, False)

    def test_max(self):
        self.config.max_int_bits = 1
        self.config.max_bytes_len = 2
        config = self.get_config({
            'max_int_bits': 10,
            'max_bytes_len': 20,
        })
        self.assertEqual(config.max_int_bits, 10)
        self.assertEqual(config.max_bytes_len, 20)


class CompleteTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        self.config.enable_all()

    def test_cond_block(self):
        # test that ast.If.test is optimized: a and b variables must be
        # replaced with their values. The if condition should be replaced with
        # False, and so the whole if is removed.
        self.check_optimize('''
            a = 5
            b = a
            if a != b: print(a)
        ''', '''
            a = 5
            b = 5
            pass
        ''')


class MiscTests(unittest.TestCase):
    def test_version(self):
        import setup
        self.assertEqual(fatoptimizer.__version__, setup.VERSION)


class CallPureMethodTests(BaseAstTests):
    def setUp(self):
        super().setUp()
        from fatoptimizer.methods import add_pure_methods
        add_pure_methods(self.config)

    def test_bytes_decode(self):
        # test number of arguments
        self.check_optimize(r'b"abc".decode()',
                            r'"abc"')
        self.check_optimize(r'b"abc".decode("ascii")',
                            r'"abc"')
        self.check_optimize(r'b"ab\xff".decode("ascii", "replace")',
                            r'"ab\ufffd"')

        # test encoding aliases
        self.check_optimize(r'b"abc".decode("ASCII")',
                            r'"abc"')
        self.check_optimize(r'b"abc".decode("latin1")',
                            r'"abc"')
        self.check_optimize(r'b"abc".decode("utf8")',
                            r'"abc"')

        # test decode error
        self.check_dont_optimize(r'b"ab\xff".decode("ascii")')

        # unsupported encoding/errors
        self.check_dont_optimize(r'b"ab\xff".decode("big5")')
        self.check_dont_optimize(r'b"ab\xff".decode("ascii", "surrogateescape")')

    def test_bytes(self):
        self.check_optimize(r'"ABC".lower()', '"abc"')
        self.check_optimize(r'"ABC".upper()', '"ABC"')
        self.check_optimize(r'"abc".capitalize()', '"Abc"')
        self.check_optimize(r'"aBc".swapcase()', '"AbC"')
        self.check_optimize(r'"ABC".casefold()', '"abc"')
        self.check_optimize(r'"abc".isalpha()', 'True')
        self.check_optimize(r'"abc123".isalnum()', 'True')
        self.check_optimize(r'"1".isdecimal()', 'True')
        self.check_optimize(r'"1".isdigit()', 'True')
        self.check_optimize(r'"abc".islower()', 'True')
        self.check_optimize(r'"1".isnumeric()', 'True')
        self.check_optimize(r'"ABC".isupper()', 'True')
        self.check_optimize(r'"1".isidentifier()', 'False')
        self.check_optimize(r'"def".isidentifier()', 'True')
        self.check_optimize(r'"A Title".istitle()', 'True')
        self.check_optimize(r'" ".isspace()', 'True')
        self.check_optimize(r'"AbC".swapcase()', '"aBc"')
        self.check_optimize(r'"hello world".title()', '"Hello World"')

    def test_float(self):
        self.check_optimize(r'(5.0).is_integer()', 'True')
        self.check_optimize(r'(1.5).as_integer_ratio()', '(3, 2)')
        self.check_optimize(r'(1.5).hex()', '"0x1.8000000000000p+0"')

    def test_int(self):
        self.check_optimize(r'(1023).bit_length()', '10')

    def test_str_encode(self):
        # test number of arguments
        self.check_optimize(r'"abc".encode()',
                            'b"abc"')
        self.check_optimize(r'"abc".encode("ascii")',
                            r'b"abc"')
        self.check_optimize(r'"ab\xff".encode("ascii", "replace")',
                            r'b"ab?"')

        # test encode error
        self.check_dont_optimize(r'"ab\xff".encode("ascii")')

        # unsupported encoding/errors
        self.check_dont_optimize(r'"ab\xff".encode("big5")')
        self.check_dont_optimize(r'"ab\xff".encode("ascii", "backslashreplace")')

    def test_str(self):
        self.check_optimize(r'"ABC".lower()', '"abc"')
        self.check_optimize(r'"ABC".upper()', '"ABC"')
        self.check_optimize(r'"abc".capitalize()', '"Abc"')
        self.check_optimize(r'"aBc".swapcase()', '"AbC"')
        self.check_optimize(r'"ABC".casefold()', '"abc"')
        self.check_optimize(r'"abc".isalpha()', 'True')
        self.check_optimize(r'"abc123".isalnum()', 'True')
        self.check_optimize(r'"1".isdecimal()', 'True')
        self.check_optimize(r'"1".isdigit()', 'True')
        self.check_optimize(r'"abc".islower()', 'True')
        self.check_optimize(r'"1".isnumeric()', 'True')
        self.check_optimize(r'"ABC".isupper()', 'True')
        self.check_optimize(r'"1".isidentifier()', 'False')
        self.check_optimize(r'"def".isidentifier()', 'True')
        self.check_optimize(r'"A Title".istitle()', 'True')
        self.check_optimize(r'" ".isspace()', 'True')
        self.check_optimize(r'"AbC".swapcase()', '"aBc"')
        self.check_optimize(r'"hello world".title()', '"Hello World"')

if __name__ == "__main__":
    unittest.main()
