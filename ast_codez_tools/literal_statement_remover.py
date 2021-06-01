import ast
import sys
import typing
from collections import deque

# We rely on Python 3.8+ behavior of treating all constants as ast.Constant
if sys.version_info < (3, 8):
    raise Exception(
        f"Python version 3.8 required; your Python version is {sys.version}"
    )


def is_literal_statement(node: ast.AST) -> bool:
    """Checks if the given node is a literal statement.

    A literal statement is a statement that consists of a single literal
    expression. It has no effect on the execution flow.

    For example, the following Python code contains 5 literal statements:

    ```
    def foo():
        0
        123.45
        -9.9j
        "string literal"
        b"bytes literal"
    ```

    This function returns `False` for `True`, `False`, `None`, and `...`, even
    though Python treats these values as constants.
    """
    if isinstance(node, ast.Expr):
        if isinstance(node.value, ast.Constant):
            # Don't use isinstance() because True and False are subtypes of int!
            if type(node.value.value) in (str, bytes, int, float, complex):
                return True
    return False


def remove_literal_statements(root: ast.AST) -> ast.AST:
    """Removes all literal statements (e.g. docstrings) in the node in-place.

    Args:
        root: AST node to modify
    Returns:
        Modified root node
    """
    for node in _ast_walk_lazy(root):
        body = getattr(node, "body", None)
        if type(body) is list:
            # 'body' must not be empty
            setattr(
                node,
                "body",
                [child for child in body if not is_literal_statement(child)]
                or [ast.Pass()],
            )

        orelse = getattr(node, "orelse", None)
        if type(orelse) is list:
            # 'orelse' can be empty
            setattr(
                node,
                "orelse",
                [child for child in orelse if not is_literal_statement(child)],
            )

        finalbody = getattr(node, "finalbody", None)
        if type(finalbody) is list:
            # 'finalbody' can be empty
            setattr(
                node,
                "finalbody",
                [child for child in finalbody if not is_literal_statement(child)],
            )

    return root


def _ast_walk_lazy(node: ast.AST) -> typing.Iterator[ast.AST]:
    """ "Lazy" version of `ast.walk()`.

    This yields the node first before iterating its child nodes.
    This allows the caller to modify a node's children before they are iterated.
    """
    todo = deque([node])
    while todo:
        node = todo.popleft()
        # ast.walk() adds child nodes to 'todo' before yielding 'node'.
        # We do it backwards to avoid iterating over child nodes that have been
        # removed by the caller.
        yield node
        todo.extend(ast.iter_child_nodes(node))
