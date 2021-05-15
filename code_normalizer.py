import ast
import astor
import sys
import typing

from function_extractor import extract_functions_from_file


class CodeNormalizer(ast.NodeTransformer):
    """
    Scans Python source code and replaces identifiers and constants with special
    constants so that the model only has to deal with a limited number of
    vocabulary.

    - We don't override import from because there's no point!
    """

    def __init__(self):
        super().__init__()
        # Note: Since functions are first-class objects in Python, we can't
        # distinguish function names from variable names.
        self._identifiers_seen: typing.Dict[str, str] = {}
        self._literals_seen_float: typing.Dict[float, str] = {}
        self._literals_seen_int: typing.Dict[int, str] = {}
        self._literals_seen_str: typing.Dict[str, str] = {}

    def _get_replacement_identifier(self, identifier: str) -> str:
        try:
            return self._identifiers_seen[identifier]
        except KeyError:
            replacement = self._identifiers_seen[
                identifier
            ] = f"IDENTIFIER_{len(self._identifiers_seen)}"
            return replacement

    def _get_replacement_float(self, literal: float) -> str:
        try:
            return self._literals_seen_float[literal]
        except KeyError:
            replacement = self._literals_seen_float[
                literal
            ] = f"FLOAT_{len(self._literals_seen_float)}"
            return replacement

    def _get_replacement_int(self, literal: int) -> str:
        try:
            return self._literals_seen_int[literal]
        except KeyError:
            replacement = self._literals_seen_int[
                literal
            ] = f"INT_{len(self._literals_seen_int)}"
            return replacement

    def _get_replacement_str(self, literal: str) -> str:
        try:
            return self._literals_seen_str[literal]
        except KeyError:
            replacement = self._literals_seen_str[
                literal
            ] = f"STR_{len(self._literals_seen_str)}"
            return replacement

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self._get_replacement_identifier(node.name)
        return self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._get_replacement_identifier(node.arg)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = self._get_replacement_identifier(node.name)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.name = self._get_replacement_identifier(node.name)
        return self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> ast.AST:
        node.names = [self._get_replacement_identifier(name) for name in node.names]
        return self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:
        node.names = [self._get_replacement_identifier(name) for name in node.names]
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node.attr = self._get_replacement_identifier(node.attr)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = self._get_replacement_identifier(node.id)
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        # Don't use isinstance() because bool() is a subtype of int() in Python
        # wtf...
        if type(node.value) is float:
            return ast.Name(self._get_replacement_float(node.value), ctx=ast.Load)
        elif type(node.value) is int:
            return ast.Name(self._get_replacement_int(node.value), ctx=ast.Load)
        elif type(node.value) is str:
            return ast.Name(self._get_replacement_str(node.value), ctx=ast.Load)
        else:
            return node


if __name__ == "__main__":
    functions = extract_functions_from_file(sys.argv[1])

    for name, code in functions.items():
        print("-" * 80)
        print(f"{name}()\n")
        print(f'{"Original: ":-<80}')
        print(code)
        print(f'{"Normalized: ":-<80}')
        print(astor.to_source(CodeNormalizer().visit(ast.parse(code))))
