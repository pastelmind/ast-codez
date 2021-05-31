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
    root = ast.parse(code)
    code_normalizer = CodeNormalizer(
        identifiers=extract_identifiers(root), idioms=idioms
    )
    normalized_code = astor.to_source(code_normalizer.visit(root))
    return normalized_code, code_normalizer.get_replacement_map()


def generate_names(
    prefix: str, exclude: typing.Collection[str]
) -> typing.Generator[str, None, None]:
    """Infinite generator that generates names.

    Args:
        prefix: Prefix for generated names
        exclude: Collection of names to exclude
    Yields:
        Generated names are of the form `<prefix>0`, `<prefix>1`, ...
        If a generated name already exists in `exclude`, it is skipped.
    """
    counter = 0
    while True:
        name = prefix + str(counter)
        if name not in exclude:
            yield name
        counter += 1


class CodeNormalizer(ast.NodeTransformer):
    """
    Scans Python source code and replaces identifiers and constants with special
    constants so that the model only has to deal with a limited number of
    vocabulary.

    - We don't override import from because there's no point!
    """

    def __init__(self, identifiers: set[str], idioms: IdiomDatabase):
        super().__init__()
        # Note: Since functions are first-class objects in Python, we can't
        # distinguish function names from variable names.
        self._identifiers_seen: typing.Dict[str, str] = {}
        self._literals_seen_float: typing.Dict[float, str] = {}
        self._literals_seen_int: typing.Dict[int, str] = {}
        self._literals_seen_str: typing.Dict[str, str] = {}
        self._f_strings_seen: typing.Dict[str, str] = {}
        self._identifier_name_generator = generate_names("IDENTIFIER_", identifiers)
        self._literal_float_name_generator = generate_names("FLOAT_", identifiers)
        self._literal_int_name_generator = generate_names("INT_", identifiers)
        self._literal_str_name_generator = generate_names("STR_", identifiers)
        self._f_string_name_generator = generate_names("F_STR_", identifiers)
        self._idioms = idioms

    def _get_replacement_identifier(self, identifier: str) -> str:
        if identifier in self._idioms.identifiers:
            return identifier

        return self._identifiers_seen.get(
            identifier
        ) or self._identifiers_seen.setdefault(
            identifier, next(self._identifier_name_generator)
        )

    def _get_replacement_float(self, literal: float) -> str:
        return self._literals_seen_float.get(
            literal
        ) or self._literals_seen_float.setdefault(
            literal, next(self._literal_float_name_generator)
        )

    def _get_replacement_int(self, literal: int) -> str:
        return self._literals_seen_int.get(
            literal
        ) or self._literals_seen_int.setdefault(
            literal, next(self._literal_int_name_generator)
        )

    def _get_replacement_str(self, literal: str) -> str:
        return self._literals_seen_str.get(
            literal
        ) or self._literals_seen_str.setdefault(
            literal, next(self._literal_str_name_generator)
        )

    def _get_replacement_f_string(self, node: ast.JoinedStr) -> str:
        # There is no easy way to compare two AST nodes for equality.
        # Instead we compare their serialized forms
        code = ast.unparse(node)
        return self._f_strings_seen.get(code) or self._f_strings_seen.setdefault(
            code, next(self._f_string_name_generator)
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


# Map of AST node class -> instance attributes that contain identifier(s)
_ATTIBS_TO_CHECK: dict[typing.Type[ast.AST], list[str]] = {
    ast.FunctionDef: ["name"],
    ast.AsyncFunctionDef: ["name"],
    ast.ClassDef: ["name"],
    ast.ImportFrom: ["module"],
    ast.Global: ["names"],
    ast.Nonlocal: ["names"],
    ast.Attribute: ["attr"],
    ast.Name: ["id"],
    ast.ExceptHandler: ["name"],
    ast.arg: ["arg"],
    ast.keyword: ["arg"],
    ast.alias: ["name", "asname"],
}


def extract_identifiers(node: ast.AST) -> set[str]:
    """Extracts all identifiers within an AST node."""
    identifiers: set[str] = set()

    # ast.walk() is ~10% faster than a NodeVisitor subclass.
    # Also, it is free from RecursionError
    for n in ast.walk(node):
        try:
            attr_names = _ATTIBS_TO_CHECK[type(n)]
        except KeyError:
            continue
        for attr_name in attr_names:
            value = getattr(n, attr_name)
            if type(value) is str:
                identifiers.add(value)
            elif value is not None:
                identifiers.update(value)

    return identifiers


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
