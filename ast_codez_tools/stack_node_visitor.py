"""A NodeVisitor clone that uses a stack instead of recursion."""

import ast
import typing
from collections import deque


def iter_fields_reversed(
    node: ast.AST,
) -> typing.Generator[
    tuple[str, typing.Union[ast.AST, list[ast.AST], None]], None, None
]:
    """Yields all fields in `node` in reverse order.

    Args:
        node: AST node
    Yields:
        A tuple of `(fieldname, value)` for each field in `node._fields`,
        yielded in reverse order.
    """
    for field in reversed(node._fields):
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass


class InvalidCallerError(Exception):
    """Exception raised when a function is called where it should not be."""


class StackNodeVisitor:
    """A variant of NodeVistor that uses a stack instead of recursion.

    A node visitor base class that uses a stack instead of recursive method
    calls. This prevents RecursionError when traversing extremely deep AST trees
    (e.g. extremely long `if...elif...else` chains).

    Like `ast.NodeVisitor`, this class is meant to be subclassed. Subclasses can
    define `visit_<NodeType>()` methods to process certain types of AST nodes.
    However, there are two major semantic difference:

    1. `generic_visit()` does not immediately visit all descendant nodes, but
        adds them to a list of nodes to be processed by `visit()`.
    2. `visit()` cannot be called directly to start traversing a node.
        Instead, you must call `do_visit(node)`.
    """

    def __init__(self):
        self._nodes_to_visit: typing.Union[deque[ast.AST], None] = None

    def do_visit(self, node: ast.AST) -> ast.AST:
        """Visits the node and all of its descendants in preorder."""
        if self._nodes_to_visit is not None:
            raise InvalidCallerError(
                f"do_visit() cannot be called from within another do_visit() call; this {type(self).__name__} is already traversing another AST node"
            )

        try:
            self._nodes_to_visit = deque()
            self.visit(node)
            while self._nodes_to_visit:
                current_node = self._nodes_to_visit.pop()
                self.visit(current_node)
        finally:
            # Ensure that the StackNodeVisitor is left in a valid state even if
            # an exception is raised during traversal
            self._nodes_to_visit = None

        return node

    def visit(self, node: ast.AST) -> ast.AST:
        """Visit a node.

        This can be overridden in a subclass to process all nodes being visited.
        Unlike `ast.NodeVisitor`, this should not be called directly, but
        through `do_visit()`.
        """
        if self._nodes_to_visit is None:
            raise InvalidCallerError(
                "visit() is protected and cannot be called directly; use do_visit() to start traversing a node"
            )
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.AST) -> ast.AST:
        """Called if no explicit visitor function exists for a node.

        Schedules all immediate child nodes of `node` to be visited later, then
        returns the original `node`.
        """
        if self._nodes_to_visit is None:
            raise InvalidCallerError(
                "generic_visit() is protected and cannot be called directly; use do_visit() to start traversing a node"
            )

        for field, value in iter_fields_reversed(node):
            if isinstance(value, list):
                for item in reversed(value):
                    if isinstance(item, ast.AST):
                        self._nodes_to_visit.append(item)
            elif isinstance(value, ast.AST):
                self._nodes_to_visit.append(value)

        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        type_name = ast._const_node_type_names.get(type(value))
        if type_name is None:
            for cls, name in ast._const_node_type_names.items():
                if isinstance(value, cls):
                    type_name = name
                    break
        if type_name is not None:
            method = "visit_" + type_name
            try:
                visitor = getattr(self, method)
            except AttributeError:
                pass
            else:
                import warnings

                warnings.warn(
                    f"{method} is deprecated; add visit_Constant", DeprecationWarning, 2
                )
                return visitor(node)
        return self.generic_visit(node)


def main():
    """Tests if StackNodeVisitor works correctly by comparing its traversal
    order with ast.NodeVisitor, using all Python code under the current
    directory as test inputs."""
    import pathlib

    class NodeRecorder(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self._node_types_seen: list[str] = []

        def visit(self, node: ast.AST) -> None:
            self._node_types_seen.append(type(node).__name__)
            return super().visit(node)

        def get_node_types_seen(self) -> tuple[str, ...]:
            return tuple(self._node_types_seen)

    class StackNodeRecorder(StackNodeVisitor):
        def __init__(self):
            super().__init__()
            self._node_types_seen: list[str] = []

        def visit(self, node: ast.AST) -> ast.AST:
            self._node_types_seen.append(type(node).__name__)
            return super().visit(node)

        def get_node_types_seen(self) -> tuple[str, ...]:
            return tuple(self._node_types_seen)

    for file_path in pathlib.Path().rglob("*.py"):
        if not file_path.is_file():
            continue
        if "site-packages" in file_path.parts:
            continue

        print(f"Testing StackNodeVisitor with {file_path}")
        root = ast.parse(file_path.read_text(encoding="utf-8"), filename=file_path)

        visitor1 = NodeRecorder()
        visitor2 = StackNodeRecorder()

        visitor1.visit(root)
        visitor2.do_visit(root)

        visited1 = visitor1.get_node_types_seen()
        visited2 = visitor2.get_node_types_seen()
        assert (
            visited1 == visited2
        ), f"StackNodeRecorder is incorrect: {file_path} was walked in wrong order.\n{visited1=}\n{visited2=}"

    print("All tests done!")


if __name__ == "__main__":
    main()
