import ast

from .tools import (OptimizerStep,
    copy_lineno, ast_contains, copy_node, compact_dump)


# AST types of nodes that cannot be removed
_CANNOT_REMOVE_TYPES = (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom,
                        # don't remove 'except' block if it contains continue
                        # or break: see can_move_final() for the rationale
                        ast.Continue)

_CANNOT_MOVE_FINAL = (ast.Continue,)


def is_empty_body(node_list):
    if not node_list:
        return True
    return all(isinstance(node, ast.Pass) for node in node_list)


def can_remove(node_list):
    if not node_list:
        # None and [] can be removed
        return True
    if ast_contains(node_list, _CANNOT_REMOVE_TYPES):
        return False
    return True


def can_move_final(node_list):
    """Check if continue is in node_list.

    Using continue in a final block (of try/finally) is illegal: these
    instructions must not be moved, they must raise a SyntaxError (see
    test_syntax).
    """
    if not node_list:
        # None and [] can be moved
        return True
    return not ast_contains(node_list, _CANNOT_MOVE_FINAL)


def log_node_removal(optimizer, message, node_list):
    for node in node_list:
        node_repr = compact_dump(node)
        optimizer.log(node, "%s: %s", message, node_repr)


def remove_dead_code(optimizer, node_list):
    """Remove dead code.

    Modify node_list in-place.
    Example: replace "return 1; return 2" with "return 1".
    """

    truncate = None
    stop = len(node_list) - 1
    for index, node in enumerate(node_list):
        if index == stop:
            break
        if not isinstance(node, (ast.Return, ast.Raise)):
            continue
        if not can_remove(node_list[index+1:]):
            continue
        truncate = index
        break
    # FIXME: use for/else: ?
    if truncate is None:
        return node_list
    optimizer.log_node_removal("Remove unreachable code", node_list[truncate+1:])
    return node_list[:truncate+1]


class RemoveDeadCode(OptimizerStep):
    def log_node_removal(self, message, node_list):
        log_node_removal(self, message, node_list)

    def _replace_node(self, node, node_list):
        if node_list:
            return node_list

        # FIXME: move this in NodeTransformer?
        new_node = ast.Pass()
        copy_lineno(node, new_node)
        return new_node

    def _visit_if_while(self, node):
        if not self.config.remove_dead_code:
            return

        if not isinstance(node.test, ast.Constant):
            return

        test_true = bool(node.test.value)
        if test_true:
            if isinstance(node, ast.While):
                # while of 'while 1: ...' must not be removed
                return
            new_nodes = node.body
            removed_nodes = node.orelse
            reason = "test always true"
        else:
            new_nodes = node.orelse
            removed_nodes = node.body
            reason = "test always false"

        if not can_remove(removed_nodes):
            return

        self.log_node_removal("Remove dead code (%s)" % reason,
                              removed_nodes)
        return self._replace_node(node, new_nodes)

    def visit_If(self, node):
        new_node = self._visit_if_while(node)
        if new_node is not None:
            return new_node

        if node.orelse and is_empty_body(node.orelse):
            self.log_node_removal("Remove dead code (empty else block of if)",
                                  node.orelse)
            new_node = copy_node(node)
            del new_node.orelse[:]
            node = new_node

        if is_empty_body(node.body) and not is_empty_body(node.orelse):
            self.log_node_removal("Remove dead code (empty if block)",
                                  node.body)
            new_node = copy_node(node)
            not_test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            copy_lineno(node.test, not_test)
            new_node = ast.If(test=not_test, body=new_node.orelse, orelse=[])
            copy_lineno(node, new_node)
            return new_node

        return node

    def visit_While(self, node):
        new_node = self._visit_if_while(node)
        if new_node is not None:
            return new_node

        if node.orelse and is_empty_body(node.orelse):
            self.log_node_removal("Remove dead code "
                                  "(empty else block of while)",
                                  node.orelse)
            new_node = copy_node(node)
            del new_node.orelse[:]
            return new_node

    def _try_empty_body(self, node):
        if not can_remove(node.body):
            return
        if not can_remove(node.handlers):
            return
        # body block is empty, handlers can be removed

        self.log_node_removal("Remove dead code (empty try block)",
                              node.body)
        self.log_node_removal("Remove dead code (empty try block)",
                              node.handlers)

        if not node.orelse:
            # body and else blocks are empty
            #
            # try: pass (except: ...) finally: final_code
            # => final_code
            if not can_move_final(node.finalbody):
                return
            return self._replace_node(node, node.finalbody)

        if is_empty_body(node.finalbody):
            # body and finally blocks are empty, else block is non empty
            #
            # try: pass (except: ...) else: else_code (final: pass)
            # => else_code
            self.log_node_removal("Remove dead code (empty finally block)",
                                  node.finalbody)
            return self._replace_node(node, node.orelse)

        # body block is empty, else and final blocks are non empty
        #
        # try: pass (except: ...) else: code1 finally: code2
        # => try: code1 finally: code2
        if not can_move_final(node.finalbody):
            return

        new_node = ast.Try(body=node.orelse, finalbody=node.finalbody,
                           handlers=[], orelse=[])
        copy_lineno(node, new_node)
        return new_node

    def visit_Try(self, node):
        if not self.config.remove_dead_code:
            return

        if node.orelse and is_empty_body(node.orelse):
            # remove 'else: pass'
            self.log_node_removal("Remove dead code (empty else block in try/except)",
                                  node.orelse)

            node = copy_node(node)
            node.orelse.clear()

        if is_empty_body(node.body):
            new_node = self._try_empty_body(node)
            if new_node is not None:
                return new_node

        return node

    def _remove_for(self, node):
        if node.orelse:
            node_list = node.body
        else:
            node_list = (node,)
        self.log_node_removal("Read dead code (empty for iterator)",
                              node_list)
        return self._replace_node(node, node.orelse)

    def visit_For(self, node):
        if not self.config.remove_dead_code:
            return

        if (isinstance(node.iter, ast.Constant)
           and isinstance(node.iter.value, tuple)
           and not node.iter.value
           and can_remove(node.body)):
            return self._remove_for(node)

        if node.orelse and is_empty_body(node.orelse):
            self.log_node_removal("Remove dead code (empty else block of for)",
                                  node.orelse)
            new_node = copy_node(node)
            del new_node.orelse[:]
            return new_node
