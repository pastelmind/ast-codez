import ast
import sys
import typing

import astor

from idiom_loader import IdiomDatabase, load_idioms


def normalize_with_idioms(code: str, *, idioms: IdiomDatabase) -> str:
    """Normalizes Python code, skipping those in the `idioms` database."""
    return astor.to_source(CodeNormalizer(idioms=idioms).visit(ast.parse(code)))


class CodeNormalizer(ast.NodeTransformer):
    """
    Scans Python source code and replaces identifiers and constants with special
    constants so that the model only has to deal with a limited number of
    vocabulary.

    - We don't override import from because there's no point!
    """

    def __init__(self, idioms: IdiomDatabase):
        super().__init__()
        # Note: Since functions are first-class objects in Python, we can't
        # distinguish function names from variable names.
        self._identifiers_seen: typing.Dict[str, str] = {}
        self._literals_seen_float: typing.Dict[float, str] = {}
        self._literals_seen_int: typing.Dict[int, str] = {}
        self._literals_seen_str: typing.Dict[str, str] = {}
        self._f_strings_seen: typing.Dict[str, str] = {}
        self._idioms = idioms

    def _get_replacement_identifier(self, identifier: str) -> str:
        if identifier in self._idioms.identifiers:
            return identifier

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

    def _get_replacement_f_string(self, node: ast.JoinedStr) -> str:
        # There is no easy way to compare two AST nodes for equality.
        # Instead we compare their serialized forms
        code = ast.unparse(node)
        return self._f_strings_seen.setdefault(
            code, f"F_STR_{len(self._f_strings_seen)}"
        )

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
            if node.value not in self._idioms.floats:
                return ast.Name(self._get_replacement_float(node.value), ctx=ast.Load())
        elif type(node.value) is int:
            if node.value not in self._idioms.ints:
                return ast.Name(self._get_replacement_int(node.value), ctx=ast.Load())
        elif type(node.value) is str:
            if node.value not in self._idioms.strings:
                return ast.Name(self._get_replacement_str(node.value), ctx=ast.Load())

        return node

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
        # f-strings are difficult (if not impossible) to normalize.
        # So we basically cheat here by replacing the entire f-string with a
        # unique identifier.
        return ast.Name(self._get_replacement_f_string(node), ctx=ast.Load())


def main():
    from .function_extractor import extract_functions_from_file

    functions = extract_functions_from_file(sys.argv[1])

    idioms = load_idioms()
    for name, code in functions.items():
        print("-" * 80)
        print(f"{name}()\n")
        print(f'{"Original: ":-<80}')
        print(code)
        print(f'{"Normalized: ":-<80}')
        print(normalize_with_idioms(code, idioms=idioms))


if __name__ == "__main__":
    main()
