import ast
import re
import sys
import typing

import astor

from idiom_loader import IdiomDatabase, load_idioms


class ReplacementMap(typing.TypedDict):
    """Dictionary that can be used to restore a normalized code back to its
    original form."""

    identifiers: dict[str, str]
    floats: dict[str, float]
    ints: dict[str, int]
    strings: dict[str, str]
    f_strings: dict[str, str]


def normalize_with_idioms(
    code: str, *, idioms: IdiomDatabase
) -> tuple[str, ReplacementMap]:
    """Normalizes Python code, skipping those in the `idioms` database."""
    code_normalizer = CodeNormalizer(idioms=idioms)
    normalized_code = astor.to_source(code_normalizer.visit(ast.parse(code)))
    return normalized_code, code_normalizer.get_replacement_map()


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
        assert not re.match(
            r"^(?:IDENTIFIER|FLOAT|INT|F_STR)_\d+$", identifier
        ), f"Code already contains identifier {identifier}; normalizing it would destroy its semantics"

        if identifier in self._idioms.identifiers:
            return identifier

        return self._identifiers_seen.setdefault(
            identifier, f"IDENTIFIER_{len(self._identifiers_seen)}"
        )

    def _get_replacement_float(self, literal: float) -> str:
        return self._literals_seen_float.setdefault(
            literal, f"FLOAT_{len(self._literals_seen_float)}"
        )

    def _get_replacement_int(self, literal: int) -> str:
        return self._literals_seen_int.setdefault(
            literal, f"INT_{len(self._literals_seen_int)}"
        )

    def _get_replacement_str(self, literal: str) -> str:
        return self._literals_seen_str.setdefault(
            literal, f"STR_{len(self._literals_seen_str)}"
        )

    def _get_replacement_f_string(self, node: ast.JoinedStr) -> str:
        # There is no easy way to compare two AST nodes for equality.
        # Instead we compare their serialized forms
        code = ast.unparse(node)
        return self._f_strings_seen.setdefault(
            code, f"F_STR_{len(self._f_strings_seen)}"
        )

    def get_replacement_map(self) -> ReplacementMap:
        """Returns mappings for converting normalized code to its original form."""
        return ReplacementMap(
            identifiers={v: k for k, v in self._identifiers_seen.items()},
            floats={v: k for k, v in self._literals_seen_float.items()},
            ints={v: k for k, v in self._literals_seen_int.items()},
            strings={v: k for k, v in self._literals_seen_str.items()},
            f_strings={v: k for k, v in self._f_strings_seen.items()},
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
    from pprint import pprint

    import astor

    from .function_extractor import extract_functions_from_file

    functions = extract_functions_from_file(sys.argv[1])

    idioms = load_idioms()
    for name, node in functions.items():
        code = astor.to_source(node)
        print("-" * 80)
        print(f"{name}()\n")
        print(f'{"Original: ":-<80}')
        print(code)
        print(f'{"Normalized: ":-<80}')
        normalized_code, replacement_map = normalize_with_idioms(code, idioms=idioms)
        print(normalized_code)
        print(f"{'Replacement map: ':-<80}")
        pprint(replacement_map, width=120)


if __name__ == "__main__":
    main()
