"""
Given a BEFORE.PY and AFTER.PY, extracts all matching pairs of functions and
class methods.

Explanation of the process:

1. Scan BEFORE.PY, recording all functions and methods.
2. Scan AFTER.PY, recording all functions and methods.
3. Attempt to pair off all functions in BEFORE.PY with all functions in AFTER.PY
   by name.

We make some big assumptions to make things easy:

1. Classes and functions are never created, removed, moved, or renamed.

- If a function is missing from BEFORE.PY but in AFTER.PY (or vice versa), we
  don't care about it.
- If a function is renamed in AFTER.PY, we don't care about it.

2. Functions are always at the top (module) level, or inside a class.

- We don't care about functions defined inside other functions.
- We don't care about lambdas.

3. Classes are always at the top (module) level.

- We don't care about classes inside other classes, or classes inside functions.

4. Within a single module, functions, methods, and classes have unique names.

- Each function is uniquely identified by its name
    - key: <function name>
- Each method is uniquely identified by <Class name> + <method name>
    - key: <class name>.<function name>
    - We don't distinguish between class methods, static methods, and instance
      methods
    - We don't care about getters and setters

...ugh. Can we just diff entire files instead?
"""

import ast
import logging
import typing

from .function_extractor import extract_functions


class FunctionPair(typing.NamedTuple):
    """Represents the buggy and fixed versions of a function."""

    func_name: str
    before_node: ast.AST
    after_node: ast.AST


def extract_function_pairs(
    *, before_code: str, before_name: str, after_code: str, after_name: str
) -> typing.Iterator[FunctionPair]:
    """Extracts function pairs from `before_code` and `after_code`

    Args:
        before_code:
            Python code before changes
        before_name:
            Name of the script file before changes, used only for messages
        after_code:
            Python code before changes
        after_name:
            Name of the script file after changes, used only for messages

    Yields:
        A NamedTuple `FunctionPair`
    """
    before_node = ast.parse(before_code, filename=before_name)
    before_functions = extract_functions(before_node)
    after_node = ast.parse(after_code, filename=after_name)
    after_functions = extract_functions(after_node)

    before_functions_seen: "set[str]" = set()
    for func_name, before_func_node in before_functions.items():
        try:
            after_func_node = after_functions[func_name]
        except KeyError:
            logging.debug(
                f"Missing function in <after>: {func_name}() is present in {before_name} but missing in {after_name}"
            )
        else:
            before_functions_seen.add(func_name)
            yield FunctionPair(
                func_name=func_name,
                before_node=before_func_node,
                after_node=after_func_node,
            )

    # This is just for warnings
    for func_name, after_func_node in after_functions.items():
        if func_name not in before_functions_seen:
            logging.debug(
                f"Missing function in <before>: {func_name}() is missing in {before_name} but present in {after_name}"
            )


def main(argv: typing.Optional[typing.Sequence[str]] = None):
    import argparse
    import pathlib

    import astor

    parser = argparse.ArgumentParser(
        prog="python -m ast_codez_tools." + pathlib.Path(__file__).stem
    )
    parser.add_argument("before_file", help="Path to Python file before changes")
    parser.add_argument("after_file", help="Path to Python file after changes")
    args = parser.parse_args(argv)

    before_name: str = args.before_file
    after_name: str = args.after_file
    before_code = pathlib.Path(before_name).read_text(encoding="utf8")
    after_code = pathlib.Path(after_name).read_text(encoding="utf8")

    for func_name, before_node, after_node in extract_function_pairs(
        before_code=before_code,
        before_name=before_name,
        after_code=after_code,
        after_name=after_name,
    ):
        func_before = astor.to_source(before_node)
        func_after = astor.to_source(after_node)

        print("-" * 80)
        print(f"Function name: {func_name}()")
        if func_before != func_after:
            print("\nHas differences!\n")
            print(f'{"Before: ":-<80}')
            print(func_before)
            print(f'{"After: ":-<80}')
            print(func_after)


if __name__ == "__main__":
    main()
