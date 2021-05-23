"""
Given a Python source file, this module extracts all top-level functions and
methods.
"""

import ast
import sys
import typing

import astor

from ast_codez_tools.literal_statement_remover import remove_literal_statements


def extract_functions(node: ast.AST) -> "dict[str, str]":
    """Wrapper around FunctionExtractor.

    Args:
        node: ast.AST node. This should be the AST of a Python file.

    Returns:
        Dictionary that maps function names to (cleaned) function code.
    """
    cleaned_node = remove_literal_statements(node)
    extractor = FunctionExtractor()
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
    return extract_functions(node)


class FunctionExtractor(ast.NodeVisitor):
    """Extracts top-level functions and methods of classes from a file.

    This class is not intended to be reused across multiple Python files.
    You should create a new instance of this class for every Python file.
    """

    def __init__(self):
        super().__init__()
        self._functions_seen: "dict[str, ast.AST]" = {}

    def get_functions_seen(self):
        """Returns all functions seen while parsing."""
        return self._functions_seen

    def _add_function(self, name: str, node: ast.AST) -> None:
        if name not in self._functions_seen:
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
        child_visitor = FunctionExtractor()

        # We can't let the child_visitor directly iterate over node, since it
        # would call its own visit_ClassDef(), creating a child-child-visitor,
        # which calls its own visit_ClassDef(), ... creating an infinite loop.
        for child_node in ast.iter_child_nodes(node):
            child_visitor.visit(child_node)

        # Methods of classes are stored as <class name>.<method name>
        for method_name, method_node in child_visitor.get_functions_seen().items():
            self._add_function(f"{node.name}.{method_name}", method_node)

        # Don't call generic_visit() since we already visited them
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
