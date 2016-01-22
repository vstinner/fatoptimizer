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


#if not any(transformer.name == 'fat' for transformer in sys.get_code_transformers()):
#    raise Exception("test must be run with python3 -X fat")


def disassemble(obj):
    output = io.StringIO()
    dis.dis(obj, file=output)
    return output.getvalue()


def call_builtin():
    return len("abc")



class CallPureBuiltins(unittest.TestCase):
    def test_code(self):
        self.assertIn('LOAD_GLOBAL', disassemble(call_builtin))

        self.assertEqual(len(fat.get_specialized(call_builtin)), 1)

        code = fat.get_specialized(call_builtin)[0][0]
        self.assertEqual(code.co_name, call_builtin.__name__)
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


def copy_builtin(x):
    len(x)
    def nested():
        pass
    return nested.__qualname__


class CopyBuiltinToConstant(unittest.TestCase):
    def test_qualname(self):
        self.assertEqual(len(fat.get_specialized(copy_builtin)), 1)

        # optimizations must not modify the function name
        qualname = copy_builtin("abc")
        self.assertEqual(qualname, 'copy_builtin.<locals>.nested')


if __name__ == "__main__":
    unittest.main()
