"""
Given a Python source file, this module extracts all top-level functions and
methods.
"""

import ast
import sys
import typing
import warnings

import astor


def extract_functions(
    node: ast.AST, filename: typing.Optional[str] = None
) -> "dict[str, str]":
    """Wrapper around FunctionExtractor.

    Args:
        node: ast.AST node. This should be the AST of a Python file.
        filename: Name of the Python file, used for warning messages only

    Returns:
        Dictionary that maps function names to (cleaned) function code.
    """
    cleaned_node = DocstringRemover().visit(node)
    extractor = FunctionExtractor(name_prefix=f"{filename}:" if filename else None)
    extractor.visit(cleaned_node)
    return {
        name: astor.to_source(function_node)
        for name, function_node in extractor.get_functions_seen().items()
    }


def extract_functions_from_file(filename: str) -> "dict[str, str]":
    """Extracts functions from python code.

    Args:
        filename: Path to Python source file.

    Returns:
        Dictionary that maps function names to (cleaned) function code.
    """
    with open(filename, mode="r", encoding="utf8") as source_file:
        source_code = source_file.read()
    node = ast.parse(source_code, filename=filename)
    return extract_functions(node, filename)


class DocstringRemover(ast.NodeTransformer):
    """Removes docstrings from functions and classes."""

    @staticmethod
    def _remove_docstring(
        node: typing.Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]
    ) -> None:
        if node.body:
            first_child = node.body[0]
            if (
                isinstance(first_child, ast.Expr)
                and isinstance(first_child.value, ast.Constant)
                and isinstance(first_child.value.value, str)
            ):
                node.body.pop(0)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._remove_docstring(node)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._remove_docstring(node)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self._remove_docstring(node)
        return self.generic_visit(node)


class FunctionExtractor(ast.NodeVisitor):
    """Extracts top-level functions and methods of classes from a file.

    This class is not intended to be reused across multiple Python files.
    You should create a new instance of this class for every Python file.
    """

    def __init__(self, name_prefix: "typing.Optional[str]" = None):
        """
        Args:
            name_prefix:
                Used for logging the class names of methods.
                This is used for logging/warning only!
        """
        super().__init__()
        self._name_prefix = name_prefix
        self._functions_seen: "dict[str, ast.AST]" = {}

    def get_functions_seen(self):
        """Returns all functions seen while parsing."""
        return self._functions_seen

    def _get_full_name(self, name: str) -> str:
        """This is used for logging/warning only"""
        return self._name_prefix + name if self._name_prefix else name

    def _add_function(self, name: str, node: ast.AST) -> None:
        if name in self._functions_seen:
            warnings.warn(
                f"Duplicate function name, is ignored: {self._get_full_name(name)}()"
            )
        else:
            self._functions_seen[name] = node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._add_function(node.name, node)
        # Don't call generic_visit() since we don't want to process inner
        # functions or classes
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._add_function(node.name, node)
        # Don't call generic_visit() since we don't want to process inner
        # functions or classes
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        child_visitor = FunctionExtractor(
            name_prefix=self._get_full_name(node.name) + "."
        )
        # We can't let the child_visitor directly iterate over node, since it
        # would call its own visit_ClassDef(), creating a child-child-visitor,
        # which calls its own visit_ClassDef(), ... creating an infinite loop.
        for child_node in ast.iter_child_nodes(node):
            child_visitor.visit(child_node)

        # Methods of classes are stored as <class name>.<method name>
        for method_name, method_node in child_visitor.get_functions_seen().items():
            self._add_function(f"{node.name}.{method_name}", method_node)

        # Don't call generic_visit() since we don't want to process innner
        # classes.  (Who uses inner classes in Python, anyway?)
        return node


def main():
    functions = extract_functions_from_file(sys.argv[1])

    for name, node in functions.items():
        print("-" * 80)
        print(f"name: {name}()")
        print("-" * 80)
        print(node)
        print()


if __name__ == "__main__":
    main()
