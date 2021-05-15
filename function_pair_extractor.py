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
import sys
import typing
import warnings
from function_extractor import extract_functions


def extract_function_pairs(
    *, before_code: str, before_name: str, after_code: str, after_name: str
) -> typing.Iterable[typing.Tuple[str, str, str]]:
    before_node = ast.parse(before_code, filename=before_name)
    before_functions = extract_functions(before_node, before_name)
    after_node = ast.parse(after_code, filename=after_name)
    after_functions = extract_functions(after_node, after_name)

    before_functions_seen: "set[str]" = set()
    for func_name, before_func_code in before_functions.items():
        try:
            after_func_code = after_functions[func_name]
        except KeyError:
            warnings.warn(
                f"Missing function in <after>: {func_name}() is present in {before_name} but missing in {after_name}"
            )
        else:
            before_functions_seen.add(func_name)
            yield (func_name, before_func_code, after_func_code)

    # This is just for warnings
    for func_name, after_func_code in after_functions.items():
        if func_name not in before_functions_seen:
            warnings.warn(
                f"Missing function in <before>: {func_name}() is missing in {before_name} but present in {after_name}"
            )


if __name__ == "__main__":
    before_name = sys.argv[1]
    after_name = sys.argv[2]
    with open(before_name, encoding="utf8") as before_file:
        before_code = before_file.read()
    with open(after_name, encoding="utf8") as after_file:
        after_code = after_file.read()

    for func_name, func_before, func_after in extract_function_pairs(
        before_code=before_code,
        before_name=before_name,
        after_code=after_code,
        after_name=after_name,
    ):
        print("-" * 80)
        print(f"Function name: {func_name}()")
        if func_before != func_after:
            print("\nHas differences!\n")
            print(f'{"Before: ":-<80}')
            print(func_before)
            print(f'{"After: ":-<80}')
            print(func_after)
