import ast

from .tools import OptimizerStep, pretty_dump, NodeTransformer, NodeVisitor

class Checker(NodeVisitor):
    '''Gather a list of problems that would prevent inlining a function.'''
    def __init__(self):
        self.problems = []

    def visit_Call(self, node):
        # Reject explicit attempts to use locals()
        # TODO: detect uses via other names
        if isinstance(node.func, ast.Name):
            if node.func.id == 'locals':
                self.problems.append('use of locals()')

class RenameVisitor(NodeTransformer):
    def __init__(self, callsite, inlinable):
        assert callsite.keywords == []
        assert callsite.starargs is None
        assert callsite.kwargs is None
        assert inlinable.args.vararg is None
        assert inlinable.args.kwonlyargs == []
        assert inlinable.args.kw_defaults == []
        assert inlinable.args.kwarg is None
        assert inlinable.args.defaults == []

        # Mapping from name in callee to name in caller
        self.remapping = {}
        for formal, actual in zip(inlinable.args.args, callsite.args):
            self.remapping[formal.arg] = actual.id

    def visit_Name(self, node):
        assert isinstance(node.ctx, ast.Load) # FIXME
        if node.id in self.remapping:
            return ast.Name(id=self.remapping[node.id], ctx=node.ctx)
        return node

class InlineSubstitution(OptimizerStep):
    """Function call inlining."""

    def can_inline(self, callsite):
        '''Given a Call callsite, determine whether we should inline
        the callee.  If so, return the callee FunctionDef, otherwise
        return None.'''
        # TODO: size criteria?
        # TODO: don't do it for recursive functions
        if not isinstance(callsite.func, ast.Name):
            return None
        from .namespace import _fndefs
        if callsite.func.id not in _fndefs:
            return None
        candidate = _fndefs[callsite.func.id]

        # For now, only support simple positional arguments
        if callsite.keywords:
            return False
        if callsite.starargs:
            return False
        if callsite.kwargs:
            return False
        if candidate.args.vararg:
            return False
        if candidate.args.kwonlyargs:
            return False
        if candidate.args.kw_defaults:
            return False
        if candidate.args.kwarg:
            return False
        if candidate.args.defaults:
            return False
        if len(candidate.args.args) != len(callsite.args):
            return False

        # For now, only allow functions that simply return a value
        body = candidate.body
        if len(body) != 1:
            return None
        if not isinstance(body[0], ast.Return):
            return None

        # Walk the candidate's nodes looking for potential problems
        c = Checker()
        c.visit(body[0])
        if c.problems:
            return None

        # All checks passed
        return candidate

    def visit_Call(self, node):
        if not self.config.inlining:
            return

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
        returned_expr = inlinable.body[0].value
        # Rename params/args
        v = RenameVisitor(node, inlinable)
        try:
            new_expr = v.visit(returned_expr)
        except NotInlinable:
            return node
        return new_expr
