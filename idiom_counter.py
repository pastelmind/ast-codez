"""
Script that scans a directory for Python code and generates an idiom database
(JSON file).

What is an idiom?

An idiom is an identifier or constant that is seen very often throughout
Python code. For example,

    with open('asdf') as f:
        print(f.read())

In this example, words like 'open' and 'f' occur frequently in Python code.
If we abstract those away, we would be actually increasing the vocabulary, not
decreasing it. Thus, we treat them as idioms, and leave them alone.
"""

import ast
import collections
import json
import pathlib
import sys
import typing
import warnings


class IdiomCollector(ast.NodeVisitor):
    """Traverses AST nodes and collects identifiers."""

    def __init__(self) -> None:
        super().__init__()
        self._identifiers_seen: typing.Counter[str] = collections.Counter()
        self._literals_seen_float: typing.Counter[float] = collections.Counter()
        self._literals_seen_int: typing.Counter[int] = collections.Counter()
        self._literals_seen_str: typing.Counter[str] = collections.Counter()

    def _add_identifier(self, identifier: str) -> None:
        self._identifiers_seen[identifier] += 1

    def _add_float(self, value: float) -> None:
        self._literals_seen_float[value] += 1

    def _add_int(self, value: int) -> None:
        self._literals_seen_int[value] += 1

    def _add_str(self, value: str) -> None:
        self._literals_seen_str[value] += 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._add_identifier(node.name)
        return self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        self._add_identifier(node.arg)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._add_identifier(node.name)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._add_identifier(node.name)
        return self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> ast.AST:
        for name in node.names:
            self._add_identifier(name)
        return self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:
        for name in node.names:
            self._add_identifier(name)
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self._add_identifier(node.attr)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        self._add_identifier(node.id)
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if node.value is None or node.value is Ellipsis:
            return node

        # Don't use isinstance() because bool() is a subtype of int() in Python
        # wtf...
        value_type = type(node.value)
        if value_type is float:
            self._add_float(node.value)
        elif value_type is int:
            self._add_int(node.value)
        elif value_type is str:
            self._add_str(node.value)
        elif value_type is bool or value_type is bytes:
            pass
        else:
            warnings.warn("Unknown type: " + str(value_type))

        return node


if __name__ == "__main__":
    # This writes the results to a JSON file, so no need to pipe it to anything
    collector = IdiomCollector()

    basedir = pathlib.Path(sys.argv[1])
    counter = 0
    for file_path in basedir.rglob("*.py"):
        print(f"Parsing {file_path}", flush=True)
        try:
            node = ast.parse(
                file_path.read_text(encoding="utf8"), filename=str(file_path)
            )
        except SyntaxError:
            warnings.warn(f"Skipping due to SyntaxError at {file_path}")
            continue
        collector.visit(node)
        counter += 1

    HORIZONTAL_BAR = "-" * 80
    print(HORIZONTAL_BAR)
    print(f"Processed {counter} file(s)")

    cutoff = min(200, len(collector._identifiers_seen))
    print(HORIZONTAL_BAR)
    print(f"Top {cutoff} identifiers:")
    identifiers_cutoff = collector._identifiers_seen.most_common(cutoff)
    for identifier, count in identifiers_cutoff:
        print(f"{count}: {identifier}")

    cutoff = min(50, len(collector._literals_seen_float))
    print(HORIZONTAL_BAR)
    print(f"Top {cutoff} floats:")
    float_cutoff = collector._literals_seen_float.most_common(cutoff)
    for value, count in float_cutoff:
        print(f"{count}: {value!r}")

    cutoff = min(50, len(collector._literals_seen_int))
    print(HORIZONTAL_BAR)
    print(f"Top {cutoff} ints:")
    int_cutoff = collector._literals_seen_int.most_common(cutoff)
    for value, count in int_cutoff:
        print(f"{count}: {value!r}")

    cutoff = min(200, len(collector._literals_seen_str))
    print(HORIZONTAL_BAR)
    print(f"Top {cutoff} strings:")
    str_cutoff = collector._literals_seen_str.most_common(cutoff)
    for value, count in str_cutoff:
        print(f"{count}: {value!r}")

    result_file = "idioms.json"
    with open(result_file, mode="w", encoding="utf8") as json_file:
        json.dump(
            {
                "identifiers": [
                    {"value": value, "count": count}
                    for value, count in identifiers_cutoff
                ],
                "float": [
                    {"value": value, "count": count} for value, count in float_cutoff
                ],
                "int": [
                    {"value": value, "count": count} for value, count in int_cutoff
                ],
                "str": [
                    {"value": value, "count": count} for value, count in str_cutoff
                ],
            },
            json_file,
            indent=2,
        )
    print("Results written to " + result_file)
