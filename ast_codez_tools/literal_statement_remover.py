import ast
import sys
import typing

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


class LiteralStatementRemover(ast.NodeTransformer):
    """Removes all string, bytes, and numeric constant expression statements in
    the node.

    This removes docstrings and other literals that happen to be placed at the
    statement level. Such statements do not affect the semantics of the code.

    If removing a statement would result in syntactically invalid code, this
    inserts a pass statement to preserve the semantics of the code.
    """

    # -------- Nodes with 'body'

    def _cleanup_node_body(
        self,
        node: typing.Union[
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.With,
            ast.AsyncWith,
            ast.ExceptHandler,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.If,
            ast.Try,
        ],
    ) -> None:
        # 'body' must not be empty
        node.body = [child for child in node.body if not is_literal_statement(child)]
        if not node.body:
            node.body.append(ast.Pass())

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    def visit_With(self, node: ast.With) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self._cleanup_node_body(node)
        return self.generic_visit(node)

    # -------- Nodes with 'body' and 'orelse'

    def _cleanup_node_body_and_orelse(
        self, node: typing.Union[ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try]
    ) -> None:
        self._cleanup_node_body(node)
        # 'orelse' can be empty
        node.orelse = [
            child for child in node.orelse if not is_literal_statement(child)
        ]

    def visit_For(self, node: ast.For) -> ast.AST:
        self._cleanup_node_body_and_orelse(node)
        return self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.AST:
        self._cleanup_node_body_and_orelse(node)
        return self.generic_visit(node)

    def visit_While(self, node: ast.While) -> ast.AST:
        self._cleanup_node_body_and_orelse(node)
        return self.generic_visit(node)

    def visit_If(self, node: ast.If) -> ast.AST:
        self._cleanup_node_body_and_orelse(node)
        return self.generic_visit(node)

    # -------- Nodes with 'body', 'orelse', and 'finalbody'

    # ast.Try is the only node that has 'finalbody'
    def visit_Try(self, node: ast.Try) -> ast.AST:
        self._cleanup_node_body_and_orelse(node)
        # 'finalbody' can be empty
        node.finalbody = [
            child for child in node.finalbody if not is_literal_statement(child)
        ]
        return self.generic_visit(node)


_literal_statement_remover = LiteralStatementRemover()


def remove_literal_statements(node: ast.AST) -> ast.AST:
    """Removes all literal statements (e.g. docstrings) in the node in-place.

    Args:
        node: AST node to modify
    Returns:
        Modified node
    """
    return _literal_statement_remover.visit(node)
