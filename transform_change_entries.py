"""Converts the downloaded Change Entries into a format that can be passed to
seq2seq.

Steps for each change entry:

1. Excluded unwanted changes. These include:

    - If either the before_code or after_code cannot be parsed
      (May happen if they are Python 2 code, not Python 3)

2. From the before_code and after_code, extract top-level functions and methods
    of top-level classes.
    Find matching function/method pairs in before_code and after_code.

    See `function_pair_extractor.py` for more info.

3. Exclude function pairs that are identical.
    This is an optimization step that does what step 5 does.

4. Normalize before_code and after_code. This does:

    - Replaces identifiers and constants with special constants
      (e.g. INT_1, STR_1, IDENTIFIER_2) so that the model can work with a
      limited vocabulary.
    - Converts Python code to a single-line representation so that seq2seq can
      recognize semantically significant tokens (e.g. indents) as words.

5. Exclude normalized function pairs that are identical.
    This leaves us with function pairs that have changes.
"""

import ast
import io
import logging
import tokenize
import typing

import astor
import jsonlines

from ast_codez_tools.code_normalizer import CodeNormalizer
from ast_codez_tools.function_pair_extractor import extract_function_pairs
from idiom_loader import IdiomDatabase, load_idioms


def yield_changed_entries(
    *, changed_entries_file: str
) -> typing.Iterator[typing.Dict[str, str]]:
    with jsonlines.open(changed_entries_file, mode="r") as rows:
        yield from rows


_HORIZONTAL_BAR = "-" * 80
_HORIZONTAL_DOUBLE_BAR = "=" * 80


class NormalizedFunctionChangeEntry(typing.NamedTuple):
    name: str
    before_code: str
    after_code: str


def extract_normalized_function_changes(
    *, changed_entries_file: str
) -> typing.Iterator[NormalizedFunctionChangeEntry]:
    """
    Yields:
        Tuple of `(func_name, before_code_normalized, after_code_normalized)`
    """
    idioms = load_idioms()

    for row in yield_changed_entries(changed_entries_file=changed_entries_file):
        repo_name = row["repository"]
        commit_before = row["commit_before"]
        commit_after = row["commit_after"]
        file_before = row["file_before"]
        file_after = row["file_after"]
        code_before = row["code_before"]
        code_after = row["code_after"]

        try:
            for func_name, func_code_before, func_code_after in extract_function_pairs(
                before_code=code_before,
                before_name=f"{repo_name}:{commit_before}:{file_before}",
                after_code=code_after,
                after_name=f"{repo_name}:{commit_after}:{file_after}",
            ):
                # Optimization!
                if func_code_before == func_code_after:
                    logging.info(
                        f"Skipped identical function: {repo_name}:{commit_after}:{file_after}:{func_name}()"
                    )
                    continue

                normalized_before_code, normalized_after_code = normalize_code_pair(
                    idioms=idioms,
                    before_code=func_code_before,
                    after_code=func_code_after,
                )
                if normalized_before_code == normalized_after_code:
                    logging.info(
                        f"Skipped identical function after normalizing: {repo_name}:{commit_after}:{file_after}:{func_name}()"
                    )
                    continue

                yield NormalizedFunctionChangeEntry(
                    name=f"{repo_name}:{commit_after}:{file_after}:{func_name}",
                    before_code=normalized_before_code,
                    after_code=normalized_after_code,
                )
        except SyntaxError as e:
            # We may have invalid Python code, or Python 2 code
            #
            # Fortunately, we don't need care about hashbang because ast.parse()
            # ignores it
            logging.warn(
                f"Skipped because of invalid Python syntax in {repo_name}:{commit_after}:{file_after}\n{e.msg}"
            )


def normalize_code_pair(
    *, idioms: IdiomDatabase, before_code: str, after_code: str
) -> typing.Tuple[str, str]:
    """Normalizes before_code, after_code using a single CodeNormalizer.

    Using the same CodeNormalizer instance allows identical identifiers to be
    normalized in a predictable manner.
    """
    normalizer = CodeNormalizer(idioms=idioms)
    # According to our paper, order is important.
    # We process
    normalized_before_code = astor.to_source(normalizer.visit(ast.parse(before_code)))
    normalized_after_code = astor.to_source(normalizer.visit(ast.parse(after_code)))
    return (
        transform_to_oneline(normalized_before_code),
        transform_to_oneline(normalized_after_code),
    )


def transform_to_oneline(code: str) -> str:
    """Transforms the given Python code to a single-line representation."""

    def tokenize_to_one_liner(code: str) -> typing.Iterator[str]:
        # I took inspiration from Nabila's code
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            # Strip comments and logically insignificant newlines
            if tok.type == tokenize.NL or tok.type == tokenize.COMMENT:
                continue
            # Replace logically significant whitespace
            elif tok.type == tokenize.NEWLINE:
                yield "$NEWLINE"
            elif tok.type == tokenize.INDENT:
                yield "$INDENT"
            elif tok.type == tokenize.DEDENT:
                yield "$DEDENT"
            else:
                yield tok.string

    one_liner = " ".join(tokenize_to_one_liner(code))
    assert "\n" not in one_liner
    return one_liner


def main():
    for entry in extract_normalized_function_changes(
        changed_entries_file="../github_file_changes/file_changes_chunk0.jsonl"
    ):
        print(entry)


if __name__ == "__main__":
    main()