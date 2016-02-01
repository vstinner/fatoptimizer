import ast

from .tools import OptimizerStep, pretty_dump
#from .specialized import BuiltinGuard


class InlineSubstitution(OptimizerStep):
    """Function call inlining."""

    def can_inline(self, node):
        '''Given a Call node, determine whether we should inline
        the callee.  If so, return the callee FunctionDef, otherwise
        return None'''
        # TODO: size criteria?
        # TODO: don't do it if either uses locals()
        # TODO: don't do it for recursive functions
        if not isinstance(node.func, ast.Name):
            return None
        from .namespace import _fndefs
        if node.func.id not in _fndefs:
            return None
        candidate = _fndefs[node.func.id]

        # For now, only allow functions that simply return a value
        body = candidate.body
        if len(body) != 1:
            return None
        if not isinstance(body[0], ast.Return):
            return None

        # All checks passed
        return candidate

    def visit_Call(self, node):
        # TODO: renaming variables to avoid clashes
        # or do something like:
        #   .saved_locals = locals()
        #   set params to args
        #   body of called function
        #   locals() = .saved_locals
        #   how to things that aren't just a return
        #   how to handle early return
        # TODO: what guards are needed?
        # etc
        '''
        left=Call(func=Name(id='g', ctx=Load()), args=[Name(id='x', ctx=Load()),
           ], keywords=[], starargs=None, kwargs=None)
        '''
        inlinable = self.can_inline(node)
        if not inlinable:
            return node
        if 0:
            print(pretty_dump(inlinable))
        '''
FunctionDef(name='g', args=arguments(args=[
    arg(arg='x', annotation=None),
  ], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]), body=[
    Return(value=BinOp(left=Name(id='x', ctx=Load()), op=Mult(), right=Name(id='x', ctx=Load()))),
  ], decorator_list=[], returns=None)
        '''
        # Substitute the Call with the expression of the single return stmt
        # within the callee.
        # This assumes a single Return stmt
        # FIXME: probably should be a copy of the value subtree
        # FIXME: remap params/args
        return inlinable.body[0].value
