"""
Integration test: test FAT mode with the fatoptimizer configured in this file.
"""
import fatoptimizer
import dis
import fat
import io
import sys
import textwrap
import unittest

# Disable the AST optimizer on this module
__fatoptimizer__ = {'enabled': False}

if 'fat' not in sys.implementation.ast_transformers:
    raise Exception("test must be run with python3 -X fat")

def create_optimizer():
    config = fatoptimizer.Config()
    config.strict = False
    config.copy_builtin_to_constant = {'chr'}

    def optimizer(tree, filename):
        return fatoptimizer.optimize(tree, filename, config)
    return optimizer

# Replace existing AST transformers with our optimizer
sys.ast_transformers[:] = [create_optimizer()]


def disassemble(obj):
    output = io.StringIO()
    dis.dis(obj, file=output)
    return output.getvalue()


class CopyGlobalToLocal(unittest.TestCase):
    def test_builtin(self):
        ns = {}
        exec(textwrap.dedent("""
            def func(x):
                return chr(x)
        """), ns, ns)
        func = ns['func']

        self.assertIn('LOAD_GLOBAL', disassemble(func))
        self.assertEqual(func.__code__.co_consts, (None,))

        # the specialized bytecode must not use LOAD_GLOBAL, but have
        # chr in its constants
        self.assertEqual(len(fat.get_specialized(func)), 1)
        new_code = fat.get_specialized(func)[0][0]
        self.assertNotIn('LOAD_GLOBAL', disassemble(new_code))
        self.assertEqual(new_code.co_consts, (None, chr))

        # call the specialized function
        self.assertNotIn('chr', globals())
        self.assertEqual(func(65), 'A')

        # chr() is modified in globals(): call the original function
        # and remove the specialized bytecode
        ns['chr'] = str
        self.assertEqual(func(65), '65')
        self.assertEqual(len(fat.get_specialized(func)), 0)


if __name__ == "__main__":
    unittest.main()
