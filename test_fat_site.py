"""
Integration test: Test FAT mode with the fatoptimizer configured by the site
module.
"""
import dis
import fat
import io
import sys
import textwrap
import unittest


if 'fat' not in sys.implementation.ast_transformers:
    raise Exception("test must be run with python3 -X fat")

if not sys.ast_transformers:
    raise Exception("fatoptimizer is not installed? %r" % sys.implementation.optim_tag)


def disassemble(obj):
    output = io.StringIO()
    dis.dis(obj, file=output)
    return output.getvalue()


class CallPureBuiltins(unittest.TestCase):
    def test_code(self):
        def func():
            return len("abc")

        self.assertIn('LOAD_GLOBAL', disassemble(func))

        self.assertEqual(len(fat.get_specialized(func)), 1)

        code = fat.get_specialized(func)[0][0]
        self.assertEqual(code.co_name, func.__name__)
        self.assertNotIn('LOAD_GLOBAL', disassemble(code))

    def test_import(self):
        ns = {}
        code = textwrap.dedent("""
            from builtins import str as chr

            def func():
                # chr() is not the expected builtin function,
                # it must not be optimized
                return chr(65)
        """)
        exec(code, ns, ns)
        func = ns['func']

        self.assertEqual(fat.get_specialized(func), [])


class CopyBuiltinToConstant(unittest.TestCase):
    def test_qualname(self):
        def func(x):
            len(x)
            def nested():
                pass
            return nested.__qualname__

        self.assertEqual(len(fat.get_specialized(func)), 1)

        # optimizations must not modify function names
        qualname = func("abc")
        self.assertEqual(qualname,
                         'CopyBuiltinToConstant.test_qualname.<locals>.func.<locals>.nested')


if __name__ == "__main__":
    unittest.main()
